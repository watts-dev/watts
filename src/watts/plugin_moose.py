# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from typing import List, Optional

import numpy as np
import pandas as pd

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import PluginGeneric, _find_executable
from .results import Results, ExecInfo


class ResultsMOOSE(Results):
    """MOOSE simulation results

    Parameters
    ----------
    params
        Parameters used to generate inputs
    exec_info
        Execution information (job ID, plugin name, time, etc.)
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
    def __init__(self, params: Parameters, exec_info: ExecInfo,
                 inputs: List[PathLike], outputs: List[PathLike]):
        super().__init__(params, exec_info, inputs, outputs)
        self.csv_data = self._save_MOOSE_csv()

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


class PluginMOOSE(PluginGeneric):
    """Plugin for running MOOSE

    Parameters
    ----------
    template_file
        Templated MOOSE input
    executable
        Path to MOOSE executable
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
    execute_command
        List of command-line arguments used to call the executable

    """

    def __init__(
        self,
        template_file: str,
        executable: PathLike = 'moose-opt',
        extra_inputs: Optional[List[str]] = None,
        extra_template_inputs: Optional[List[PathLike]] = None,
        show_stdout: bool = False,
        show_stderr: bool = False
    ):
        executable = _find_executable(executable, 'MOOSE_DIR')
        execute_command = ['{self.executable}', '-i', '{self.input_name}']
        super().__init__(
            executable, execute_command, template_file, extra_inputs,
            extra_template_inputs, "MOOSE", show_stdout, show_stderr)
        self.input_name = "MOOSE.i"
