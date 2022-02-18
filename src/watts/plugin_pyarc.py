# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from datetime import datetime
from pathlib import Path
import os
import tempfile
import time
from typing import Mapping, List, Optional

import h5py
import sys

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import TemplatePlugin
from .results import Results


class ResultsPyARC(Results):
    """OpenMC simulation results

    Parameters
    ----------
    params
        Parameters used to generate inputs
    time
        Time at which workflow was run
    inputs
        List of input files
    outputs
        List of output files

    Attributes
    ----------

    """

    def __init__(self, params: Parameters, time: datetime,
                 inputs: List[Path], outputs: List[Path], user_object):
        super().__init__('PyARC', params, time, inputs, outputs, user_object)
        self.results_data = self._save_PyARC(user_object)

    @property
    def stdout(self) -> str:
        return (self.base_path / "PyARC_log.txt").read_text()

    def _save_PyARC(self, user_object) -> dict:
        """Return PyARC results in a dictionary

        Returns
        -------
        Results from PyARC results

        """
        results_data = {}
        results_data["mcc3"] = user_object.results_keff_mcc3
        results_data["dif3d"] = user_object.results_keff_dif3d
        results_data["proteus_nodal"] = user_object.results_keff_nodal
        results_data["rzmflx"] = user_object.results_keff_rzmflx
        results_data["persent_pert"] = user_object.results_kpert_persent
        results_data["persent_sens"] = user_object.results_kuq_persent
        results_data["gamsor"] = user_object.results_power_gamsor
        results_data["dassh"] = user_object.results_dassh
        # TODO - this is minimum information that can be brought back easily.
        # More should be returned but will require work on PyARC.
        return results_data

    def save(self, filename: PathLike):
        """Save results to an HDF5 file

        Parameters
        ----------
        filename
            File to save results to
        """
        with h5py.File(filename, 'w') as h5file:
            super()._save(h5file)

    @classmethod
    def _from_hdf5(cls, obj: h5py.Group):
        """Load results from an HDF5 file

        Parameters
        ----------
        obj
            HDF5 group to load results from
        """
        time, parameters, inputs, outputs = Results._load(obj)
        return cls(parameters, time, inputs, outputs)


class PluginPyARC(TemplatePlugin):
    """Plugin for running PyARC

    Parameters
    ----------
    template_file
        Templated PyARC input
    show_stdout
        Whether to display output from stdout when PyARC is run
    show_stderr
        Whether to display output from stderr when PyARC is run
    extra_inputs
        List of extra (non-templated) input files that are needed

    Attributes
    ----------
    pyarc_exec
        Path to PyARC executable

    """

    def  __init__(self, template_file: str, show_stdout: bool = False,
                  show_stderr: bool = False,
                  extra_inputs: Optional[List[str]] = None):
        super().__init__(template_file, extra_inputs)
        self._pyarc_exec = Path(os.environ.get('PyARC_DIR', 'PyARC.py'))
        self.pyarc_inp_name = "pyarc_input.son"
        self.show_stdout = show_stdout
        self.show_stderr = show_stderr

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

        params_copy = super().convert_unit(params, unit_system='si', unit_temperature='K')

        print("Pre-run for PyARC Plugin")
        self._run_time = time.time_ns()
        super().prerun(params_copy, filename=self.pyarc_inp_name)

    def run(self, **kwargs: Mapping):
        """Run PyARC

        Parameters
        ----------
        **kwargs
            Keyword arguments passed on to :func:`pyarc.execute`
        """
        print("Run for PyARC Plugin")
        sys.path.insert(0, f'{self._pyarc_exec}')
        import PyARC
        self.pyarc = PyARC.PyARC()
        self.pyarc.user_object.do_run = True
        self.pyarc.user_object.do_postrun = True
        od = Path.cwd()

        with tempfile.TemporaryDirectory() as tmpdir:
            self.pyarc.execute(["-i", self.pyarc_inp_name, "-w", tmpdir, "-o", str(od)], **kwargs)
        sys.path.pop(0)  # Restore sys.path to original state
        os.chdir(od) # TODO: I don't know why but I keep going to self._pyarc_exec after execution - this is very wierd!

    def postrun(self, params: Parameters) -> ResultsPyARC:
        """Collect information from PyARC and create results object

        Parameters
        ----------
        params
            Parameters used to create PyARC model

        Returns
        -------
        PyARC results object
        """
        print("Post-run for PyARC Plugin")

        time = datetime.fromtimestamp(self._run_time * 1e-9)
        inputs = [p.name for p in self.extra_inputs]
        inputs.append(self.pyarc_inp_name)
        outputs = [p for p in Path.cwd().iterdir() if p.name not in inputs]
        return ResultsPyARC(params, time, inputs, outputs, self.pyarc.user_object)

