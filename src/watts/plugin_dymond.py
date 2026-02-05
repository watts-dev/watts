# SPDX-FileCopyrightText: 2024 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
from typing import List, Optional
import numpy as np
import json
import os

from .plugin import PluginGeneric, _find_executable
from .results import Results, ExecInfo
from .fileutils import PathLike
from .parameters import Parameters
from .enrichment_utils import enrichment_cascade


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
    output_data
        Dictionary with information on structure of other dictionaries
        (model times and nuclides)

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

    def get_object(self):
        return DYMONDOutput(self.inputs, self.outputs)


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
        executable: PathLike = "dymond.sh",
        extra_inputs: Optional[List[str]] = None,
        extra_template_inputs: Optional[List[PathLike]] = None,
        show_stdout: bool = False,
        show_stderr: bool = False,
    ):

        executable = _find_executable(executable, "DYMOND_DIR")
        execute_command = ["{self.executable}", "-i", "{self.input_name}"]

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

        self.input_name = "DYMOND_input"

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
    def __init__(self, input_files, output_files):
        """
        Class to access and browse an output file from DYMOND.
        All input and output files must be formatted as json files.
        Parameters:
        -----------
        path: str
            path to output file, including file name
        """
        # Convert to Path objects if necessary
        input_files = [Path(inp) for inp in input_files]
        output_files = [Path(oup) for oup in output_files]
        
        # Check if files exist
        for inp in input_files:
            assert inp.is_file(), f"Input file {inp} does not exist."
        for oup in output_files:
            assert oup.is_file(), f"Output file {oup} does not exist."

        # Check if files are json-formatted
        for inp in input_files:
            try:
                input_dict = json.loads(inp.read_text(encoding="utf-8"))
            except Exception as error:
                raise ValueError(
                    f"Error reading input file {inp} as JSON: {error}")
        for oup in output_files:
            try:
                output_dict = json.loads(oup.read_text(encoding="utf-8"))
            except Exception as error:
                raise ValueError(
                    f"Error reading output file {oup} as JSON: {error}")

        self.inputs = input_files
        self.reactors, self.reprocess_plants = self._get_type_names()
        self.outputs = output_files
        self.stocks, self.flows, self.operations, self.output_data, self.reactor_data = (
            self._get_DYMOND_json_data()
        )
   
    def _get_DYMOND_json_data(self) -> dict:
        """Read abbreviated DYMOND output JSON files and return it
        as dictionaries"""
        for oup in self.outputs:
            if "stocks" in str(oup):
                stocks_dict = json.loads(oup.read_text())
            elif "flows" in str(oup):
                flows_dict = json.loads(oup.read_text())
            elif "operations" in str(oup):
                operations_dict = json.loads(oup.read_text())
            elif "output" in str(oup):
                output_data_dict = json.loads(oup.read_text())

        # Get reactor data from input data
        # Input data is contained in output_data_dict
        reactor_data = output_data_dict.get("input", {}).get("types", {}).get("reactor", [])
        reactor_data_dict = {}
        for r in reactor_data:
            reactor = str(r["name"])
            del r["name"]
            reactor_data_dict[reactor] = r
            
        return (stocks_dict, flows_dict, operations_dict, output_data_dict, reactor_data_dict)

    def _get_type_names(self) -> list[str]:
        """Read DYMOND input for type definitions and return the type names"""
        for inp in self.inputs:
            if ".input" in str(inp):
                input_dict = json.loads(inp.read_text())

        reactors = []
        if "reactor" in input_dict["types"]:
            for reactor in input_dict["types"]["reactor"]:
                reactors.append(reactor["name"])

        reprocessing_plants = []
        if "reprocessing" in input_dict["types"]:
            for reprocessing in input_dict["types"]["reprocessing"]:
                reprocessing_plants.append(reprocessing["name"])

        return (reactors, reprocessing_plants)

    def get_times(self):
        """
        Gets different time-related data from a simulation

        Parameters:
        -----------

        Returns:
        --------
        dict
            {'init_year':int, 'init_month':int,
             'duration':int, 'time': int, 'years':int}
        """
        years = self.output_data["times"]  # Get years from output data
        init_year = min(years)  # First year of simulation
        init_month = 1  # DYMOND outputs yearly
        duration = int((max(years) - min(years) + 1)
                       * 12)  # duration in months
        return {
            "init_year": init_year,
            "init_month": init_month,
            "duration": duration,
            "years": years,
        }

    def get_capacity_factors(self, reactors=None):
        """
        Get capacity factors for reactors.

        Parameters:
        -----------
        reactors: list of str or None
            List of reactor names to get capacity factors for. 
            If None, use all reactors.

        Returns:
        --------
        dict
            Dictionary with reactor names as keys and capacity factors as values.
        """
        if reactors is None:
            reactors = self.reactors
        reactors = np.atleast_1d(reactors)
        cf_dict = {
            reactor: self.reactor_data[reactor].get("capacity factor", np.nan) 
            for reactor in reactors
        }
        return cf_dict

    def get_generated_power(
        self, reactors=None, return_sum=True
    ) -> dict[str, np.ndarray] | np.ndarray:
        """
        Determines the amount of generated power (GW) for 
        each time step for each reactor.

        Parameters:
        -----------
        reactors: list of str or None
            names of reactors in the simulation

        Returns:
        --------
        power_dict: dictionary
            keys are strings, the reactor names
            the values are a numpy array with one element for
            each time step in the scenario, indicating how
            much power is generated for each key during the
            simulation.
        """
        if reactors is None:
            reactors = self.reactors
        reactors = np.atleast_1d(reactors)
        power_dict = {}
        for reactor in reactors:
            if reactor not in self.operations["reactors"]:
                raise ValueError(
                    f"Reactor '{reactor}' not found in operations data.")
            # Convert power from MW to GW
            power_dict[reactor] = np.array(
                self.operations["reactors"][reactor]) / 1e3
        if return_sum:
            return np.sum(list(power_dict.values()), axis=0)
        return power_dict

    def get_generated_electricity(
        self, reactors=None, return_sum=True
    ) -> dict[str, np.ndarray] | np.ndarray:
        """
        Determines the amount of generated electricity (GWh) for 
        each time step for each reactor.
        This accounts for the fact that DYMOND outputs yearly values.
        
        Parameters:
        -----------
        reactors: list of str or None
            names of reactors in the simulation

        Returns:
        --------
        electricity_dict: dictionary
            keys are strings, the reactor names
            the values are a numpy array with one element for
            each time step in the scenario, indicating how
            much electricity is generated for each key during the
            simulation.
        """
        power_dict = self.get_generated_power(reactors, return_sum=False)
        electricity_dict = {}        
        
        for reactor, power in power_dict.items():
            # Convert power (GW) to electricity (GWh)
            electricity_dict[reactor] = power * 8760  # hours in a year
        if return_sum:
            return np.sum(list(electricity_dict.values()), axis=0)
        return electricity_dict
    
    def get_deployed_capacity(
        self, reactors=None, return_sum=True
    ) -> dict[str, np.ndarray] | np.ndarray:
        """
        Determines the deployed capacity (GW) for each time step
        for each reactor. It corresponds to the generated power
        divided by the corresponding capacity factor for each reactor.

        Parameters:
        -----------
        reactors: list of str or None
            names of reactors in the simulation

        Returns:
        --------
        capacity_dict: dictionary
            keys are strings, the reactor names
            the values are a numpy array with one element for
            each time step in the scenario, indicating how
            much capacity is deployed for each key during the
            simulation.
        """
        if reactors is None:
            reactors = self.reactors
        reactors = np.atleast_1d(reactors)
        capacity_factors = self.get_capacity_factors(reactors)
        power_dict = self.get_generated_power(reactors, return_sum=False)
        capacity_dict = {}
        for reactor in reactors:
            cf = capacity_factors[reactor]
            if cf == 0 or np.isnan(cf):
                raise ValueError(
                    f"Capacity factor for reactor '{reactor}' is zero or NaN."
                    " Cannot compute deployed capacity."
                )
            capacity_dict[reactor] = power_dict[reactor] / cf
        if return_sum:
            return np.sum(list(capacity_dict.values()), axis=0)
        return capacity_dict
    
    def get_fuel_mass_and_enrichment(
        self,
        reactors: str | list[str] | None = None,
        return_sum: bool = True
    ) -> tuple[np.ndarray, np.ndarray] | \
            dict[str, tuple[np.ndarray, np.ndarray]]:
        fuel_mass = self.stock_fuel_demand(reactors, return_sum=return_sum)
        enrichment = self.get_enrichments(reactors)
        return fuel_mass, enrichment

    def stock_fuel_demand(
        self, reactors: str | list[str] | None = None, return_sum: bool = True
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Annual fuel mass demand from one or more reactors.

        Parameters
        ----------
        reactors : str or list of str
            Reactor(s) to calculate fuel demand for.
        return_sum : bool
            If True, returns a single array summed over all reactors.

        Returns
        -------
        fuel_mass : np.ndarray or dict[str, np.ndarray]
            Yearly fuel mass per reactor, or total if return_sum=True.
        """
        if reactors is None:
            reactors = self.reactors
        reactors = np.atleast_1d(reactors)
        flows_dict = self.flows

        fuel_mass_dict = {}
        for reactor in reactors:
            if reactor not in flows_dict["reactor_in"]["TOTAL"]:
                raise ValueError(
                    f"Reactor '{reactor}' not found in flows data.")
            fuel_mass_dict[reactor] = np.array(
                flows_dict["reactor_in"]["TOTAL"][reactor]
            )

        if return_sum:
            return np.sum(list(fuel_mass_dict.values()), axis=0)
        return fuel_mass_dict

    def stock_fuel_discharged(
        self, reactors: str | list[str] | None = None, return_sum: bool = True
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Annual discharged fuel mass from one or more reactors.

        Parameters
        ----------
        reactors : str or list of str
            Reactor(s) to calculate discharged fuel for.
        return_sum : bool
            If True, returns a single array summed over all reactors.

        Returns
        -------
        discharged_mass : np.ndarray or dict[str, np.ndarray]
            Yearly discharged fuel mass per reactor, or total
            if return_sum=True.
        """
        if reactors is None:
            reactors = self.reactors
        reactors = np.atleast_1d(reactors)
        flows_dict = self.flows

        fuel_mass_dict = {}
        for reactor in reactors:
            if reactor not in flows_dict["reactor_out"]["TOTAL"]:
                raise ValueError(
                    f"Reactor '{reactor}' not found in flows data.")
            fuel_mass_dict[reactor] = np.array(
                flows_dict["reactor_out"]["TOTAL"][reactor]
            )

        if return_sum:
            return np.sum(list(fuel_mass_dict.values()), axis=0)
        return fuel_mass_dict

    def get_enrichments(
        self, reactors: str | list[str] | None = None
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Annual enrichment (U-235 mass fraction) for fuel delivered
        to one or more reactors. Always returns one array per reactor.

        Parameters
        ----------
        reactors : str or list of str
            Name(s) of the reactors to analyze.

        Returns
        -------
        enrichment : dict[str, np.ndarray]
            Annual enrichment time series for each reactor, or a total array.
        """
        # Convert reactor to a numpy array
        if reactors is None:
            reactors = self.reactors
        reactors = np.atleast_1d(reactors)
        flows_dict = self.flows
        enrichments = {}
        for inp in self.inputs:
            if ".input" in str(inp):
                input_dict = json.loads(inp.read_text())
        for reactor in reactors:
            # Find the reactor spec in input_dict
            match = next(
                (r for r in input_dict["types"]
                 ["reactor"] if r["name"] == reactor),
                None,
            )
            if match is None:
                raise ValueError(f"Reactor '{reactor}' not found in input.")

            if "fuel" not in match:
                print(
                    f"Reactor {reactor} does not take traditional fuel. "
                    f"Returning zeros."
                )
                enrichments[reactor] = np.zeros_like(
                    flows_dict["reactor_in"]["TOTAL"][reactor]
                )
                continue

            fuel_material_recipe = match["fuel"]

            # Build composition
            fuel_composition = {}
            for fuel_mat in fuel_material_recipe:
                for event in input_dict["events"]:
                    if fuel_mat in event["parameters"]:
                        comp = event["parameters"][fuel_mat]
                        for nuclide, mass in comp.items():
                            comp_mass = fuel_material_recipe[fuel_mat] * mass
                            fuel_composition[nuclide] = (
                                fuel_composition.get(nuclide, 0.0) + comp_mass
                            )

            u235_mass = fuel_composition.get("u235", 0.0)
            u_mass = sum(m for n, m in fuel_composition.items()
                         if n.startswith("u"))
            enrichment = u235_mass / u_mass if u_mass > 0 else 0.0

            enrichments[reactor] = np.full_like(
                flows_dict["reactor_in"]["TOTAL"][reactor], enrichment
            )
        return enrichments

    def stock_fuel_resources(
        self,
        reactors: str | list[str] | None = None,
        natu_assay: float = None,
        tails_assay: float = None,
        return_sum: bool = True,
        split_cat: bool = False,
        cascade_splits=[0.1, 0.2],
    ):
        """
        Compute natural-uranium feed, enrichment tails, and SWU
        requirements for one or more reactors.

        Parameters:
        ----------
        reactors : str or list[str]
            Prototype name(s).
        natu_assay : float
            Enrichment of the feed (typically natural uranium) as a decimal.
        tails_assay : float
            Enrichment of the tails material as a decimal.
        return_sum : bool, optional
            If True, returns the sum across reactors (default True).
        split_cat : bool, optional
            If True, return tails and SWU split by cascade stage;
            otherwise return totals (default False).
        cascade_splits : list of float
            Intermediate enrichments (as decimals) that define cascade stages.
            Defaults to [0.1, 0.2].

        Returns:
        -------
        dict[str, dict[str, np.ndarray] | np.ndarray]
            Dictionary with keys 'natu', 'tails', and 'swu'.
            For each entry the structure matches the corresponding
            stock_fuel_* helper that it replaces.
        """

        if not cascade_splits:
            cascade_splits = [np.inf]

        # Reactor list
        if reactors is None:
            reactors = self.reactors
        reactors = np.atleast_1d(reactors)

        # Mass and enrichment arrays
        fuel_mass, enr = self.get_fuel_mass_and_enrichment(
            reactors, return_sum=False)

        # Cache cascade splits by unique enrichment
        cache = {}
        for reactor in reactors:
            for enrichment in enr[reactor]:
                if enrichment > 0:
                    key = round(float(enrichment), 8)
                    if key not in cache:
                        cascade = enrichment_cascade(
                            feed_enr=natu_assay,
                            prod_enr=enrichment,
                            tail_enr=tails_assay,
                            cascade_splits=cascade_splits,
                        )
                        # For natural uranium, use only the first stage,
                        # because the rest is reused by the next stage
                        cache[key] = {
                            "natu": cascade["feed"][0],
                            "tails": np.asarray(cascade["tails"], dtype=float),
                            "swu": np.asarray(cascade["swu"], dtype=float),
                        }

        # Ensure a consistent number of stages
        lengths = [len(v["tails"]) for v in cache.values()]
        assert (
            len(set(lengths)) == 1
        ), "All cascades must have the same number of stages."
        n_stages = lengths[0]
        zeros = np.zeros(n_stages)

        res = {"natu": {}, "tails": {}, "swu": {}}

        for reactor in reactors:
            # Natural-uranium feed
            r_natu = np.array(
                [
                    cache.get(round(float(e), 8), {"natu": 0})[
                        "natu"] if e > 0 else 0
                    for e in enr[reactor]
                ],
                dtype=float,
            )
            res["natu"][reactor] = r_natu.T * fuel_mass[reactor]

            # Tails
            r_tails = np.array(
                [
                    (
                        cache.get(round(float(e), 8), {
                                  "tails": zeros})["tails"]
                        if e > 0
                        else zeros
                    )
                    for e in enr[reactor]
                ],
                dtype=float,
            )
            tails_val = r_tails.T * fuel_mass[reactor]
            if not split_cat:
                tails_val = np.sum(tails_val, axis=0)
            res["tails"][reactor] = tails_val

            # SWU
            r_swu = np.array(
                [
                    (
                        cache.get(round(float(e), 8), {"swu": zeros})["swu"]
                        if e > 0
                        else zeros
                    )
                    for e in enr[reactor]
                ],
                dtype=float,
            )
            swu_val = r_swu.T * fuel_mass[reactor]
            if not split_cat:
                swu_val = np.sum(swu_val, axis=0)
            res["swu"][reactor] = swu_val

        if return_sum:
            return {k: sum(v.values()) for k, v in res.items()}
        return res

    def stock_fuel_natu(
        self,
        reactors: str | list[str] | None = None,
        natu_assay: float = None,
        tails_assay: float = None,
        return_sum: bool = True,
        cascade_splits=[0.1, 0.2],
    ):
        """
        Compute natural uranium requirements for one or more reactors.

        Parameters:
        ----------
        reactors : str or list[str]
            Prototype name(s).
        natu_assay : float
            Enrichment of the feed (typically natural uranium) as a decimal.
        tails_assay : float
            Enrichment of the tails material as a decimal.
        return_sum : bool, optional
            If True, returns the sum across reactors (default True).
        cascade_splits : list of float
            Intermediate enrichments (as decimals) that define cascade stages.
            Defaults to [0.1, 0.2].

        Returns:
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
        cascade_splits=[0.1, 0.2],
    ):
        """
        Compute enrichment tails for one or more reactors.

        Parameters:
        ----------
        reactors : str or list[str]
            Prototype name(s).
        natu_assay : float
            Enrichment of the feed (typically natural uranium) as a decimal.
        tails_assay : float
            Enrichment of the tails material as a decimal.
        return_sum : bool, optional
            If True, returns the sum across reactors (default True).
        split_cat : bool, optional
            If True, return tails split by cascade stage; otherwise
            return total tails per reactor (default False).
        cascade_splits : list of float
            Intermediate enrichments (as decimals) that define cascade stages.
            Defaults to [0.1, 0.2].

        Returns:
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
        cascade_splits=[0.1, 0.2],
    ):
        """
        Compute SWU requirements for one or more reactors.

        Parameters:
        ----------
        reactors : str or list[str]
            Prototype name(s).
        natu_assay : float
            Enrichment of the feed (typically natural uranium) as a decimal.
        tails_assay : float
            Enrichment of the tails material as a decimal.
        return_sum : bool, optional
            If True, returns the sum across reactors (default True).
        split_cat : bool, optional
            If True, return SWU split by cascade stage; otherwise
            return total SWU per reactor (default False).
        cascade_splits : list of float
            Intermediate enrichments (as decimals) that define cascade stages.
            Defaults to [0.1, 0.2].

        Returns:
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

    # Old functions

    def power_generated(self, reactor: str):
        """
        retrieves the power generation data from the operations json output

        Parameters:
        -----------
        reactor: str
            the name of the reactor type to get the generation data for

        Returns:
        -----------
        numpy.array<float>
            the annual power generation info for the reactor type

        """

        operations_dict = self.operations

        return np.array(operations_dict["reactors"][reactor])

    def fuel_fabricated(self, reactor: str):
        """
         retrieves the fuel fabrication data from the flows json output

        Parameters:
        -----------
        reactor: str
            the name of the reactor type to get the mass flow data for

        Returns:
        -----------
        numpy.array<float>
            the annual fuel fabrication info for the reactor type

        """

        flows_dict = self.flows

        return np.array(flows_dict["reactor_in"]["TOTAL"][reactor])

    def reprocessed_mass(
        self,
        reprocess_plants: str | list[str] | None = None,
        return_sum: bool = True
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
         retrieves the total reprocessing utilization data from the
         flows json output

        Parameters:
        -----------
        reprocess_plants : str or list of str
            the name(s) of the reprocessing plant type to get the mass
            flow data for
        return_sum : bool
            If True, returns a single array summed over all reprocessing
            plants

        Returns:
        -----------
        reprocessed_mass : np.ndarray or dict[str, np.ndarray]
            the annual reprocessing info for the reprocessing plant
            type(s), or total if return_sum=True

        """
        if reprocess_plants is None:
            reprocess_plants = self.reprocess_plants
        reprocess_plants = np.atleast_1d(reprocess_plants)
        flows_dict = self.flows

        reprocessed_mass_dict = {}
        for reprocess_plant in reprocess_plants:
            if reprocess_plant not in flows_dict["reprocessing_out"]:
                raise ValueError(
                    f"Reprocessing Plant '{reprocess_plant}'"
                    f" not found in flows data"
                )
            reprocessed_mass_dict[reprocess_plant] = np.sum(
                np.array(
                    list(flows_dict["reprocessing_out"]
                         [reprocess_plant].values())
                ),
                axis=0,
            )

        if return_sum:
            return np.sum(list(reprocessed_mass_dict.values()), axis=0)

        return reprocessed_mass_dict

    def stock_waste_mass(
            self,
            material: str | list[str] | None = None,
            storage: str = 'waste',
            return_sum: bool = True) -> np.ndarray | dict[str, np.ndarray]:
        """
        Retrieves the cumulative waste data from the stocks json output and
        calculates the annual flow data

        Parameters:
        -----------
        material: str or list of str
            the name of the material type to get the cumulative waste
            mass data for; if None, returns all materials
        storage: str
            the name of the storage type where the material is stored
        return_sum: bool
            if True, returns a single array summed over all materials;
            otherwise, returns a dictionary with keys as material names
            and values as arrays of cumulative mass

        Returns:
        -----------
        numpy.array<float> or dict[str, np.ndarray]
            the annual waste mass for the specified material
            or all materials if material is None
            if return_sum is True, returns a single array summed
            over all materials; otherwise, returns a dictionary
            with keys as material names and values as arrays
            of annual mass flows

        """

        stocks_dict = self.stocks
        if storage not in stocks_dict:
            raise ValueError(f"Storage '{storage}' not found in stocks data")
        storage_dict = stocks_dict[storage]

        # Get material list
        if material is None:
            material = list(storage_dict.keys())
        elif isinstance(material, str):
            material = [material]
        material = np.atleast_1d(material)

        cumulative_mass_dict = {}
        for mat in material:
            if mat not in storage_dict:
                raise ValueError(
                    f"Material '{mat}' not found in stocks data for "
                    f"storage '{storage}'"
                )
            cumulative_mass_dict[mat] = np.array(
                storage_dict[mat]
            )

        mass_flow_dict = {}
        for mat in cumulative_mass_dict.keys():
            mass_flow_dict[mat] = np.zeros(len(cumulative_mass_dict[mat]))
            mass_flow_dict[mat][0] = cumulative_mass_dict[mat][0]
            for y in range(1, len(cumulative_mass_dict[mat])):
                mass_flow_dict[mat][y] = cumulative_mass_dict[mat][y] - \
                    cumulative_mass_dict[mat][y-1]

        if return_sum:
            return np.sum(
                np.array(list(mass_flow_dict.values())), axis=0
            )

        return mass_flow_dict
