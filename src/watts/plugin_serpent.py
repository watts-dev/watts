# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from typing import List, Optional

from .fileutils import PathLike
from .plugin import PluginGeneric, _find_executable
from .results import Results


class ResultsSerpent(Results):
    """Serpent simulation results

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
        Standard output from Serpent run
    """


class PluginSerpent(PluginGeneric):
    """Plugin for running Serpent

    Parameters
    ----------
    template_file
        Templated Serpent input
    executable
        Path to Serpent executable
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when Serpent is run
    show_stderr
        Whether to display output from stderr when Serpent is run

    Attributes
    ----------
    executable
        Path to Serpent executable
    execute_command
        List of command-line arguments used to call the executable

    """

    def __init__(
        self,
        template_file: str,
        executable: PathLike = 'sss2',
        extra_inputs: Optional[List[str]] = None,
        extra_template_inputs: Optional[List[PathLike]] = None,
        show_stdout: bool = False,
        show_stderr: bool = False
    ):
        executable = _find_executable(executable, 'SERPENT_DIR')
        super().__init__(
            executable, ['{self.executable}', '{self.input_name}'],
            template_file, extra_inputs, extra_template_inputs, "Serpent",
            show_stdout, show_stderr, unit_system='cgs'
        )
        self.input_name = "serpent_input"
