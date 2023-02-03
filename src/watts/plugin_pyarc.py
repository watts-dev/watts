# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
import os
import sys
import tempfile
from typing import Mapping, List, Optional

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import PluginGeneric, _find_executable
from .results import Results, ExecInfo


class ResultsPyARC(Results):
    """PyARC simulation results

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
    results_data
        PyARC results

    """

    def __init__(self, params: Parameters, exec_info: ExecInfo,
                 inputs: List[Path], outputs: List[Path], results_data: dict):
        super().__init__(params, exec_info, inputs, outputs)
        self.results_data = results_data


class PluginPyARC(PluginGeneric):
    """Plugin for running PyARC

    Parameters
    ----------
    template_file
        Templated PyARC input
    executable
        Path to PyARC.py script
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
    executable
        Path to PyARC executable

    """

    def __init__(
        self,
        template_file: str,
        executable: PathLike = 'PyARC.py',
        extra_inputs: Optional[List[str]] = None,
        extra_template_inputs: Optional[List[PathLike]] = None,
        show_stdout: bool = False,
        show_stderr: bool = False
    ):
        executable = _find_executable(executable, 'PyARC_DIR')
        super().__init__(executable, None, template_file, extra_inputs,
                         extra_template_inputs, show_stdout, show_stderr)
        self.input_name = "pyarc_input.son"
        self.plugin_name = "PyARC"

    @PluginGeneric.executable.setter
    def executable(self, exe: PathLike):
        if not exe.is_file():
            raise RuntimeError(
                f"{self.plugin_name} module '{exe}' does not exist. The "
                "PyARC_DIR environment variable needs to be set to a directory "
                "containing the PyARC.py module."
            )
        self._executable = Path(exe)

    def run(self, **kwargs: Mapping):
        """Run PyARC

        Parameters
        ----------
        **kwargs
            Keyword arguments passed on to :func:`pyarc.execute`
        """
        sys.path.insert(0, f'{self.executable.parent}')
        import PyARC
        self.pyarc = PyARC.PyARC()
        self.pyarc.user_object.do_run = True
        self.pyarc.user_object.do_postrun = True
        od = Path.cwd()

        with tempfile.TemporaryDirectory() as tmpdir:
            self.pyarc.execute(["-i", self.input_name, "-w", tmpdir, "-o", str(od)], **kwargs)
        sys.path.pop(0)  # Restore sys.path to original state
        os.chdir(od)  # TODO: I don't know why but I keep going to self.executable after execution - this is very wierd!

    def postrun(self, params: Parameters, exec_info: ExecInfo) -> ResultsPyARC:
        """Collect information from PyARC and create results object

        Parameters
        ----------
        params
            Parameters used to create PyARC model
        exec_info
            Execution information

        Returns
        -------
        PyARC results object
        """
        return super().postrun(params, exec_info, results_data=self.pyarc.user_object.results)
