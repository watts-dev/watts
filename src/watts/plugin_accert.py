# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from datetime import datetime
from pathlib import Path
import os
import sys
from typing import List, Optional
import pandas as pd

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import PluginGeneric, _find_executable
from .results import Results


class PluginACCERT(PluginGeneric):
    """Plugin for running ACCERT

    Parameters
    ----------
    template_file
        Templated ACCERT input
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when ACCERT is run
    show_stderr
        Whether to display output from stderr when ACCERT is run

    Attributes
    ----------
    executable
        Path to ACCERT executable

    """

    def __init__(self, template_file: str,
                 executable: PathLike = 'Main.py',
                 extra_inputs: Optional[List[str]] = None,
                 extra_template_inputs: Optional[List[PathLike]] = None,
                 show_stdout: bool = False, show_stderr: bool = False):
        executable = _find_executable(executable, 'ACCERT_DIR')
        execute_command = [sys.executable, '{self.executable}', '-i','{self.input_name}']
        super().__init__(executable, execute_command, template_file, extra_inputs,
                         extra_template_inputs, show_stdout, show_stderr)
        self.input_name = "ACCERT_input.son"

    @PluginGeneric.executable.setter
    def executable(self, exe: PathLike):
        if not exe.is_file():
            raise RuntimeError(
                f"{self.plugin_name} module '{exe}' does not exist. The "
                "ACCERT_DIR environment variable needs to be set to a directory "
                "containing the Main.py module."
            )
        self._executable = Path(exe)



class ResultsACCERT(Results):
    """ACCERT simulation results

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
    total_cost
        ACCERT results of total cost
    account_table
        ACCERT results of account table
    """

    def __init__(self, params: Parameters, name: str, time: datetime,
                 inputs: List[Path], outputs: List[Path]):
        super().__init__(params, name, time, inputs, outputs)
        self.account_table = self._get_account_table()
        self.total_cost = self.total_cost()

    def total_cost(self):
        return self.account_table['total_cost'].values[0]

    def _get_account_table(self) -> pd.DataFrame:
        """Read ACCERT '.xlsx' file and return results' table

        Returns
        -------
        Results from ACCERT_updated_account.xlsx

        """
        account_table = pd.DataFrame()
        if Path('output.out').exists():
            account_table = pd.read_excel('ACCERT_updated_account.xlsx')
        else:
            raise Exception('ACCERT output file not found')
        return account_table
