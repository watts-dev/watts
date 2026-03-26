# SPDX-FileCopyrightText: 2024 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
from typing import List, Optional
import sys
import json
import numpy as np
import h5py

from .plugin import PluginGeneric, _find_executable
from .results import Results, ExecInfo
from .fileutils import PathLike
from .parameters import Parameters
from .enrichment_utils import enrichment_cascade

SECONDS_PER_YEAR = 365.25 * 24 * 3600


def _default_dymond_executable():
    """Return the platform-appropriate DYMOND launcher script name."""
    if sys.platform == "win32":
        return "DYMOND_windows.bat"
    elif sys.platform == "darwin":
        return "DYMOND_mac"
    else:
        return "DYMOND_linux.sh"


class ResultsDYMOND(Results):
    """DYMOND simulation results

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
    stocks
        Dictionary of cumulative material stored in the model at each time
        point by agent type and material type
    flows
        Dictionary of material that has entered an agent between each time
        point by agent type and material type
    operations
        Dictionary of facility operational data (e.g., power produced or
        material throughput)

    stdout
        standard output from a DYMOND run
    """

    def __init__(
        self,
        params: Parameters,
        exec_info: ExecInfo,
        inputs: List[Path],
        outputs: List[Path],
    ):
        super().__init__(params, exec_info, inputs, outputs)

        self.obj = self.get_object()

    @property
    def hdf5_file(self) -> Path:
        """Returns the path to the output HDF5 file from the simulation."""
        path_list = [
            p for p in self.outputs if p.suffix in (".h5", ".hdf5")]
        assert len(path_list) == 1, \
            f"Expected 1 HDF5 file, found {len(path_list)}"
        return path_list[0]

    def get_object(self):
        return DYMONDOutput(self.hdf5_file)


class PluginDYMOND(PluginGeneric):
    """Plugin for running DYMOND simulations

    Parameters
    ----------
    template_file
        Templated DYMOND input
    executable
        Path to DYMOND bash/shell script
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when DYMOND is run
    show_stderr
        Whether to display output from stderr when DYMOND is run

    Attributes
    ----------
    executable
        Path to DYMOND executable
    execute_command
        List of command-line arguments to call the executable
    """

    def __init__(
        self,
        template_file: PathLike,
        executable: PathLike = None,
        extra_inputs: Optional[List[str]] = None,
        extra_template_inputs: Optional[List[PathLike]] = None,
        show_stdout: bool = False,
        show_stderr: bool = False,
    ):

        if executable is None:
            executable = _default_dymond_executable()
        executable = _find_executable(executable, "DYMOND_DIR")
        execute_command = ["{self.executable}", "{self.input_name}"]

        super().__init__(
            executable,
            execute_command,
            template_file,
            extra_inputs,
            extra_template_inputs,
            "DYMOND",
            show_stdout,
            show_stderr,
        )

        self.input_name = "DYMOND_input.json"

    @PluginGeneric.executable.setter
    def executable(self, exe: PathLike):
        if not exe.is_file():
            raise RuntimeError(
                f"{self.plugin_name} module '{exe}' does not exist."
                f" The DYMOND_DIR environment variable needs to be "
                f" set to a directory containing the DYMOND scripts"
                f" and model modules."
            )
        self._executable = Path(exe)


class DYMONDOutput:
    def __init__(self, hdf5_path):
        """
        Access and organize DYMOND simulation output data from an HDF5 file.

        Parameters
        ----------
        hdf5_path : str or pathlib.Path
            Path to the DYMOND HDF5 output file containing the OUTPUT group
            with stocks, flows, and operations data tables.
        """
        self.hdf5_path = Path(hdf5_path)
        assert self.hdf5_path.is_file(), \
            f"HDF5 file {self.hdf5_path} does not exist."

        with h5py.File(self.hdf5_path, 'r') as f:
            assert 'OUTPUT' in f, \
                f"HDF5 file {self.hdf5_path} does not contain an OUTPUT group."

            # Read input JSON embedded in the OUTPUT group
            input_raw = f['OUTPUT/input'][()]
            if isinstance(input_raw, bytes):
                input_raw = input_raw.decode('utf-8')
            elif isinstance(input_raw, np.ndarray):
                input_raw = str(input_raw.flat[0])
                if isinstance(input_raw, bytes):
                    input_raw = input_raw.decode('utf-8')
            self.input_data = json.loads(input_raw)

            # Read stocks, flows, operations as nested dicts
            output_grp = f['OUTPUT']
            self.stocks = self._read_group(output_grp['stocks']) \
                if 'stocks' in output_grp else {}
            self.flows = self._read_group(output_grp['flows']) \
                if 'flows' in output_grp else {}
            self.operations = self._read_group(output_grp['operations']) \
                if 'operations' in output_grp else {}

        # Store times
        td = self.get_times()
        for k, v in td.items():
            setattr(self, k, v)

        # Extract type names and reactor specs from input data
        self.type_names = self._get_type_names()
        self.reactor_types = self.type_names["reactor"]
        self.reprocessing_types = self.type_names["reprocessing"]
        self.storage_types = self.type_names["storage"]
        self.enrichment_types = self.type_names["enrichment"]
        self.fabrication_types = self.type_names["fabrication"]
        self.facility_types = self.type_names["facility"]
        self.reactor_data = self._get_reactor_data()

# ===================General Use Interface====================================

    def get_input_dict(self) -> dict:
        """
        Returns the DYMOND input as a dictionary, read from the
        OUTPUT/input dataset in the HDF5 output file.

        Returns
        -------
        dict
            The parsed JSON input data.
        """
        return self.input_data

    def get_facility_agents(self, facility_class=None):
        """
        Get agents from the HDF5 output file, organized by facility class
        and facility type.

        Parameters
        ----------
        facility_class : str or list of str or None
            Facility class(es) to query (e.g., 'Reactor', 'Storage').
            If None, returns agents from all facility classes.

        Returns
        -------
        dict[str, dict[str, list[str]]]
            Nested dict: {facility_class: {facility_type: [agent_names]}}.
        """
        if facility_class is None:
            facility_class = ['Reactor', 'Reprocessing', 'Facility',
                              'Storage', 'Fabrication', 'Enrichment']
        elif isinstance(facility_class, str):
            facility_class = [facility_class]

        result = {}
        with h5py.File(self.hdf5_path, 'r') as f:
            for fc in facility_class:
                if fc not in f:
                    continue
                result[fc] = {}
                for ftype in f[fc]:
                    if isinstance(f[fc][ftype], h5py.Group):
                        result[fc][ftype] = list(f[fc][ftype].keys())
        return result

    def get_proto_ids(self, facility_type, facility_class=None):
        """
        Get agent names for a given facility type.

        In DYMOND, agents are identified by name strings rather than
        integer IDs. This returns the list of agent names belonging
        to a facility type.

        Parameters
        ----------
        facility_type : str
            The facility type name (e.g., 'PWR', 'waste').
        facility_class : str or None
            The facility class (e.g., 'Reactor', 'Storage'). If None,
            searches all facility classes for the given type.

        Returns
        -------
        list[str]
            List of agent names under the facility type.
        """
        agents = self.get_facility_agents(facility_class)
        for fc, types in agents.items():
            if facility_type in types:
                return types[facility_type]
        raise ValueError(
            f"Facility type '{facility_type}' not found in output data.")

    def get_nucids(self):
        """
        Returns the nuclide ID strings from the OUTPUT/nuclide_ids
        dataset. These correspond to the columns of the per-agent
        composition arrays.

        Returns
        -------
        list[str]
            List of nuclide ID strings (e.g., ['u238', 'pu239', ...]).
        """
        with h5py.File(self.hdf5_path, 'r') as f:
            if 'OUTPUT/nuclide_ids' not in f:
                raise ValueError(
                    "nuclide_ids not found in OUTPUT group. "
                    "This may require a newer version of DYMOND.")
            nids = f['OUTPUT/nuclide_ids'][()]
        return [n.decode('utf-8') if isinstance(n, bytes) else str(n)
                for n in nids]

    def get_times(self) -> dict:
        """
        Gets different time-related data from a simulation.

        The model time unit must be ``"YEARS"``.

        Returns
        -------
        dict
            ``{'init_year': int, 'init_month': int,
            'duration': int, 'years': np.ndarray, 'years_int': np.ndarray}``
        """
        time_unit = (
            self.input_data
            .get("Model", self.input_data.get("model", {}))
            .get("units", {})
            .get("time", "YEARS")
            .upper()
        )
        assert time_unit == "YEARS", \
            f"get_times requires model time unit 'YEARS', got '{time_unit}'."

        sim = self.input_data.get(
            "Simulation", self.input_data.get("simulation", {}))
        start_year = sim["start year"]
        duration = sim["duration"]

        times = self._get_times_array()
        years = times + start_year

        return {
            "init_year": start_year,
            "init_month": 0,
            "duration": duration,
            "years": years,
            "years_int": np.arange(start_year, start_year + duration + 1),
        }

    def get_capacity_factors(self, facilities=None, facility_class="reactor"):
        """
        Get capacity factors for facilities of a given class from input data.

        Parameters
        ----------
        facilities : list of str or None
            Facility names. If None, uses all facilities of the given class.
        facility_class : str, optional
            Facility class to query (e.g., ``"reactor"``, ``"fabrication"``).
            Defaults to ``"reactor"``.

        Returns
        -------
        dict[str, float]
            Mapping of facility name to capacity factor. Returns ``nan`` if
            the capacity factor is not specified in the input data.
        """
        type_data = self._get_type_data(facility_class)
        facilities = self._normalize_facilities(
            facilities=facilities,
            facility_class=facility_class
        )
        return {
            fac: type_data[fac].get("capacity factor", np.nan)
            for fac in facilities
        }

    def get_capacities(self, facilities=None, facility_class="reactor"):
        """
        Get unit capacity for facilities of a given class from input data.

        Parameters
        ----------
        facilities : list of str or None
            Facility names. If None, uses all facilities of the given class.
        facility_class : str, optional
            Facility class to query (e.g., ``"reactor"``, ``"fabrication"``).
            Defaults to ``"reactor"``.

        Returns
        -------
        dict[str, float]
            Mapping of facility name to unit capacity (or rated power for
            reactors). Returns ``nan`` if not specified in the input data.
        """
        type_data = self._get_type_data(facility_class)
        facilities = self._normalize_facilities(
            facilities=facilities,
            facility_class=facility_class
        )
        capacity_key = "power" if facility_class == "reactor" else "capacity"
        return {
            fac: type_data[fac].get(capacity_key, np.nan)
            for fac in facilities
        }

    def get_generated_power(
        self, reactors=None, return_sum=True
    ) -> dict[str, np.ndarray] | np.ndarray:
        """
        Returns the generated power for each time step for each reactor type.

        Extracts the ``"Operating"`` state output summary directly from
        operations data.

        Parameters
        ----------
        reactors : list of str or None
            Names of reactors in the simulation. If None, uses all reactors.
        return_sum : bool, optional
            If True, returns a single array summed over all reactors.
            If False, returns a dict of per-reactor arrays. Default True.

        Returns
        -------
        power_dict : dict[str, np.ndarray] or np.ndarray
            Generated power per reactor (dict) or summed across all reactors
            (ndarray) depending on ``return_sum``.
        """
        reactors = self._normalize_facilities(
            facilities=reactors,
            facility_class="reactor"
        )

        ops_reactor = self.operations.get("reactor", {})
        times = self._get_times_array()

        power_dict = {}
        for reactor in reactors:
            if reactor not in ops_reactor:
                raise ValueError(
                    f"Reactor '{reactor}' not found in operations data.")
            power_dict[reactor] = np.asarray(ops_reactor[reactor].get(
                "Operating", np.zeros_like(times)))

        if return_sum:
            return np.sum(list(power_dict.values()), axis=0)
        return power_dict

    def get_deployed_capacity(
        self, facilities=None, facility_class="reactor", return_sum=True,
    ) -> dict[str, np.ndarray] | np.ndarray:
        """
        Determines the deployed capacity for each time step for each
        facility type, using the Deployments block in the input data.

        Active units at each time step are taken from
        ``get_facility_fleet_size``.
        Deployed capacity equals the number of active units multiplied by
        rated capacity (from the Types block).

        Parameters
        ----------
        facilities : list of str or None
            Names of facilities in the simulation. If None, uses all
            facilities of the given ``facility_class``.
        facility_class : str, optional
            Facility class to query (e.g., ``"reactor"``, ``"fabrication"``).
            Defaults to ``"reactor"``.
        return_sum : bool, optional
            If True, returns a single array summed over all facilities.
            If False, returns a dict of per-facility arrays. Default True.

        Returns
        -------
        capacity_dict : dict[str, np.ndarray] or np.ndarray
            Deployed capacity in GW per facility (dict) or summed across all
            facilities (ndarray) depending on ``return_sum``.
        """
        facilities = self._normalize_facilities(
            facilities=facilities,
            facility_class=facility_class
        )

        type_data = self._get_type_data(facility_class)
        power_units = (
            self.input_data
            .get("Model", self.input_data.get("model", {}))
            .get("units", {})
            .get("power", "MW")
            .upper()
        )

        power_to_gw = {
            "W": 1e-9,
            "MW": 1e-3,
            "GW": 1.0,
            "EJ/YR": 1e18 / (SECONDS_PER_YEAR * 1e9),
            "TWH/YR": 1e12 / (8766 * 1e9),
        }
        to_gw = power_to_gw[power_units]

        capacity_dict = {}
        for fac in facilities:
            fac_info = type_data.get(fac, {})
            rated_capacity = fac_info.get(
                "capacity", fac_info.get("power", 0.0))
            rated_capacity_gw = rated_capacity * to_gw

            fleet = self.get_facility_fleet_size(fac, facility_class)
            capacity_dict[fac] = fleet * rated_capacity_gw

        if return_sum:
            return np.sum(list(capacity_dict.values()), axis=0)
        return capacity_dict

    def get_fuel_mass_and_enrichment(
        self,
        reactors: str | list[str] | None = None,
        return_sum: bool = True
    ) -> tuple[np.ndarray | dict[str, np.ndarray], dict[str, np.ndarray]]:
        fuel_mass = self.stock_fuel_demand(reactors, return_sum=return_sum)
        enrichment = self.get_enrichments(reactors)
        return fuel_mass, enrichment

    def get_enrichments(
        self, reactors: str | list[str] | None = None
    ) -> dict[str, np.ndarray]:
        """
        Annual mass-weighted U-235 enrichment for fuel received by reactors,
        computed from per-transaction composition data in the HDF5 output file.

        For each time step, enrichment is the ratio of U-235 mass to total
        uranium mass summed over all incoming transactions in that year.
        Steps with no uranium input return 0.0.

        Parameters
        ----------
        reactors : str or list of str or None
            Name(s) of the reactor types to analyze. If None, uses all
            reactor types.

        Returns
        -------
        enrichments : dict[str, np.ndarray]
            Annual enrichment time series (U-235 mass fraction) for each
            reactor type. Array length equals the number of simulation time
            steps.
        """
        reactors = self._normalize_facilities(
            facilities=reactors,
            facility_class="reactor"
        )

        n_steps = len(self._get_times_array())

        enrichments = {}
        with h5py.File(self.hdf5_path, 'r') as f:
            # Build nuclide index lookup
            nuclide_ids = [
                nid.decode() if isinstance(nid, bytes) else nid
                for nid in f['OUTPUT/nuclide_ids'][()]
            ]
            nuclide_index = {name: i for i, name in enumerate(nuclide_ids)}
            u235_idx = nuclide_index.get('u235')
            u_idxs = [i for name, i in nuclide_index.items()
                      if name.startswith('u')]

            for reactor in reactors:
                reactor_group_path = f'Reactor/{reactor}'
                if reactor_group_path not in f:
                    print(
                        f"Warning: Reactor group '{reactor_group_path}' not "
                        f"found in HDF5. Returning zeros."
                    )
                    enrichments[reactor] = np.zeros(n_steps)
                    continue

                total_u235 = np.zeros(n_steps)
                total_u = np.zeros(n_steps)

                for instance in f[reactor_group_path].values():
                    proc = instance.get('process')
                    if proc is None:
                        continue
                    times_raw = proc['times'][()]
                    masses = proc['masses'][()]
                    compositions = proc['compositions'][()]

                    incoming = masses > 0
                    if not np.any(incoming):
                        continue

                    times_in = times_raw[incoming]
                    masses_in = masses[incoming]
                    comps_in = compositions[incoming]

                    idxs = (times_in / SECONDS_PER_YEAR).astype(int)

                    for i, (idx, mass, comp) in enumerate(
                            zip(idxs, masses_in, comps_in)):
                        if idx < 0 or idx >= n_steps:
                            continue
                        if u235_idx is not None:
                            total_u235[idx] += comp[u235_idx] * mass
                        total_u[idx] += comp[u_idxs].sum() * mass

                with np.errstate(invalid='ignore', divide='ignore'):
                    enr = np.where(total_u > 0, total_u235 / total_u, 0.0)
                enrichments[reactor] = enr

        return enrichments

    def reprocessed_mass(
        self,
        reprocess_plants: str | list[str] | None = None,
        return_sum: bool = True,
        config_name: str | None = None
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Retrieves the total reprocessing utilization data from flows output.

        Parameters
        ----------
        reprocess_plants : str or list of str or None
            Reprocessing plant type name(s). If None, uses all reprocessing
            plants.
        return_sum : bool, optional
            If True, returns a single array summed over all plants.
            Default True.
        config_name : str or None, optional
            Flows config name. If None, uses the first available.

        Returns
        -------
        reprocessed : np.ndarray or dict[str, np.ndarray]
            The annual reprocessing mass per plant (dict) or summed
            (ndarray) depending on ``return_sum``.
        """
        reprocess_plants = self._normalize_facilities(
            facilities=reprocess_plants,
            facility_class="reprocessing"
        )

        reprocessed_mass_dict = {}
        for plant in reprocess_plants:
            outgoing = self._get_flow(
                plant, "reprocessing", "process", "outgoing", config_name)
            if outgoing is None:
                outgoing = np.zeros_like(self._get_times_array())
            reprocessed_mass_dict[plant] = outgoing

        if return_sum:
            return np.sum(list(reprocessed_mass_dict.values()), axis=0)
        return reprocessed_mass_dict

    def aggregate_flows(self, facilities, facility_class, default_list,
                        location, direction, return_sum, config_name):
        """Common loop: iterate facilities, call _get_flow, optionally sum.

        Parameters
        ----------
        facilities : str, list of str, or None
            Facility type names. If None, uses default_list.
        facility_class : str
            Facility class name.
        default_list : list of str
            Default list of facility names when facilities is None.
        location : str or None
            Process stage category, or None to sum all.
        direction : str
            'incoming' or 'outgoing'.
        return_sum : bool
            If True, sum across all facilities.
        config_name : str or None
            Flows config name.

        Returns
        -------
        np.ndarray or dict[str, np.ndarray]
        """
        facilities = self._normalize_facilities(
            facilities=facilities,
            default_list=default_list
        )

        result = {}
        for fac in facilities:
            flow = self._get_flow(fac, facility_class, location, direction,
                                  config_name)
            if flow is None:
                flow = np.zeros_like(self._get_times_array())
            result[fac] = flow

        if return_sum:
            return np.sum(list(result.values()), axis=0)
        return result

    def flow_reactor(self, reactors=None, location=None, direction="incoming",
                     return_sum=True, config_name=None):
        """Get flow data for reactor facility types.
        """
        return self.aggregate_flows(reactors, "reactor", self.reactor_types,
                                    location, direction, return_sum,
                                    config_name)

    def flow_storage(self, storages=None, location="facility",
                     direction="incoming", return_sum=True, config_name=None):
        """Get flow data for storage facility types.
        """
        return self.aggregate_flows(storages, "storage", self.storage_types,
                                    location, direction, return_sum,
                                    config_name)

    def flow_enrichment(self, enrichments=None, location=None,
                        direction="incoming", return_sum=True,
                        config_name=None):
        """Get flow data for enrichment facility types.
        """
        return self.aggregate_flows(enrichments, "enrichment",
                                    self.enrichment_types, location,
                                    direction, return_sum, config_name)

    def flow_fabrication(self, fabrications=None, location=None,
                         direction="incoming", return_sum=True,
                         config_name=None):
        """Get flow data for fabrication facility types.
        """
        return self.aggregate_flows(fabrications, "fabrication",
                                    self.fabrication_types, location,
                                    direction, return_sum, config_name)

    def flow_reprocessing(self, facility=None, location=None,
                          direction="incoming", return_sum=True,
                          config_name=None):
        """Get flow data for reprocessing facility types.
        """
        return self.aggregate_flows(facility, "reprocessing",
                                    self.reprocessing_types, location,
                                    direction, return_sum, config_name)

    def flow_facility(self, facilities=None, location=None,
                      direction="incoming", return_sum=True,
                      config_name=None):
        """Get flow data for generic facility types.
        """
        return self.aggregate_flows(facilities, "facility",
                                    self.facility_types, location,
                                    direction, return_sum, config_name)

    def aggregate_operations(self, facilities, facility_class, default_list,
                             state, return_sum):
        """Get operations data for a facility type.
        Common loop: iterate facilities, call _get_operation, optionally sum.

        Parameters
        ----------
        facilities : str, list of str, or None
            Facility type names. If None, uses default_list.
        facility_class : str
            Facility class name (e.g. ``"reactor"``).
        default_list : list of str
            Default list of facility names when facilities is None.
        state : str or None
            Operational state to retrieve (e.g. ``"Operating"``). If None,
            sums all states.
        return_sum : bool
            If True, sum across all facilities.

        Returns
        -------
        np.ndarray or dict[str, np.ndarray]
        """
        facilities = self._normalize_facilities(
            facilities=facilities,
            default_list=default_list
        )

        result = {}
        for fac in facilities:
            ops = self._get_operation(fac, facility_class, state)
            if ops is None:
                ops = np.zeros_like(self._get_times_array())
            result[fac] = ops

        if return_sum:
            return np.sum(list(result.values()), axis=0)
        return result

    def operation_reactor(self, reactors=None, state=None, return_sum=True):
        """Get operations data for reactor facility types.
        If state="operating" units are power unit * time unit (eg. MWe-yr)
        otherwise, units are time unit
        """
        return self.aggregate_operations(reactors, "reactor",
                                         self.reactor_types, state,
                                         return_sum)

    def operation_storage(self, storages=None, state=None, return_sum=True):
        """Get operations data for storage facility types.
        units are time unit
        """
        return self.aggregate_operations(storages, "storage",
                                         self.storage_types, state,
                                         return_sum)

    def operation_enrichment(self, enrichments=None, state=None,
                             return_sum=True):
        """Get operations data for enrichment facility types.
        If state="operating" units are mass unit-SWU available
        otherwise, units are time unit
        """
        return self.aggregate_operations(enrichments, "enrichment",
                                         self.enrichment_types, state,
                                         return_sum)

    def operation_fabrication(self, fabrications=None, state=None,
                              return_sum=True):
        """Get operations data for fabrication facility types.
        If state="operating" units are mass unit capacity available
        otherwise, units are time unit
        """
        return self.aggregate_operations(fabrications, "fabrication",
                                         self.fabrication_types, state,
                                         return_sum)

    def operation_reprocessing(self, plants=None, state=None,
                               return_sum=True):
        """Get operations data for reprocessing facility types.
        If state="operating" units are mass unit capacity available
        otherwise, units are time unit
        """
        return self.aggregate_operations(plants, "reprocessing",
                                         self.reprocessing_types, state,
                                         return_sum)

    def operation_facility(self, facilities=None, state=None,
                           return_sum=True):
        """Get operations data for generic facility types.
        If state="operating" units are mass unit capacity available
        otherwise, units are time unit
        """
        return self.aggregate_operations(facilities, "facility",
                                         self.facility_types, state,
                                         return_sum)

    def aggregate_stocks(self, facilities, facility_class, default_list,
                         location, material, return_sum, config_name):
        """ Get cumulative stock flows for facilities.
        Common loop: iterate facilities, call _get_stock, optionally sum.

        Parameters
        ----------
        facilities : str, list of str, or None
            Facility type names. If None, uses default_list.
        facility_class : str
            Facility class name.
        default_list : list of str
            Default list of facility names when facilities is None.
        location : str or None
            Process stage category, or None to sum all.
        material : str, list of str, or None
            Material filter.
        return_sum : bool
            If True, sum across all facilities.
        config_name : str or None
            Stocks config name.

        Returns
        -------
        dict[str, np.ndarray] or dict[str, dict[str, np.ndarray]]
        """
        facilities = self._normalize_facilities(
            facilities=facilities,
            default_list=default_list
        )

        result = {}
        for fac in facilities:
            stock = self._get_stock(fac, facility_class, location, material,
                                    config_name)
            result[fac] = stock

        if return_sum:
            totals = {}
            for fac_stock in result.values():
                for mat_name, arr in fac_stock.items():
                    totals[mat_name] = totals.get(mat_name, 0) + arr
            return totals
        return result

    def stock_reactor(self, reactors=None, location="facility", material=None,
                      return_sum=True, config_name=None):
        """Get cumulative stock data for reactor facility types.
        """
        return self.aggregate_stocks(reactors, "reactor", self.reactor_types,
                                     location, material, return_sum,
                                     config_name)

    def stock_storage(self, storages=None, location="facility", material=None,
                      return_sum=True, config_name=None):
        """Get cumulative stock data for storage facility types.
        """
        return self.aggregate_stocks(storages, "storage", self.storage_types,
                                     location, material, return_sum,
                                     config_name)

    def stock_enrichment(self, enrichments=None, location=None, material=None,
                         return_sum=True, config_name=None):
        """Get cumulative stock data for enrichment facility types.
        """
        return self.aggregate_stocks(enrichments, "enrichment",
                                     self.enrichment_types, location,
                                     material, return_sum, config_name)

    def stock_fabrication(self, fabrications=None, location=None,
                          material=None, return_sum=True, config_name=None):
        """Get cumulative stock data for fabrication facility types.
        """
        return self.aggregate_stocks(fabrications, "fabrication",
                                     self.fabrication_types, location,
                                     material, return_sum, config_name)

    def stock_reprocessing(self, plants=None, location=None, material=None,
                           return_sum=True, config_name=None):
        """Get cumulative stock data for reprocessing facility types.
        """
        return self.aggregate_stocks(plants, "reprocessing",
                                     self.reprocessing_types, location,
                                     material, return_sum, config_name)

    def stock_facility(self, facilities=None, location=None, material=None,
                       return_sum=True, config_name=None):
        """Get cumulative stock data for generic facility types.
        """
        return self.aggregate_stocks(facilities, "facility",
                                     self.facility_types, location,
                                     material, return_sum, config_name)

# =======================WISE FUNCTIONS========================================

    def get_new_facility_deployments(
        self,
        facility_type: str,
        facility_class: str = "reactor",
    ) -> np.ndarray:
        """
        Number of new units of a given facility type deployed in each
        simulation time step, summed across all fleets.

        The simulation time axis is constructed from ``Simulation.start year``
        and ``Simulation.duration``.  The model time unit must be ``"YEARS"``.
        Each deployment event is assigned to the time step whose interval
        ``(step_start, step_start + 1)`` contains the deployment year.
        Events that fall outside the simulation window are ignored.

        Parameters
        ----------
        facility_type : str
            The ``"type name"`` of the facility to query (e.g. ``"PWR"``).
        facility_class : str, optional
            Facility class used only to validate that ``facility_type``
            exists in the input.  Defaults to ``"reactor"``.

        Returns
        -------
        deployments : np.ndarray
            Float array of length matching the simulation time axis where
            each element is the total quantity of ``facility_type`` deployed
            during that year.

        Raises
        ------
        ValueError
            If ``facility_type`` is not found in ``Types[facility_class]``,
            or if the model time unit is not ``"YEARS"``.
        """
        # Validate that the type exists
        type_names = self.type_names.get(facility_class, [])
        if facility_type not in type_names:
            raise ValueError(
                f"Facility type '{facility_type}' not found in "
                f"Types['{facility_class}']."
            )

        start_year = self.init_year

        time_unit = (
            self.input_data
            .get("Model", self.input_data.get("model", {}))
            .get("units", {})
            .get("time", "YEARS")
            .upper()
        )
        if time_unit != "YEARS":
            raise ValueError(
                f"get_new_facility_deployments requires model time unit "
                f"'YEARS', got '{time_unit}'."
            )

        n_steps = len(self._get_times_array())
        deployments = np.zeros(n_steps)

        all_deployments = self.input_data.get(
            "Deployments", self.input_data.get("deployments", {}))

        for fleet in all_deployments.values():
            if fleet.get("type name") != facility_type:
                continue

            quantities = fleet.get("deployment quantity", [])

            if "deployment dates" in fleet:
                dates = fleet["deployment dates"]
                deploy_years = []
                for d in dates:
                    if isinstance(d, int):
                        deploy_years.append(float(d))
                    else:
                        # "YYYY-MM-DD" string
                        deploy_years.append(float(str(d)[:4]))
            elif "deployment time" in fleet:
                deploy_years = [
                    start_year + t for t in fleet["deployment time"]]
            else:
                continue

            for year, qty in zip(deploy_years, quantities):
                idx = int(year - start_year)
                if 0 <= idx < n_steps:
                    deployments[idx] += float(qty)
        return deployments

    def get_facility_retirements(
        self,
        facility_type: str,
        facility_class: str = "reactor",
    ) -> np.ndarray:
        """
        Number of units of a given facility type retiring in each simulation
        time step, derived by offsetting deployments by the type's lifetime.

        Each unit deployed in time step ``i`` is counted as a retirement in
        time step ``i + lifetime``.  Retirements that fall outside the
        simulation window are discarded.

        Parameters
        ----------
        facility_type : str
            The ``"type name"`` of the facility to query (e.g. ``"PWR"``).
        facility_class : str, optional
            Facility class used to look up the type's lifetime and to
            validate that ``facility_type`` exists. Defaults to
            ``"reactor"``.

        Returns
        -------
        retirements : np.ndarray
            Float array of the same length as ``get_new_facility_deployments``
            where each element is the quantity of units retiring that year.

        Raises
        ------
        ValueError
            If ``facility_type`` is not found in ``Types[facility_class]``,
            if the model time unit is not ``"YEARS"``, or if the type has
            no ``"lifetime"`` defined.
        """
        deployments = self.get_new_facility_deployments(
            facility_type,
            facility_class)
        duration = len(self._get_times_array())

        type_data = self._get_type_data(facility_class)
        lifetime = type_data.get(facility_type, {}).get("lifetime")
        if lifetime is None:
            raise ValueError(
                f"Facility type '{facility_type}' has no 'lifetime' defined."
            )
        lifetime = int(lifetime)

        retirements = np.zeros(duration)
        for i, qty in enumerate(deployments):
            j = i + lifetime
            if qty > 0 and 0 <= j < duration:
                retirements[j] += float(qty)

        return retirements

    def get_facility_fleet_size(
        self,
        facility_type: str,
        facility_class: str = "reactor",
    ) -> np.ndarray:
        """
        Total number of active units of a given facility type at each
        simulation time step.

        Computed as the cumulative sum of deployments minus the cumulative
        sum of retirements.

        Parameters
        ----------
        facility_type : str
            The ``"type name"`` of the facility to query (e.g. ``"PWR"``).
        facility_class : str, optional
            Facility class. Defaults to ``"reactor"``.

        Returns
        -------
        fleet_size : np.ndarray
            Float array of the same length as ``get_new_facility_deployments``
            where each element is the number of active units at that
            time step.

        Raises
        ------
        ValueError
            If ``facility_type`` is not found in ``Types[facility_class]``,
            if the model time unit is not ``"YEARS"``, or if the type has
            no ``"lifetime"`` defined.
        """
        deployments = self.get_new_facility_deployments(
            facility_type, facility_class)
        retirements = self.get_facility_retirements(
            facility_type, facility_class)
        return np.cumsum(deployments - retirements)

    def get_new_deployments(
        self,
        reactors: str | list[str] | None = None,
        return_sum: bool = False,
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Number of new reactor deployments for one or more reactor types.

        Parameters
        ----------
        reactors : str or list[str] or None
            Reactor type name(s). If None, uses all reactor types.
        return_sum : bool, optional
            If True, return a single array summed across all requested
            reactor types. If False, return a dict keyed by reactor type.
            Default False.

        Returns
        -------
        np.ndarray or dict[str, np.ndarray]
            Deployment counts per reactor type, or summed across reactor
            types if ``return_sum=True``.
        """
        reactors = self._normalize_facilities(
            facilities=reactors,
            facility_class="reactor"
        )

        deploy_dict = {}
        for reactor in reactors:
            deploy_dict[reactor] = self.get_new_facility_deployments(
                facility_type=reactor,
                facility_class="reactor",
            )

        if return_sum:
            return np.sum(list(deploy_dict.values()), axis=0)
        return deploy_dict

    def get_retirements(
        self,
        reactors: str | list[str] | None = None,
        return_sum: bool = False,
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Number of reactor retirements for one or more reactor types.

        Parameters
        ----------
        reactors : str or list[str] or None
            Reactor type name(s). If None, uses all reactor types.
        return_sum : bool, optional
            If True, return a single array summed across all requested
            reactor types. If False, return a dict keyed by reactor type.
            Default False.

        Returns
        -------
        np.ndarray or dict[str, np.ndarray]
            Retirement counts per reactor type, or summed across reactor
            types if ``return_sum=True``.
        """
        reactors = self._normalize_facilities(
            facilities=reactors,
            facility_class="reactor"
        )

        retire_dict = {}
        for reactor in reactors:
            retire_dict[reactor] = self.get_facility_retirements(
                facility_type=reactor,
                facility_class="reactor",
            )

        if return_sum:
            return np.sum(list(retire_dict.values()), axis=0)
        return retire_dict

    def get_fleet_size(
        self,
        reactors: str | list[str] | None = None,
        return_sum: bool = False,
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Fleet size for one or more reactor types.

        Parameters
        ----------
        reactors : str or list[str] or None
            Reactor type name(s). If None, uses all reactor types.
        return_sum : bool, optional
            If True, return a single array summed across all requested
            reactor types. If False, return a dict keyed by reactor type.
            Default False.

        Returns
        -------
        np.ndarray or dict[str, np.ndarray]
            Fleet size per reactor type, or summed across reactor types
            if ``return_sum=True``.
        """
        reactors = self._normalize_facilities(
            facilities=reactors,
            facility_class="reactor"
        )

        fleet_dict = {}
        for reactor in reactors:
            fleet_dict[reactor] = self.get_facility_fleet_size(
                facility_type=reactor,
                facility_class="reactor",
            )

        if return_sum:
            return np.sum(list(fleet_dict.values()), axis=0)
        return fleet_dict

    def stock_fuel_demand(
        self, reactors: str | list[str] | None = None,
        return_sum: bool = True,
        config_name: str | None = None
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Annual fuel mass demand from one or more reactors.

        Tries the ``"process"`` stage incoming flow first; falls back to
        the ``"facility"`` stage if not found.

        Parameters
        ----------
        reactors : str or list of str or None
            Reactor(s) to calculate fuel demand for. If None, uses all
            reactors.
        return_sum : bool, optional
            If True, returns a single array summed over all reactors.
            Default True.
        config_name : str or None, optional
            Flows config name. If None, uses the first available.

        Returns
        -------
        fuel_mass : np.ndarray or dict[str, np.ndarray]
            Yearly fuel mass per reactor, or total if ``return_sum=True``.
        """
        reactors = self._normalize_facilities(
            facilities=reactors,
            facility_class="reactor"
        )

        fuel_mass_dict = {}
        for reactor in reactors:
            incoming = self._get_flow(
                reactor, "reactor", "process", "incoming", config_name)
            if incoming is None:
                incoming = self._get_flow(
                    reactor, "reactor", "facility", "incoming", config_name)
            if incoming is None:
                raise ValueError(
                    f"Reactor '{reactor}' not found in flows data.")
            fuel_mass_dict[reactor] = incoming

        if return_sum:
            return np.sum(list(fuel_mass_dict.values()), axis=0)
        return fuel_mass_dict

    def stock_fuel_discharged(
        self, reactors: str | list[str] | None = None,
        return_sum: bool = True,
        config_name: str | None = None
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Annual discharged fuel mass from one or more reactors.

        Tries the ``"process"`` stage outgoing flow first; falls back to
        the ``"facility"`` stage if not found.

        Parameters
        ----------
        reactors : str or list of str or None
            Reactor(s) to calculate discharged fuel for. If None, uses all
            reactors.
        return_sum : bool, optional
            If True, returns a single array summed over all reactors.
            Default True.
        config_name : str or None, optional
            Flows config name. If None, uses the first available.

        Returns
        -------
        discharged_mass : np.ndarray or dict[str, np.ndarray]
            Discharged fuel mass per reactor, or total if
            ``return_sum=True``.
        """
        reactors = self._normalize_facilities(
            facilities=reactors,
            facility_class="reactor"
        )

        fuel_mass_dict = {}
        for reactor in reactors:
            outgoing = self._get_flow(
                reactor, "reactor", "process", "outgoing", config_name)
            if outgoing is None:
                outgoing = self._get_flow(
                    reactor, "reactor", "facility", "outgoing", config_name)
            if outgoing is None:
                raise ValueError(
                    f"Reactor '{reactor}' not found in flows data.")
            fuel_mass_dict[reactor] = outgoing

        if return_sum:
            return np.sum(list(fuel_mass_dict.values()), axis=0)
        return fuel_mass_dict

    def stock_fuel_resources(
        self,
        reactors: str | list[str] | None = None,
        natu_assay: float = None,
        tails_assay: float = None,
        return_sum: bool = True,
        split_cat: bool = False,
        cascade_splits: list[float] | None = None,
    ):
        """
        Compute natural-uranium feed, enrichment tails, and SWU
        requirements for one or more reactors.

        Enrichment and mass are derived per-transaction from the raw HDF5
        process data, avoiding errors from averaging non-linear enrichment
        calculations. Each incoming transaction to a reactor's process stage
        is individually cascaded and the results binned into annual totals.

        Parameters
        ----------
        reactors : str or list[str]
            Prototype name(s).
        natu_assay : float
            Enrichment of the feed (typically natural uranium) as a decimal
            between 0 and 1. Required.
        tails_assay : float
            Enrichment of the tails material as a decimal between 0 and 1.
            Required.
        return_sum : bool, optional
            If True, returns the sum across reactors (default True).
        split_cat : bool, optional
            If True, return tails and SWU split by cascade stage;
            otherwise return totals (default False).
        cascade_splits : list of float
            Intermediate enrichments (as decimals) that define cascade stages.

        Returns
        -------
        dict[str, dict[str, np.ndarray] | np.ndarray]
            Dictionary with keys 'natu', 'tails', and 'swu'.
        """
        assert natu_assay is not None and 0 <= natu_assay <= 1, \
            f"natu_assay must be a number between 0 and 1, got {natu_assay!r}"
        assert tails_assay is not None and 0 <= tails_assay <= 1, \
            f"tails_assay must be a number between 0 and 1, got " \
            f"{tails_assay!r}"

        if not cascade_splits:
            cascade_splits = [np.inf]
        else:
            cascade_splits = list(cascade_splits)

        reactors = self._normalize_facilities(
            facilities=reactors,
            facility_class="reactor"
        )

        n_steps = len(self._get_times_array())

        cascade_cache = {}
        res = {"natu": {}, "tails": {}, "swu": {}}

        with h5py.File(self.hdf5_path, 'r') as f:
            nuclide_ids = [
                nid.decode() if isinstance(nid, bytes) else nid
                for nid in f['OUTPUT/nuclide_ids'][()]
            ]
            nuclide_index = {name: i for i, name in enumerate(nuclide_ids)}
            u235_idx = nuclide_index.get('u235')
            u_idxs = [i for name, i in nuclide_index.items()
                      if name.startswith('u')]

            for reactor in reactors:
                natu_arr = np.zeros(n_steps)
                # tails_arr and swu_arr are allocated once n_stages is known
                tails_arr = None
                swu_arr = None

                reactor_group_path = f'Reactor/{reactor}'
                if reactor_group_path not in f:
                    res["natu"][reactor] = natu_arr
                    res["tails"][reactor] = np.zeros(n_steps)
                    res["swu"][reactor] = np.zeros(n_steps)
                    continue

                for instance in f[reactor_group_path].values():
                    proc = instance.get('process')
                    if proc is None:
                        continue
                    times_raw = proc['times'][()]
                    masses = proc['masses'][()]
                    compositions = proc['compositions'][()]

                    incoming = masses > 0
                    if not np.any(incoming):
                        continue

                    times_in = times_raw[incoming]
                    masses_in = masses[incoming]
                    comps_in = compositions[incoming]
                    idxs = (times_in / SECONDS_PER_YEAR).astype(int)

                    for idx, mass, comp in zip(idxs, masses_in, comps_in):
                        if idx < 0 or idx >= n_steps:
                            continue
                        if u235_idx is None:
                            continue

                        u_mass = comp[u_idxs].sum()
                        if u_mass <= 0:
                            continue

                        enr = float(comp[u235_idx]) / float(u_mass)
                        if enr <= 0:
                            continue

                        key = round(enr, 8)
                        if key not in cascade_cache:
                            try:
                                cascade = enrichment_cascade(
                                    feed_enr=natu_assay,
                                    prod_enr=enr,
                                    tail_enr=tails_assay,
                                    cascade_splits=cascade_splits,
                                )
                                cascade_cache[key] = {
                                    "natu": cascade["feed"][0],
                                    "tails": np.asarray(
                                        cascade["tails"], dtype=float),
                                    "swu": np.asarray(
                                        cascade["swu"], dtype=float),
                                }
                            except (ValueError, AssertionError):
                                continue

                        c = cascade_cache[key]
                        n_stages = len(c["tails"])
                        if tails_arr is None:
                            tails_arr = np.zeros((n_steps, n_stages))
                            swu_arr = np.zeros((n_steps, n_stages))

                        natu_arr[idx] += c["natu"] * mass
                        tails_arr[idx] += c["tails"] * mass
                        swu_arr[idx] += c["swu"] * mass

                if tails_arr is None:
                    tails_arr = np.zeros((n_steps, 1))
                    swu_arr = np.zeros((n_steps, 1))

                res["natu"][reactor] = natu_arr
                res["tails"][reactor] = (
                    tails_arr if split_cat else tails_arr.sum(axis=1))
                res["swu"][reactor] = (
                    swu_arr if split_cat else swu_arr.sum(axis=1))

        if return_sum:
            return {k: sum(v.values()) for k, v in res.items()}
        return res

    def stock_fuel_natu(
        self,
        reactors: str | list[str] | None = None,
        natu_assay: float = None,
        tails_assay: float = None,
        return_sum: bool = True,
        cascade_splits: list[float] | None = None,
    ):
        """
        Compute natural uranium requirements for one or more reactors.

        Parameters
        ----------
        reactors : str or list[str]
            Prototype name(s).
        natu_assay : float
            Enrichment of the feed (typically natural uranium) as a decimal
            between 0 and 1. Required.
        tails_assay : float
            Enrichment of the tails material as a decimal between 0 and 1.
            Required.
        return_sum : bool, optional
            If True, returns the sum across reactors (default True).
        cascade_splits : list of float
            Intermediate enrichments (as decimals) that define cascade stages.

        Returns
        -------
        dict[str, np.ndarray] or np.ndarray
            Natural-uranium feed per reactor (or summed).
        """
        return self.stock_fuel_resources(
            reactors=reactors,
            natu_assay=natu_assay,
            tails_assay=tails_assay,
            return_sum=return_sum,
            cascade_splits=cascade_splits,
        )["natu"]

    def stock_fuel_tails(
        self,
        reactors: str | list[str] | None = None,
        natu_assay: float = None,
        tails_assay: float = None,
        return_sum: bool = True,
        split_cat: bool = False,
        cascade_splits: list[float] | None = None,
    ):
        """
        Compute enrichment tails for one or more reactors.

        Parameters
        ----------
        reactors : str or list[str]
            Prototype name(s).
        natu_assay : float
            Enrichment of the feed (typically natural uranium) as a decimal
            between 0 and 1. Required.
        tails_assay : float
            Enrichment of the tails material as a decimal between 0 and 1.
            Required.
        return_sum : bool, optional
            If True, returns the sum across reactors (default True).
        split_cat : bool, optional
            If True, return tails split by cascade stage.
        cascade_splits : list of float
            Intermediate enrichments (as decimals) that define cascade stages.

        Returns
        -------
        dict[str, np.ndarray] or np.ndarray
            Tails per reactor (or summed), split or total.
        """
        return self.stock_fuel_resources(
            reactors=reactors,
            natu_assay=natu_assay,
            tails_assay=tails_assay,
            return_sum=return_sum,
            split_cat=split_cat,
            cascade_splits=cascade_splits,
        )["tails"]

    def stock_fuel_swu(
        self,
        reactors: str | list[str] | None = None,
        natu_assay: float = None,
        tails_assay: float = None,
        return_sum: bool = True,
        split_cat: bool = False,
        cascade_splits: list[float] | None = None,
    ):
        """
        Compute SWU requirements for one or more reactors.

        Parameters
        ----------
        reactors : str or list[str]
            Prototype name(s).
        natu_assay : float
            Enrichment of the feed (typically natural uranium) as a decimal
            between 0 and 1. Required.
        tails_assay : float
            Enrichment of the tails material as a decimal between 0 and 1.
            Required.
        return_sum : bool, optional
            If True, returns the sum across reactors (default True).
        split_cat : bool, optional
            If True, return SWU split by cascade stage.
        cascade_splits : list of float
            Intermediate enrichments (as decimals) that define cascade stages.

        Returns
        -------
        dict[str, np.ndarray] or np.ndarray
            SWU per reactor (or summed), split or total.
        """
        return self.stock_fuel_resources(
            reactors=reactors,
            natu_assay=natu_assay,
            tails_assay=tails_assay,
            return_sum=return_sum,
            split_cat=split_cat,
            cascade_splits=cascade_splits,
        )["swu"]

    def stock_waste_mass(
            self,
            material: str | list[str] | None = None,
            storage: str = 'waste',
            return_sum: bool = True,
            config_name: str | None = None
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Retrieves cumulative waste data from stocks output and
        calculates the annual flow data.

        Parameters
        ----------
        material : str or list of str or None
            Material type name(s). If None, returns all materials.
        storage : str, optional
            The storage type name where the material is stored.
            Default ``'waste'``.
        return_sum : bool, optional
            If True, returns a single array summed over all materials.
            Default True.
        config_name : str or None, optional
            Stocks config name. If None, uses the first available.

        Returns
        -------
        waste_flow : np.ndarray or dict[str, np.ndarray]
            The annual waste mass flow per material (dict) or summed
            (ndarray) depending on ``return_sum``.
        """
        cumulative = self._get_stock(storage, "storage", "facility", material,
                                     config_name)
        if not cumulative:
            raise ValueError(
                f"Storage '{storage}' not found in stocks data")

        mass_flow_dict = {}
        for mat, cum_arr in cumulative.items():
            mass_flow_dict[mat] = np.diff(cum_arr, prepend=0)

        if return_sum:
            return np.sum(
                np.array(list(mass_flow_dict.values())), axis=0
            )
        return mass_flow_dict

    def get_generated_electricity(
        self, reactors=None, return_sum=True
    ) -> dict[str, np.ndarray] | np.ndarray:
        """
        Determines the amount of generated electricity (GW-yr) for
        each time step for each reactor type.

        ``get_generated_electricity`` is a wrapper for ``get_generated_power``
        that returns the result in GW-yr, and works only if time steps are
        1 year long. For any other time units or uses, use
        ``get_generated_power`` directly.

        Parameters
        -----------
        reactors : list of str or None
            Names of reactors in the simulation.
        return_sum : bool
            If True, returns a summed array.

        Returns
        --------
        electricity_dict : dict or np.ndarray
            Electricity in GW-yr per reactor (or summed).
        """
        return self.get_generated_power(reactors, return_sum=return_sum)

    # ===========================HELPER FUNCTIONS=============================

    @staticmethod
    def _read_group(group):
        """Recursively read an HDF5 group into a nested dict of arrays."""
        result = {}
        for key in group:
            item = group[key]
            if isinstance(item, h5py.Group):
                result[key] = DYMONDOutput._read_group(item)
            elif isinstance(item, h5py.Dataset):
                data = item[()]
                if isinstance(data, bytes):
                    result[key] = data.decode('utf-8')
                elif isinstance(data, np.ndarray) and \
                        data.dtype.kind in ('U', 'S', 'O'):
                    result[key] = data.item() if data.ndim == 0 \
                        else data.tolist()
                else:
                    result[key] = np.atleast_1d(np.asarray(data, dtype=float))
        return result

    def _get_type_names(self):
        """Extract facility type names from input data for all classes.

        Returns
        -------
        dict[str, list[str]]
            Mapping of facility class to list of type names, e.g.
            {"reactor": ["PWR", "SFR"], "storage": ["waste"], ...}
        """
        types = self.input_data.get("Types", self.input_data.get("types", {}))
        facility_classes = [
            "reactor", "storage", "enrichment",
            "fabrication", "reprocessing", "facility"
        ]
        result = {}
        for fc in facility_classes:
            result[fc] = [entry["name"] for entry in types.get(fc, [])]
        return result

    def _get_type_data(self, type_name):
        """Extract specifications for all facility types from input data."""
        types = self.input_data.get("Types", self.input_data.get("types", {}))
        facility_list = types.get(type_name, [])
        facility_data = {}
        for facility in facility_list:
            f_copy = dict(facility)
            name = str(f_copy.pop("name"))
            facility_data[name] = f_copy
        return facility_data

    def _get_reactor_data(self):
        """Extract reactor type specifications from input data."""
        return self._get_type_data("reactor")

    @staticmethod
    def _default_config(data_dict):
        """Return the first config name from a stocks/flows dict."""
        keys = [k for k in data_dict if k != "times"]
        if not keys:
            raise ValueError("No config found in data.")
        return keys[0]

    def _get_times_array(self):
        """Get the times array from whichever output group is available."""
        if self.operations and "times" in self.operations:
            return np.asarray(self.operations["times"])
        if self.stocks:
            cfg = self._default_config(self.stocks)
            return np.asarray(self.stocks[cfg]["times"])
        if self.flows:
            cfg = self._default_config(self.flows)
            return np.asarray(self.flows[cfg]["times"])
        raise ValueError("No times array found in output data.")

    def _get_flows_config(self, config_name=None, facility_class=None):
        """Get a specific flows config dict.

        If config_name is not provided, try facility_class as the config name.
        If that is not available, fall back to the first available config.
        """
        # Use explicit config if provided
        if config_name is not None:
            if config_name not in self.flows:
                raise ValueError(
                    f"Flows config '{config_name}' not found. "
                    f"Available configs: {list(self.flows.keys())}"
                )
            return self.flows[config_name]

        # Prefer the facility class when it matches a top-level flows config
        if facility_class is not None and facility_class in self.flows:
            return self.flows[facility_class]

        # Fall back to the first available config
        config_name = self._default_config(self.flows)
        return self.flows[config_name]

    def _get_stocks_config(self, config_name=None):
        """Get a specific stocks config dict, defaulting to first available."""
        if config_name is None:
            config_name = self._default_config(self.stocks)
        return self.stocks[config_name]

    def _get_operation(self, facility, facility_class, state=None):
        """Get operations array(s) for a facility type.

        Parameters
        ----------
        facility : str
            Facility type name (e.g. ``"PWR"``).
        facility_class : str
            Facility class (e.g. ``"reactor"``).
        state : str or None
            Operational state to retrieve (e.g. ``"Operating"``). If None,
            sums all states for the facility type.

        Returns
        -------
        np.ndarray or None
            Operations array, or None if the facility is not found.
        """
        class_data = self.operations.get(facility_class, {})
        facility_data = class_data.get(facility)
        if facility_data is None:
            return None

        if state is not None:
            arr = facility_data.get(state)
            return np.asarray(arr) if arr is not None else None

        # Sum all states
        total = None
        for arr in facility_data.values():
            if isinstance(arr, np.ndarray):
                total = arr if total is None else total + arr
        return total

    @staticmethod
    def _sum_materials(category_dict, direction=None):
        """Sum all material arrays in a category, optionally selecting
        a direction (incoming/outgoing) for flows data."""
        total = None
        for mat_name, mat_data in category_dict.items():
            if isinstance(mat_data, dict) and direction is not None:
                arr = np.asarray(mat_data[direction])
            elif isinstance(mat_data, np.ndarray):
                arr = mat_data
            else:
                continue
            total = arr if total is None else total + arr
        return total if total is not None else np.array([])

    def _get_flow(self, facility, facility_class, location, direction,
                  config_name=None):
        """Get total flow for a facility type at a location.

        Parameters
        ----------
        facility : str
            Facility type name (e.g. 'PWR', 'waste').
        facility_class : str
            Facility class (e.g. 'reactor', 'storage').
        location : str or None
            Material category (e.g. 'facility', 'process'). If None,
            sums across all categories.
        direction : str
            'incoming' or 'outgoing'.
        config_name : str or None
            Flows config name. If None, uses the first available.

        Returns
        -------
        np.ndarray or None
            Total flow array, or None if not found.
        """
        flows_cfg = self._get_flows_config(
            config_name=config_name,
            facility_class=facility_class,
        )
        class_data = flows_cfg.get(facility_class, {})

        # Try per-type first, fall back to totals
        source = class_data.get("totals", class_data.get(facility, {}))
        if facility in class_data and facility != "totals":
            source = class_data[facility]

        total = None
        if location is not None:
            # Single category
            cat_data = source.get(location, {})
            if not isinstance(cat_data, dict):
                return total
            cat_sum = self._sum_materials(cat_data, direction=direction)
            if cat_sum is not None and len(cat_sum) > 0:
                total = cat_sum if total is None else total + cat_sum
        else:
            # Sum across all categories
            for cat_name, cat_data in source.items():
                if not isinstance(cat_data, dict):
                    continue
                cat_sum = self._sum_materials(cat_data, direction=direction)
                if cat_sum is not None and len(cat_sum) > 0:
                    total = cat_sum if total is None else total + cat_sum

        return total

    def _get_stock(self, facility, facility_class, location="facility",
                   material=None, config_name=None):
        """Get cumulative stock arrays for a facility type.

        Parameters
        ----------
        facility : str
            Facility type name.
        facility_class : str
            Facility class (e.g. 'storage', 'reactor').
        location : str or None
            Process stage category. If None, sums across all categories.
        material : str or list of str or None
            Filter to specific material(s). If None, returns all.
        config_name : str or None
            Stocks config name. If None, uses the first available.

        Returns
        -------
        dict[str, np.ndarray]
            {material_name: cumulative_mass_array}
        """
        stocks_cfg = self._get_stocks_config(config_name)
        class_data = stocks_cfg.get(facility_class, {})

        if facility not in class_data:
            return {}

        facility_data = class_data[facility]

        # Collect arrays from the requested location(s)
        collected = {}
        if location is not None:
            loc_data = facility_data.get(location, {})
            if isinstance(loc_data, dict):
                for k, v in loc_data.items():
                    if isinstance(v, np.ndarray):
                        collected[k] = collected.get(k, 0) + v
        else:
            for loc_name, loc_data in facility_data.items():
                if not isinstance(loc_data, dict):
                    continue
                for k, v in loc_data.items():
                    if isinstance(v, np.ndarray):
                        collected[k] = collected.get(k, 0) + v

        # Filter by material if specified
        if material is not None:
            if isinstance(material, str):
                material = [material]
            collected = {k: v for k, v in collected.items() if k in material}

        return collected

# =================================DEPRECATED==================================

    def _get_reactor_incoming_flow(self, reactor, config_name=None):
        """Get total incoming flow for a reactor type across all materials
        and categories. Deprecated: use _get_flow directly."""
        print("WARNING: This function is deprecated. Use _get_flow instead.")
        return self._get_flow(reactor, "reactor", "facility", "incoming",
                              config_name)

    def _get_reactor_outgoing_flow(self, reactor, config_name=None):
        """Get total outgoing flow for a reactor type across all materials
        and categories. Deprecated: use _get_flow directly."""
        print("WARNING: This function is deprecated. Use _get_flow instead.")
        return self._get_flow(reactor, "reactor", "facility", "outgoing",
                              config_name)

    def power_generated(self, reactor: str):
        """
        Retrieves the power generation data from operations output.

        Deprecated: use get_generated_power instead.

        Parameters
        -----------
        reactor : str
            The name of the reactor type.

        Returns
        -----------
        np.ndarray
            The annual power generation (MW) for the reactor type.
        """
        print("WARNING: This function is deprecated. "
              "Use get_generated_power instead.")
        ops_reactor = self.operations.get("reactor", {})
        if reactor not in ops_reactor:
            raise ValueError(
                f"Reactor '{reactor}' not found in operations data.")

        times = self._get_times_array()
        step_sizes = np.diff(times, prepend=0)
        op_time = np.asarray(ops_reactor[reactor].get(
            "Operating", np.zeros_like(times)))
        rated_power_mw = self.reactor_data[reactor].get("power", 0.0)

        with np.errstate(divide='ignore', invalid='ignore'):
            fraction = np.where(step_sizes > 0, op_time / step_sizes, 0.0)
        return fraction * rated_power_mw

    def fuel_fabricated(self, reactor: str, config_name=None):
        """
        Retrieves the fuel fabrication data (incoming flow) for a reactor.

        Deprecated: use stock_fuel_demand instead.

        Parameters
        -----------
        reactor : str
            The name of the reactor type.
        config_name : str or None
            Flows config name. If None, uses the first available.

        Returns
        -----------
        np.ndarray
            The annual fuel fabrication for the reactor type.
        """
        print("WARNING: This function is deprecated. "
              "Use stock_fuel_demand or flows_fabrication instead.")
        incoming = self._get_reactor_incoming_flow(reactor, config_name)
        if incoming is None:
            raise ValueError(
                f"Reactor '{reactor}' not found in flows data.")
        return incoming

# ===========================UTILITY FUNCTIONS=============================

    def _normalize_facilities(
        self,
        facilities,
        facility_class="reactor",
        default_list=None
    ) -> np.ndarray:
        """
        Return a normalized array of facilities.
        If facilities is None, uses default_list, but if default_list is also
        None, uses all facilities of the specified class.

        Parameters
        ----------
        facilities : str or list of str or None
            Facility name(s). If None, uses all facilities of the
            specified class.
        facility_class : str
            Facility class to look up type names if facilities is None.
        default_list: list of str or None
            Default list of facilities to use if facilities is None. If None,
            uses all facilities of the specified class.

        Returns
        -------
        np.ndarray
            Array of facility names.
        """
        if facilities is None:
            if default_list is not None:
                facilities = default_list
            else:
                facilities = self.type_names[facility_class]
        facilities = np.atleast_1d(facilities)
        return facilities
