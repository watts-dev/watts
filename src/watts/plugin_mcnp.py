# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import re
from typing import List, Optional

from uncertainties import ufloat

from .data import ATOMIC_SYMBOL, ATOMIC_NUMBER, isotopes
from .fileutils import PathLike
from .plugin import PluginGeneric, _find_executable
from .results import Results


def expand_element(value, default_suffix=None):
    values = value.split()

    # Determine whether filter block includes start of material card
    # TODO: Use regex to break into multiple material blocks?
    if len(values) % 2 == 1:
        mat_num, *values = values
        start = f"{mat_num}    "
    else:
        start = ""

    lines = []
    for zaid_with_suffix, conc in zip(values[::2], values[1::2]):
        # Determine ZAID and suffix used
        zaid, *original_suffix = zaid_with_suffix.split('.')
        if original_suffix and default_suffix is None:
            suffix = original_suffix[0]
        else:
            suffix = default_suffix

        # Determine Z and A
        if zaid.isalpha():
            Z = ATOMIC_NUMBER[zaid]
            A = 0
        else:
            Z, A = divmod(int(zaid), 1000)

        # Split into isotopes if natural element is given
        if A == 0:
            conc = float(conc)
            symbol = ATOMIC_SYMBOL[Z]
            for isotope, fraction in isotopes(symbol):
                iso_A = int(*re.match(rf'{symbol}(\d+)', isotope).groups())
                lines.append(f"{Z}{iso_A:03}.{suffix} {conc * fraction}")
        else:
            lines.append(f"{zaid_with_suffix} {conc}")

    return start + "\n     ".join(lines)


class ResultsMCNP(Results):
    """MCNP simulation results

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
    input_file
        Rendered MCNP input file
    keff
        K-effective value
    stdout
        Standard output from MCNP run
    """

    @property
    def input_file(self) -> str:
        return self.inputs[0].read_text()

    @property
    def keff(self) -> ufloat:
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


class PluginMCNP(PluginGeneric):
    """Plugin for running MCNP

    Parameters
    ----------
    template_file
        Templated MCNP input
    executable
        Path to MCNP executable
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
    execute_command
        List of command-line arguments used to call the executable

    """

    def __init__(
        self,
        template_file: str,
        executable: PathLike = 'mcnp6',
        extra_inputs: Optional[List[str]] = None,
        extra_template_inputs: Optional[List[PathLike]] = None,
        show_stdout: bool = False,
        show_stderr: bool = False
    ):
        executable = _find_executable(executable, 'MCNP_DIR')
        super().__init__(
            executable, ['{self.executable}', 'i={self.input_name}'],
            template_file, extra_inputs, extra_template_inputs, "MCNP",
            show_stdout, show_stderr, unit_system='cgs')
        self.input_name = "mcnp_input"

        # Add custom 'expand_element' Jinja filter
        self.render_template.environment.filters['expand_element'] = expand_element
        for renderer in self.extra_render_templates:
            renderer.environment.filters['expand_element'] = expand_element
