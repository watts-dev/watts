# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import time
from typing import Callable, Mapping, List, Optional

import h5py

from .fileutils import PathLike, tee_stdout, tee_stderr
from .parameters import Parameters
from .plugin import Plugin
from .results import Results


class ResultsOpenMC(Results):
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
    keff
        K-effective value from the final statepoint
    statepoints
        List of statepoint files
    stdout
        Standard output from OpenMC run
    tallies
        List of OpenMC tally objects
    """

    def __init__(self, params: Parameters, time: datetime,
                 inputs: List[Path], outputs: List[Path]):
        super().__init__('OpenMC', params, time, inputs, outputs)

    @property
    def statepoints(self) -> List[Path]:
        return [p for p in self.outputs if p.name.startswith('statepoint')]

    @property
    @lru_cache()
    def keff(self):
        import openmc
        # Get k-effective from last statepoint
        last_statepoint = self.statepoints[-1]
        with openmc.StatePoint(last_statepoint) as sp:
            return sp.k_combined

    @property
    @lru_cache()
    def tallies(self) -> List:
        import openmc
        # Get k-effective from last statepoint
        last_statepoint = self.statepoints[-1]
        with openmc.StatePoint(last_statepoint) as sp:
            return list(sp.tallies.values())

    @property
    def stdout(self) -> str:
        return (self.base_path / "OpenMC_log.txt").read_text()

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


class PluginOpenMC(Plugin):
    """Plugin for running OpenMC

    Parameters
    ----------
    model_builder
        Function that generates an OpenMC model
    supp_inputs
        Supplemental input files
    show_stdout
        Whether to display output from stdout when OpenMC is run
    show_stderr
        Whether to display output from stderr when OpenMC is run

    """

    def __init__(self, model_builder: Optional[Callable[[Parameters], None]] = None,
                 supp_inputs: Optional[List[PathLike]] = None,
                 show_stdout: bool = False, show_stderr: bool = False):
        super().__init__(supp_inputs)
        self.model_builder = model_builder
        self.show_stdout = show_stdout
        self.show_stderr = show_stderr

    def prerun(self, params: Parameters) -> None:
        """Generate OpenMC input files

        Parameters
        ----------
        params
            Parameters used by the OpenMC template
        """
        # Make a copy of params and convert units if necessary
        # The original params remains unchanged

        params_copy = super().convert_unit(params, unit_system='cgs', unit_temperature='K')

        print("Pre-run for OpenMC Plugin")
        self._run_time = time.time_ns()
        if self.model_builder is not None:
            self.model_builder(params_copy)

    def run(self, **kwargs: Mapping):
        """Run OpenMC

        Parameters
        ----------
        **kwargs
            Keyword arguments passed on to :func:`openmc.run`
        """
        print("Run for OpenMC Plugin")
        import openmc
        with open('OpenMC_log.txt', 'w') as f:
            func_stdout = tee_stdout if self.show_stdout else redirect_stdout
            func_stderr = tee_stderr if self.show_stderr else redirect_stderr
            with func_stdout(f), func_stderr(f):
                openmc.run(**kwargs)

    def postrun(self, params: Parameters) -> ResultsOpenMC:
        """Collect information from OpenMC simulation and create results object

        Parameters
        ----------
        params
            Parameters used to create OpenMC model

        Returns
        -------
        OpenMC results object
        """
        print("Post-run for OpenMC Plugin")

        def files_since(pattern, time):
            matches = []
            for p in Path.cwd().glob(pattern):
                # Because of limited time resolution, we rely on access time to
                # determine input files
                mtime = p.stat().st_atime_ns
                if mtime >= time:
                    matches.append(p)
            matches.sort(key=lambda x: x.stat().st_mtime_ns)
            return matches

        # Start with non-templated input files
        inputs = [Path.cwd() / p.name for p in self.supp_inputs]

        # Get generated input files
        for path in files_since('*.xml', self._run_time):
            if path not in inputs:
                inputs.append(path)

        # Get list of all output files
        outputs = ['OpenMC_log.txt']
        outputs.extend(files_since('tallies.out', self._run_time))
        outputs.extend(files_since('source.*.h5', self._run_time))
        outputs.extend(files_since('particle.*.h5', self._run_time))
        outputs.extend(files_since('statepoint.*.h5', self._run_time))

        time = datetime.fromtimestamp(self._run_time * 1e-9)
        return ResultsOpenMC(params, time, inputs, outputs)
