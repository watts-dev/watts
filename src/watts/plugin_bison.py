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


class ResultsBISON(Results):
    """BISON simulation results

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
        Standard output from BISON run
    csv_data
        Dictionary with data from .csv files
    """
    def __init__(self, params: Parameters, time: datetime,
                 inputs: List[PathLike], outputs: List[PathLike]):
        super().__init__('BISON', params, time, inputs, outputs)
        self.csv_data = self._save_BISON_csv()

    @property
    def stdout(self) -> str:
        return (self.base_path / "BISON_log.txt").read_text()

    def _save_BISON_csv(self) -> dict:
        """Read all BISON '.csv' files and return results in a dictionary

        Returns
        -------
        Results from BISON .csv files

        """
        input_file = self.inputs[0]
        csv_file = input_file.with_name(f"{input_file.stem}_csv.csv")

        # Save BISON's main output '.csv' files
        csv_data = {}
        if csv_file.exists():
            csv_file_df = pd.read_csv(csv_file)
            for column_name in csv_file_df.columns:
                csv_data[column_name] =  np.array(csv_file_df[column_name])

        # Read BISON's vector postprocesssor '.csv' files and save the parameters as individual array
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


class PluginBISON(TemplatePlugin):
    """Plugin for running BISON

    Parameters
    ----------
    template_file
        Templated BISON input
    show_stdout
        Whether to display output from stdout when BISON is run
    show_stderr
        Whether to display output from stderr when BISON is run

    Attributes
    ----------
    bison_exec
        Path to BISON executable

    """
    def  __init__(self, template_file: str, show_stdout: bool = False,
                  show_stderr: bool = False):
        super().__init__(template_file)
        self._bison_exec = Path('bison-opt')
        self.bison_inp_name = "BISON.i"
        self.show_stdout = show_stdout
        self.show_stderr = show_stderr

    @property
    def bison_exec(self) -> Path:
        return self._bison_exec

    @bison_exec.setter
    def bison_exec(self, exe: PathLike):
        if shutil.which(exe) is None:
            raise RuntimeError(f"BISON executable '{exe}' is missing.")
        self._bison_exec = Path(exe)

    def options(self, bison_exec):
        """Input BISON user-specified options

        Parameters
        ----------
        BISON_exec
            Path to BISON executable
        """
        self.bison_exec = bison_exec

    def prerun(self, params: Parameters):
        """Generate the BISON input based on the template

        Parameters
        ----------
        params
            Parameters used when rendering template

        """
        self._run_time = time.time_ns()
        # Render the template
        print("Pre-run for BISON Plugin")
        super().prerun(params, filename=self.bison_inp_name)

    def run(self):
        """Run BISON"""
        print("Run for BISON Plugin")

        log_file = Path("BISON_log.txt")

        with log_file.open("w") as outfile:
            func_stdout = tee_stdout if self.show_stdout else redirect_stdout
            func_stderr = tee_stderr if self.show_stderr else redirect_stderr
            with func_stdout(outfile), func_stderr(outfile):
                run_proc([self.bison_exec, "-i", self.bison_inp_name])


    def postrun(self, params: Parameters) -> ResultsBISON:
        """Read BISON results and create results object

        Parameters
        ----------
        params
            Parameters used to create BISON model

        Returns
        -------
        BISON results object
        """
        print("Post-run for BISON Plugin")

        time = datetime.fromtimestamp(self._run_time * 1e-9)
        inputs = ['BISON.i']
        outputs = [p for p in Path.cwd().iterdir() if p.name not in inputs]
        return ResultsBISON(params, time, inputs, outputs)
