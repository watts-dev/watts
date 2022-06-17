# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from datetime import datetime
from pathlib import Path
import os
import sys
import tempfile
from typing import Mapping, List, Optional

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import TemplatePlugin
from .plugin import Plugin
from .results import Results


class PluginABCE(Plugin):
    """Plugin for running Agent Based Capacity Expansion (ABCE)

    Parameters
    ----------
    model_builder
        Function that generates an OpenMC model
    extra_inputs
        Extra (non-templated) input files
    show_stdout
        Whether to display output from stdout when OpenMC is run
    show_stderr
        Whether to display output from stderr when OpenMC is run

    """