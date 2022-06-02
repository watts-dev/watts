# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
from typing import List, Optional

from uncertainties import ufloat

from .fileutils import PathLike
from .plugin import TemplatePlugin
from .results import Results


class ResultsSerpent(Results):
    """Serpent simulation results

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
    keff
        K-effective value
    stdout
        Standard output from Serpent run
    """


class PluginSerpent(TemplatePlugin):
    """Plugin for running Serpent

    Parameters
    ----------
    template_file
        Templated Serpent input
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

    """

    def __init__(self, template_file: str,
                 extra_inputs: Optional[List[str]] = None,
                 extra_template_inputs: Optional[List[PathLike]] = None,
                 show_stdout: bool = False, show_stderr: bool = False):
        super().__init__(template_file, extra_inputs, extra_template_inputs,
                         show_stdout, show_stderr)
        self._executable = Path('sss2')
        self.input_name = "serpent_input"
        self.unit_system = 'cgs'

    @property
    def execute_command(self):
        return [self.executable, str(self.input_name)]
