# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from datetime import datetime
from pathlib import Path
import os
import sys
from typing import List, Optional

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import PluginGeneric, _find_executable
from .results import Results


class PluginABCE(PluginGeneric):
    """Plugin for running ABCE

    Parameters
    ----------
    template_file
        Templated ABCE input
    executable
        Path to ABCE run.py script
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when ABCE is run
    show_stderr
        Whether to display output from stderr when ABCE is run

    Attributes
    ----------
    executable
        Path to ABCE executable
    execute_command
        List of command-line arguments used to call the executable

    """


    def __init__(
        self,
        template_file: str,
        executable: PathLike = 'run.py',
        extra_inputs: Optional[List[str]] = None,
        extra_template_inputs: Optional[List[PathLike]] = None,
        show_stdout: bool = False,
        show_stderr: bool = False
    ):
        executable = _find_executable(executable, 'ABCE_DIR')
        execute_command = [sys.executable, '{self.executable}', '--settings_file', '{self.input_name}']
        super().__init__(
            executable, execute_command, template_file, extra_inputs,
            extra_template_inputs, show_stdout, show_stderr)
        self.input_name = 'settings.yml'


class ResultsABCE(Results):
    """ABCE simulation results

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
        Standard output from ABCE run
    """
    def __init__(self, params: Parameters, name: str, time: datetime,
                 inputs: List[PathLike], outputs: List[PathLike]):
        super().__init__(params, name, time, inputs, outputs)
