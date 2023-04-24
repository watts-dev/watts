# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
import sys
from typing import List, Optional

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import PluginGeneric, _find_executable
from .results import Results, ExecInfo


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
            extra_template_inputs, 'ABCE', show_stdout, show_stderr)
        self.input_name = 'settings.yml'

    @PluginGeneric.executable.setter
    def executable(self, exe: PathLike):
        if not exe.is_file():
            raise RuntimeError(
                f"{self.plugin_name} script '{exe}' does not exist. The "
                "ABCE_DIR environment variable needs to be set to a directory "
                "containing the run.py script."
            )
        self._executable = Path(exe)


class ResultsABCE(Results):
    """ABCE simulation results

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
        Standard output from ABCE run
    """
    def __init__(self, params: Parameters, exec_info: ExecInfo,
                 inputs: List[PathLike], outputs: List[PathLike]):
        super().__init__(params, exec_info, inputs, outputs)
