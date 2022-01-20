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


class ResultsMOOSE(Results):
    """MOOSE simulation results

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
        Standard output from MOOSE run
    csv_data
        Dictionary with data from .csv files
    """
    def __init__(self, params: Parameters, time: datetime,
                 inputs: List[PathLike], outputs: List[PathLike]):
        super().__init__('MOOSE', params, time, inputs, outputs)
        self.csv_data = self._save_MOOSE_csv()

    @property
    def stdout(self) -> str:
        return (self.base_path / "MOOSE_log.txt").read_text()

    def _save_MOOSE_csv(self) -> dict:
        """Read all MOOSE '.csv' files and return results in a dictionary

        Returns
        -------
        Results from MOOSE .csv files

        """
        input_file = self.inputs[0]
        csv_file = input_file.with_name(f"{input_file.stem}_csv.csv")

        # Save MOOSE's main output '.csv' files
        csv_data = {}
        if csv_file.exists():
            csv_file_df = pd.read_csv(csv_file)
            for column_name in csv_file_df.columns:
                csv_data[column_name] =  np.array(csv_file_df[column_name])

        # Read MOOSE's vector postprocesssor '.csv' files and save the parameters as individual array
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


class PluginMOOSE(TemplatePlugin):
    """Plugin for running MOOSE

    Parameters
    ----------
    template_file
        Templated MOOSE input
    show_stdout
        Whether to display output from stdout when MOOSE is run
    show_stderr
        Whether to display output from stderr when MOOSE is run

    Attributes
    ----------
    moose_exec
        Path to MOOSE executable

    """
    def  __init__(self, template_file: str, show_stdout: bool = False,
                  show_stderr: bool = False, n_cpu: int = 1):
        super().__init__(template_file)
        self._moose_exec = Path('moose-opt')
        self.moose_inp_name = "MOOSE.i"
        self.show_stdout = show_stdout
        self.show_stderr = show_stderr
        if n_cpu < 1:
            raise RuntimeError(f"The CPU number used to run MOOSE app must be a natural number.")
        self.n_cpu = n_cpu

    @property
    def moose_exec(self) -> Path:
        return self._moose_exec

    @moose_exec.setter
    def moose_exec(self, exe: PathLike):
        if shutil.which(exe) is None:
            raise RuntimeError(f"MOOSE executable '{exe}' is missing.")
        self._moose_exec = Path(exe)

    def options(self, moose_exec):
        """Input MOOSE user-specified options

        Parameters
        ----------
        MOOSE_exec
            Path to MOOSE executable
        """
        self.moose_exec = moose_exec

    def prerun(self, params: Parameters):
        """Generate the MOOSE input based on the template

        Parameters
        ----------
        params
            Parameters used when rendering template

        """
        self._run_time = time.time_ns()
        # Render the template
        print("Pre-run for MOOSE Plugin")
        super().prerun(params, filename=self.moose_inp_name)

    def run(self):
        """Run MOOSE"""
        print("Run for MOOSE Plugin")

        log_file = Path("MOOSE_log.txt")

        with log_file.open("w") as outfile:
            func_stdout = tee_stdout if self.show_stdout else redirect_stdout
            func_stderr = tee_stderr if self.show_stderr else redirect_stderr
            with func_stdout(outfile), func_stderr(outfile):
                run_proc(["mpiexec", "-n", str(self.n_cpu) , self.moose_exec, "-i", self.moose_inp_name])


    def postrun(self, params: Parameters) -> ResultsMOOSE:
        """Read MOOSE results and create results object

        Parameters
        ----------
        params
            Parameters used to create MOOSE model

        Returns
        -------
        MOOSE results object
        """
        print("Post-run for MOOSE Plugin")

        time = datetime.fromtimestamp(self._run_time * 1e-9)
        inputs = ['MOOSE.i']
        outputs = [p for p in Path.cwd().iterdir() if p.name not in inputs]
        return ResultsMOOSE(params, time, inputs, outputs)
