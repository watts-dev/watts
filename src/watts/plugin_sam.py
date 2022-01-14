# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import List

import h5py
import numpy as np
import pandas as pd

from .fileutils import PathLike, run as run_proc, tee_stdout, tee_stderr
from .parameters import Parameters
from .plugin import TemplatePlugin
from .results import Results


class ResultsSAM(Results):
    """SAM simulation results

    Parameters
    ----------
    params
        Parameters used to generate inputs
    time
        Time at which workflow was run
    inputs
        List of input files
    outputs
        List of output files

    Attributes
    ----------
    stdout
        Standard output from SAM run
    csv_data
        Dictionary with data from .csv files
    """
    def __init__(self, params: Parameters, time: datetime,
                 inputs: List[PathLike], outputs: List[PathLike]):
        super().__init__('SAM', params, time, inputs, outputs)
        self.csv_data = self._save_SAM_csv()

    @property
    def stdout(self) -> str:
        return (self.base_path / "SAM_log.txt").read_text()

    def _save_SAM_csv(self) -> dict:
        """Read all SAM '.csv' files and return results in a dictionary

        Returns
        -------
        Results from SAM .csv files

        """
        input_file = self.inputs[0]
        csv_file = input_file.with_name(f"{input_file.stem}_csv.csv")

        # Save SAM's main output '.csv' files
        csv_data = {}
        if csv_file.exists():
            csv_file_df = pd.read_csv(csv_file)
            for column_name in csv_file_df.columns:
                csv_data[column_name] =  np.array(csv_file_df[column_name])

        # Read SAM's vector postprocesssor '.csv' files and save the parameters as individual array
        for output in self.outputs:
            if output.name.startswith(f"{input_file.stem}_csv_") and not output.name.endswith("_0000.csv"):
                vector_csv_df = pd.read_csv(output)
                csv_param = list(set(vector_csv_df.columns) - {"id", "x", "y", "z"})
                csv_data[output.stem] = np.array(vector_csv_df[csv_param[0]], dtype=float)

                for name in ("id", "x", "y", "z"):
                    new_name = output.name[:-8] + name
                    if new_name not in csv_data:
                        csv_data[new_name] = np.array(vector_csv_df[name], dtype=float)

        return csv_data

    def save(self, filename: PathLike):
        """Save results to an HDF5 file

        Parameters
        ----------
        filename
            File to save results to
        """
        with h5py.File(filename, 'w') as h5file:
            super()._save(h5file)

    @classmethod
    def _from_hdf5(cls, obj: h5py.Group):
        """Load results from an HDF5 file

        Parameters
        ----------
        obj
            HDF5 group to load results from
        """
        time, parameters, inputs, outputs = Results._load(obj)
        return cls(parameters, time, inputs, outputs)


class PluginSAM(TemplatePlugin):
    """Plugin for running SAM

    Parameters
    ----------
    template_file
        Templated SAM input
    show_stdout
        Whether to display output from stdout when SAM is run
    show_stderr
        Whether to display output from stderr when SAM is run

    Attributes
    ----------
    sam_exec
        Path to SAM executable

    """
    def  __init__(self, template_file: str, show_stdout: bool = False,
                  show_stderr: bool = False):
        super().__init__(template_file)
        self._sam_exec = Path('sam-opt')
        self.sam_inp_name = "SAM.i"
        self.show_stdout = show_stdout
        self.show_stderr = show_stderr

    @property
    def sam_exec(self) -> Path:
        return self._sam_exec

    @sam_exec.setter
    def sam_exec(self, exe: PathLike):
        if shutil.which(exe) is None:
            raise RuntimeError(f"SAM executable '{exe}' is missing.")
        self._sam_exec = Path(exe)

    def options(self, sam_exec):
        """Input SAM user-specified options

        Parameters
        ----------
        SAM_exec
            Path to SAM executable
        """
        self.sam_exec = sam_exec

    def prerun(self, params: Parameters):
        """Generate the SAM input based on the template

        Parameters
        ----------
        params
            Parameters used when rendering template

        """
        self._run_time = time.time_ns()
        # Render the template
        print("Pre-run for SAM Plugin")
        super().prerun(params, filename=self.sam_inp_name)

    def run(self):
        """Run SAM"""
        print("Run for SAM Plugin")

        log_file = Path("SAM_log.txt")

        with log_file.open("w") as outfile:
            func_stdout = tee_stdout if self.show_stdout else redirect_stdout
            func_stderr = tee_stderr if self.show_stderr else redirect_stderr
            with func_stdout(outfile), func_stderr(outfile):
                run_proc([self.sam_exec, "-i", self.sam_inp_name])


    def postrun(self, params: Parameters) -> ResultsSAM:
        """Read SAM results and create results object

        Parameters
        ----------
        params
            Parameters used to create SAM model

        Returns
        -------
        SAM results object
        """
        print("Post-run for SAM Plugin")

        time = datetime.fromtimestamp(self._run_time * 1e-9)
        inputs = ['SAM.i']
        outputs = [p for p in Path.cwd().iterdir() if p.name not in inputs]
        return ResultsSAM(params, time, inputs, outputs)

