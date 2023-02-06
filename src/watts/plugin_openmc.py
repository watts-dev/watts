# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from functools import lru_cache
from pathlib import Path
from typing import Callable, Mapping, List, Optional

from uncertainties import ufloat

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import Plugin
from .results import Results, ExecInfo


class ResultsOpenMC(Results):
    """OpenMC simulation results

    Parameters
    ----------
    params
        Parameters used to generate inputs
    exec_info
        Execution information (job ID, plugin name, timestamp, etc.)
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

    def __init__(self, params: Parameters, exec_info: ExecInfo,
                 inputs: List[Path], outputs: List[Path]):
        super().__init__(params, exec_info, inputs, outputs)

    @property
    def statepoints(self) -> List[Path]:
        return [p for p in self.outputs if p.name.startswith('statepoint')]

    @property
    @lru_cache()
    def keff(self) -> ufloat:
        import openmc
        # Get k-effective from last statepoint
        last_statepoint = self.statepoints[-1]
        with openmc.StatePoint(last_statepoint) as sp:
            if hasattr(sp, 'keff'):
                return sp.keff
            else:
                return sp.k_combined

    @property
    @lru_cache()
    def tallies(self) -> List:
        import openmc
        # Get k-effective from last statepoint
        last_statepoint = self.statepoints[-1]
        with openmc.StatePoint(last_statepoint) as sp:
            return list(sp.tallies.values())


class PluginOpenMC(Plugin):
    """Plugin for running OpenMC

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

    def __init__(self, model_builder: Optional[Callable[[Parameters], None]] = None,
                 extra_inputs: Optional[List[PathLike]] = None,
                 show_stdout: bool = False, show_stderr: bool = False):
        super().__init__(extra_inputs, show_stdout, show_stderr)
        self.model_builder = model_builder
        self.unit_system = 'cgs'
        self.plugin_name = 'OpenMC'

    def prerun(self, params: Parameters) -> None:
        """Generate OpenMC input files

        Parameters
        ----------
        params
            Parameters used by the OpenMC template
        """
        # Convert quantities in parameters to CGS system
        params_copy = params.convert_units(system=self.unit_system)

        if self.model_builder is not None:
            self.model_builder(params_copy)

    def run(self, function: Optional[Callable] = None, **kwargs: Mapping):
        """Run OpenMC

        Parameters
        ----------
        function
            Function to execute. If not passed, defaults to only calling
            :func:`openmc.run`.
        **kwargs
            Keyword arguments passed on to ``function``

        See also
        --------
        openmc.run, openmc.plot_geometry, openmc.calculate_volumes

        """
        import openmc
        if function:
            function(**kwargs)
        else:
            openmc.run(**kwargs)

    def postrun(self, params: Parameters, exec_info: ExecInfo) -> ResultsOpenMC:
        """Collect information from OpenMC simulation and create results object

        Parameters
        ----------
        params
            Parameters used to create OpenMC model
        exec_info
            Execution information

        Returns
        -------
        OpenMC results object
        """

        def files_since(pattern, timestamp):
            matches = []
            for p in Path.cwd().glob(pattern):
                # Because of limited time resolution, we rely on access time to
                # determine input files
                mtime = p.stat().st_atime_ns
                if mtime >= timestamp:
                    matches.append(p)
            matches.sort(key=lambda x: x.stat().st_mtime_ns)
            return matches

        # Start with non-templated input files
        inputs = [Path.cwd() / p.name for p in self.extra_inputs]

        # Get generated input files
        for path in files_since('*.xml', exec_info.timestamp):
            if path not in inputs:
                inputs.append(path)

        # Get list of all output files
        outputs = ['OpenMC_log.txt']
        outputs.extend(files_since('tallies.out', exec_info.timestamp))
        outputs.extend(files_since('source.*.h5', exec_info.timestamp))
        outputs.extend(files_since('particle*.h5', exec_info.timestamp))
        outputs.extend(files_since('statepoint.*.h5', exec_info.timestamp))
        outputs.extend(files_since('volume*.h5', exec_info.timestamp))
        outputs.extend(files_since('*.png', exec_info.timestamp))
        outputs.extend(files_since('*.ppm', exec_info.timestamp))

        return ResultsOpenMC(params, exec_info, inputs, outputs)
