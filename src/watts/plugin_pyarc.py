# SPDX-FileCopyrightText: 2022-2025 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
import os
import pickle
import tempfile
from typing import List, Optional

from .fileutils import PathLike, run as run_proc
from .parameters import Parameters
from .plugin import PluginGeneric, _find_executable
from .results import Results, ExecInfo


# Python snippet executed in PyARC's own environment (through entry.sh). It
# runs PyARC and pickles the results dictionary, which is otherwise only
# available in memory, so that WATTS can load it afterwards.
_PYARC_SCRIPT = """
import pickle, sys, tempfile
pyarc_dir, input_file, output_dir, results_file = sys.argv[1:5]
sys.path.insert(0, pyarc_dir)
import PyARC
pyarc = PyARC.PyARC()
pyarc.user_object.do_run = True
pyarc.user_object.do_postrun = True
with tempfile.TemporaryDirectory() as tmpdir:
    pyarc.execute(["-i", input_file, "-w", tmpdir, "-o", output_dir])
with open(results_file, "wb") as fh:
    pickle.dump(pyarc.user_object.results, fh)
"""


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
    """Plugin for running PyARC (version 4.0.0 or later)

    PyARC is run in its own Python environment through the ``entry.sh``
    script that is shipped next to ``PyARC.sh``.

    Parameters
    ----------
    template_file
        Templated PyARC input
    executable
        Path to PyARC.sh script
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
        executable: PathLike = 'PyARC.sh',
        extra_inputs: Optional[List[str]] = None,
        extra_template_inputs: Optional[List[PathLike]] = None,
        show_stdout: bool = False,
        show_stderr: bool = False
    ):
        executable = _find_executable(executable, 'PyARC_DIR')
        super().__init__(executable, None, template_file, extra_inputs,
                         extra_template_inputs, "PyARC", show_stdout, show_stderr)
        self.input_name = "pyarc_input.son"

    @PluginGeneric.executable.setter
    def executable(self, exe: PathLike):
        if not exe.is_file():
            raise RuntimeError(
                f"{self.plugin_name} script '{exe}' does not exist. The "
                "PyARC_DIR environment variable needs to be set to a directory "
                "containing the PyARC.sh script (PyARC 4.0.0 or later)."
            )
        self._executable = Path(exe)

    def run(self):
        """Run PyARC"""
        pyarc_dir = self.executable.resolve().parent
        cwd = Path.cwd()

        # Results file is written outside of the execution directory so that
        # it is not collected as a PyARC output
        fd, results_file = tempfile.mkstemp(suffix='.pkl')
        os.close(fd)
        os.remove(results_file)
        try:
            run_proc(['bash', str(pyarc_dir / 'entry.sh'), '-c', _PYARC_SCRIPT,
                      str(pyarc_dir), str(cwd / self.input_name), str(cwd),
                      results_file])
            if not os.path.isfile(results_file):
                raise RuntimeError(
                    f"PyARC did not complete successfully. See "
                    f"{self.plugin_name}_log.txt for details.")
            with open(results_file, 'rb') as fh:
                self._results_data = pickle.load(fh)
        finally:
            if os.path.isfile(results_file):
                os.remove(results_file)

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
        return super().postrun(params, exec_info, results_data=self._results_data)
