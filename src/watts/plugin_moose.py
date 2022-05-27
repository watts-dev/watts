# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

from .fileutils import PathLike, run as run_proc
from .parameters import Parameters
from .plugin import TemplatePlugin
from .results import Results


class ResultsMOOSE(Results):
    """MOOSE simulation results

    Parameters
    ----------
    params
        Parameters used to generate inputs
    name
        Name of workflow producing results
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
    def __init__(self, params: Parameters, name: str, time: datetime,
                 inputs: List[PathLike], outputs: List[PathLike]):
        super().__init__('MOOSE', params, name, time, inputs, outputs)
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
                csv_data[column_name] = np.array(csv_file_df[column_name])

        # Read MOOSE's vector postprocesssor '.csv' files and save the
        # parameters as individual array
        for output in self.outputs:
            if (output.name.startswith(f"{input_file.stem}_csv_") and
                not output.name.endswith("_0000.csv")):
                vector_csv_df = pd.read_csv(output)
                csv_param = list(set(vector_csv_df.columns) - {"id", "x", "y", "z"})
                csv_data[output.stem] = np.array(vector_csv_df[csv_param[0]], dtype=float)

                for name in ("id", "x", "y", "z"):
                    new_name = output.name[:-8] + name
                    if new_name not in csv_data:
                        csv_data[new_name] = np.array(vector_csv_df[name], dtype=float)

        return csv_data


class PluginMOOSE(TemplatePlugin):
    """Plugin for running MOOSE

    Parameters
    ----------
    template_file
        Templated MOOSE input
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when MOOSE is run
    show_stderr
        Whether to display output from stderr when MOOSE is run

    Attributes
    ----------
    executable
        Path to MOOSE executable

    """

    def __init__(self, template_file: str,
                 extra_inputs: Optional[List[str]] = None,
                 extra_template_inputs: Optional[List[PathLike]] = None,
                 show_stdout: bool = False, show_stderr: bool = False):
        super().__init__(template_file, extra_inputs, extra_template_inputs,
                         show_stdout, show_stderr)
        self._executable = Path('moose-opt')
        self.input_name = "MOOSE.i"

    def run(self, mpi_args: Optional[List[str]] = None):
        """Run MOOSE

        Parameters
        ----------
        mpi_args
            MPI execute command and any additional MPI arguments to pass,
            e.g. ['mpiexec', '-n', '8'].

        """
        if mpi_args is None:
            mpi_args = []
        run_proc(mpi_args + [self.executable, "-i", self.input_name])
