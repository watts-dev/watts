from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
import time
from typing import Callable, Mapping, List

import h5py

from .fileutils import PathLike
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
    stdout
        Standard output from OpenMC run

    Attributes
    ----------
    keff
        K-effective value from the final statepoint
    statepoints
        List of statepoint files
    """

    def __init__(self, params: Parameters, time: datetime,
                 inputs: List[Path], outputs: List[Path], stdout: str):
        super().__init__('OpenMC', params, time, inputs, outputs)
        self.stdout = stdout

    @property
    def statepoints(self) -> List[Path]:
        return [p for p in self.outputs if p.name.startswith('statepoint')]

    @property
    def keff(self):
        import openmc
        # Get k-effective from last statepoint
        last_statepoint = self.statepoints[-1]
        with openmc.StatePoint(last_statepoint) as sp:
            return sp.k_combined

    def save(self, filename: PathLike):
        """Save results to an HDF5 file

        Parameters
        ----------
        filename
            File to save results to
        """
        with h5py.File(filename, 'w') as h5file:
            super()._save(h5file)
            h5file.create_dataset('stdout', data=self.stdout)

    @classmethod
    def _from_hdf5(cls, obj: h5py.Group):
        """Load results from an HDF5 file

        Parameters
        ----------
        obj
            HDF5 group to load results from
        """
        time, parameters, inputs, outputs = Results._load(obj)
        stdout = obj['stdout'][()].decode()
        return cls(parameters, time, inputs, outputs, stdout)


class PluginOpenMC(Plugin):
    """Plugin for running OpenMC

    Parameters
    ----------
    model_builder
        Function that generates an OpenMC model

    """

    def __init__(self, model_builder: Callable[[Parameters], None]):
        self.model_builder = model_builder

    def prerun(self, params: Parameters) -> None:
        """Generate OpenMC input files

        Parameters
        ----------
        params
            Parameters used by the OpenMC template
        """
        self._run_time = time.time_ns()
        self.model_builder(params)

    def run(self, **kwargs: Mapping):
        """Run OpenMC

        Parameters
        ----------
        **kwargs
            Keyword arguments passed on to :func:`openmc.run`
        """
        import openmc
        with redirect_stdout(StringIO()) as output:
            openmc.run(**kwargs)
        self._stdout = output.getvalue()

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

        # Get generated input files
        inputs = files_since('*.xml', self._run_time)

        # Get list of all output files
        outputs = files_since('tallies.out', self._run_time)
        outputs.extend(files_since('source.*.h5', self._run_time))
        outputs.extend(files_since('particle.*.h5', self._run_time))
        outputs.extend(files_since('statepoint.*.h5', self._run_time))

        time = datetime.fromtimestamp(self._run_time * 1e-9)
        return ResultsOpenMC(params, time, inputs, outputs, self._stdout)

