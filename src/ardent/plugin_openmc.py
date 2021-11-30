from pathlib import Path
import time
from typing import Callable, Mapping

from .model import Parameters
from .plugin import Plugin


class PluginOpenMC(Plugin):
    """Plugin for running OpenMC

    Parameters
    ----------
    model_builder
        Function that generates an OpenMC model

    """

    def __init__(self, model_builder: Callable[[Parameters], None]):
        self.model_builder = model_builder

    def prerun(self, model: Parameters) -> None:
        """Generate OpenMC input files

        Parameters
        ----------
        model
            Model that is used by the OpenMC template
        """
        self.model_builder(model)

    def run(self, **kwargs: Mapping):
        """Run OpenMC

        Parameters
        ----------
        **kwargs
            Keyword arguments passed on to :func:`openmc.run`
        """
        import openmc
        self._run_time = time.time()
        openmc.run(**kwargs)

    def postrun(self, model: Parameters):
        """Collect information from OpenMC simulation and store in model

        Parameters
        ----------
        model
            Model to store simulation results in
        """
        import openmc
        # Determine most recent statepoint
        tstart = self._run_time
        last_statepoint = None
        for sp in Path.cwd().glob('statepoint.*.h5'):
            mtime = sp.stat().st_mtime
            if mtime >= tstart:
                tstart = mtime
                last_statepoint = sp

        # Make sure statepoint was found
        if last_statepoint is None:
            raise RuntimeError("Couldn't find statepoint resulting from OpenMC simulation")

        # Get k-effective and set it on model
        with openmc.StatePoint(last_statepoint) as sp:
            keff = sp.k_combined
        results = {
            'keff': keff.nominal_value,
            'keff_stdev': keff.std_dev
        }
        model.set('openmc_results', results, user='plugin_openmc')
