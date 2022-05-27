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
from .results import Results


class ResultsPyARC(Results):
    """PyARC simulation results

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
    results_data
        PyARC results

    """

    def __init__(self, params: Parameters, name: str, time: datetime,
                 inputs: List[Path], outputs: List[Path], results_data: dict):
        super().__init__('PyARC', params, name, time, inputs, outputs)
        self.results_data = results_data

    @property
    def stdout(self) -> str:
        return (self.base_path / "PyARC_log.txt").read_text()


class PluginPyARC(TemplatePlugin):
    """Plugin for running PyARC

    Parameters
    ----------
    template_file
        Templated PyARC input
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when PyARC is run
    show_stderr
        Whether to display output from stderr when PyARC is run

    Attributes
    ----------
    pyarc_exec
        Path to PyARC executable

    """

    def __init__(self, template_file: str,
                 extra_inputs: Optional[List[str]] = None,
                 extra_template_inputs: Optional[List[PathLike]] = None,
                 show_stdout: bool = False, show_stderr: bool = False):
        super().__init__(template_file, extra_inputs, extra_template_inputs,
                         show_stdout, show_stderr)
        self._pyarc_exec = Path(os.environ.get('PyARC_DIR', 'PyARC.py'))
        self.input_name = "pyarc_input.son"

    @property
    def pyarc_exec(self) -> Path:
        return self._pyarc_exec

    @pyarc_exec.setter
    def pyarc_exec(self, exe: PathLike):
        if os.path.exists(exe) is False:
            raise RuntimeError(f"PyARC executable '{exe}' is missing.")
        self._pyarc_exec = Path(exe)

    def prerun(self, params: Parameters) -> None:
        """Generate PyARC input files

        Parameters
        ----------
        params
            Parameters used by the PyARC template
        """
        # Render the template
        # Make a copy of params and convert units if necessary
        # The original params remains unchanged

        params_copy = params.convert_units()
        super().prerun(params_copy, filename=self.input_name)

    def run(self, **kwargs: Mapping):
        """Run PyARC

        Parameters
        ----------
        **kwargs
            Keyword arguments passed on to :func:`pyarc.execute`
        """
        sys.path.insert(0, f'{self._pyarc_exec}')
        import PyARC
        self.pyarc = PyARC.PyARC()
        self.pyarc.user_object.do_run = True
        self.pyarc.user_object.do_postrun = True
        od = Path.cwd()

        with tempfile.TemporaryDirectory() as tmpdir:
            self.pyarc.execute(["-i", self.input_name, "-w", tmpdir, "-o", str(od)], **kwargs)
        sys.path.pop(0)  # Restore sys.path to original state
        os.chdir(od)  # TODO: I don't know why but I keep going to self._pyarc_exec after execution - this is very wierd!

    def postrun(self, params: Parameters, name: str) -> ResultsPyARC:
        """Collect information from PyARC and create results object

        Parameters
        ----------
        params
            Parameters used to create PyARC model
        name
            Name of the workflow

        Returns
        -------
        PyARC results object
        """

        time, inputs, outputs = self._get_result_input(self.input_name)
        return ResultsPyARC(params, name, time, inputs, outputs, self.pyarc.user_object.results)
