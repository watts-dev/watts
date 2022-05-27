# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
from typing import List, Optional

from uncertainties import ufloat

from .fileutils import PathLike
from .plugin import TemplatePlugin
from .results import Results


class ResultsMCNP(Results):
    """MCNP simulation results

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
        Standard output from MCNP run
    """

    @property
    def keff(self):
        with open(self.base_path / 'outp', 'r') as f:
            for line in f:
                if line.strip().startswith('col/abs/trk len'):
                    words = line.split()
                    mean = float(words[2])
                    stdev = float(words[3])
                    return ufloat(mean, stdev)
            else:
                raise ValueError(
                    "Could not determine final k-effective value from MCNP output")


class PluginMCNP(TemplatePlugin):
    """Plugin for running MCNP

    Parameters
    ----------
    template_file
        Templated MCNP input
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when MCNP is run
    show_stderr
        Whether to display output from stderr when MCNP is run

    Attributes
    ----------
    executable
        Path to MCNP executable

    """

    def __init__(self, template_file: str,
                 extra_inputs: Optional[List[str]] = None,
                 extra_template_inputs: Optional[List[PathLike]] = None,
                 show_stdout: bool = False, show_stderr: bool = False):
        super().__init__(template_file, extra_inputs, extra_template_inputs,
                         show_stdout, show_stderr)
        self._executable = Path('mcnp6')
        self.input_name = "mcnp_input"

    @property
    def execute_command(self):
        return [self.executable, f"i={self.input_name}"]
