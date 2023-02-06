# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
import sys
from typing import List, Optional

import pandas as pd

from .fileutils import PathLike
from .plugin import PluginGeneric, _find_executable
from .results import Results


class PluginACCERT(PluginGeneric):
    """Plugin for running ACCERT

    Parameters
    ----------
    template_file
        Templated ACCERT input
    executable
        Path to ACCERT Main.py script
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
        execute_command = [sys.executable, '{self.executable}', '-i', '{self.input_name}']
        super().__init__(executable, execute_command, template_file, extra_inputs,
                         extra_template_inputs, show_stdout, show_stderr)
        self.input_name = "ACCERT_input.son"
        self.plugin_name = "ACCERT"

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
    exec_info
        Execution information (job ID, plugin name, time, etc.)
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

    @property
    def total_cost(self) -> float:
        return self.account_table['total_cost'].values[0]

    @property
    def account_table(self) -> pd.DataFrame:
        account_file = self.base_path / 'ACCERT_updated_account.xlsx'
        if Path(account_file).exists():
            return pd.read_excel(account_file)
        else:
            raise FileNotFoundError('ACCERT output file not found')
