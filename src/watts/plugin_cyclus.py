# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from functools import lru_cache
from pathlib import Path
from typing import Callable, Mapping, List, Optional

import sqlite3 as lite
import numpy as np
import os

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import Plugin, PluginGeneric, _find_executable
from .results import Results, ExecInfo
from .enrichment_utils import enrichment_cascade


class ResultsCyclus(Results):
    """Cyclus simulation restuls

    Parameters:
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
        """Returns a CyclusOutput object linked to the output SQLite file."""
        return CyclusOutput(self.sqlite_file)

    @property
    def sqlite_file(self) -> Path:
        """Returns the path to the output SQLite file from the simulation."""
        path_list = [
            path for path in self.outputs if path.name.endswith("sqlite")]
        assert len(path_list) == 1
        return path_list[0]

    @property
    def prototypes(self):
        """Returns a list of unique prototype names from the simulation."""
        return list(set(self.obj.agent_dict.values()))

    @property
    def reactors(self):
        """Returns a dictionary of agent IDs and their prototype names
        for reactor facilities."""
        return self.obj.get_facility_agents("reactor")

    @property
    def commodities(self) -> List[str]:
        """Returns a list of unique commodity names used in the simulation."""
        query = self.obj.cur.execute(
            "SELECT distinct(commodity) FROM transactions")
        return [commod["commodity"] for commod in query]

    @property
    def time_dict(self) -> dict:
        """Returns a dictionary with simulation time metadata (start
        year/month, duration, etc.)."""
        return self.obj.get_times()

    @property
    def mass_flow_dict(self) -> dict:
        """Returns a dictionary mapping commodities to their yearly
        mass flows."""
        arr = self.obj.get_fuel_demands(self.commodities)
        dictionary = {}
        for indx in range(len(arr)):
            dictionary[self.commodities[indx]] = arr[indx, :]
        return dictionary


class PluginCyclus(PluginGeneric):
    """Plugin for running Cyclus

    #! In addition to the basic capability to use placeholders in
    MCNP input files, this class also provides a custom Jinja
    filter called `expand_element that allows you to specify natural
    elements in MCNP material definitions and have them automatically
    expanded based on what isotopes appear in the xsdir file.

    Parameters:
    ----------
    template_file
        Templated Cyclus input (.xml)
    executable
        Path to Cyclus executable
    show_stdout
        Whether to display output from stdout when Cyclus is run
    show_stderr
        Whether to display output from stderr when Cyclus is run

    Attributes
    ----------
    executable
        Path to Cyclu executable
    execute_command
        List of command-line arguments used to call the executable

    """

    def __init__(
        self,
        template_file: str,
        executable: PathLike = "cyclus",
        show_stdout: bool = False,
        show_stderr: bool = False,
    ):
        executable = _find_executable(executable, "PATH")
        output_name = template_file.replace(".xml", ".sqlite")
        super().__init__(
            executable,
            ["{self.executable}", "{self.input_name}", "-o", output_name],
            template_file,
            plugin_name="Cyclus",
            show_stdout=show_stdout,
            show_stderr=show_stderr,
            unit_system="si",
        )
        self.input_name = "cyclus_input"


class CyclusOutput:
    def __init__(self, path, by_proto=True):
        """
        Class to access and browse an output file from Cyclus.
        Output file MUST be an SQLite database (.sqlite)

        Parameters:
        -----------
        path: str
            path to output file, including file name
        """
        assert os.path.exists(path), "File does not exist."
        ext = os.path.splitext(path)
        assert ext[-1] == ".sqlite", "File extension has to be .sqlite"
        con = lite.connect(path)
        con.row_factory = lite.Row
        self.cur = con.cursor()
        # get times
        td = self.get_times()
        for k, v in td.items():
            setattr(self, k, v)
        self.nucids = self.get_nucids()
        self.agent_dict = self.get_facility_agents()
        self.reactors = np.unique(
            list(self.get_facility_agents("reactor").values()))

    def get_facility_agents(self, spec_keywords=None):
        """Returns all facility agents in the simulation

        Parameters:
        ----------
        spec_keywords : str, optional
            If provided, filters facility agents whose specification
            string (Spec) contains this keyword. Used to isolate a
            specific type of facility, such as 'reactor', based on
            its Cyclus specification.

        Returns:
        -------
        dict
            Dictionary mapping agent ID (int) to prototype name (str).
        """
        if not spec_keywords:
            query = self.sql_query(
                '''SELECT distinct(agentid), prototype
                   FROM agententry
                   WHERE kind=="Facility"'''
            )
        else:
            query = self.sql_query(
                f"""SELECT distinct(agentid), prototype
                    FROM agententry
                    WHERE kind=="Facility" and spec
                    LIKE "%{spec_keywords}%" --case-insensitive"""
            )
        agents = {q["agentid"]: q["prototype"] for q in query}
        return agents

    def process_prototype(self, protos, get_isotopics):
        """
        Process mass flows and compute stock over time for a given prototype.

        Parameters:
        ----------
        protos : str or list of str
            Prototype name(s) to process.
        get_isotopics : bool
            If True, includes isotopic mass data; otherwise only total mass.

        Returns:
        -------
        tuple
            (prototype name, flow dictionary, cumulative stock array)
        """
        print(f"\tProcessing prototype: {protos}")
        flow_dict = {}
        for facility_type in ["receiverid", "senderid"]:
            key = facility_type.replace("erid", "ing")
            flow_dict[key] = {}
            # get ids
            if isinstance(protos, list):
                proto_string = ", ".join(
                    [f'"{str(proto)}"' for proto in protos])
                query = self.sql_query(
                    f"""SELECT agentid
                        FROM agententry
                        WHERE prototype
                        IN ({proto_string})"""
                )
            else:
                query = self.sql_query(
                    f'''SELECT agentid
                        FROM agententry
                        WHERE prototype == "{protos}"'''
                )
            ids = [q["agentid"] for q in query]
            id_str = ", ".join([str(id) for id in ids])
            query = self.sql_query(
                f"""SELECT distinct(commodity)
                    FROM transactions
                    WHERE {facility_type}
                    IN ({id_str})"""
            )
            trade_commods = [q["commodity"] for q in query]

            for commod in trade_commods:
                if not get_isotopics:
                    query = self.sql_query(
                        f"""SELECT sum(quantity), time
                            FROM transactions
                            INNER JOIN resources
                            ON transactions.resourceid = resources.resourceid
                            WHERE {facility_type} in ({id_str})
                            AND commodity=="{commod}"
                            GROUP BY time"""
                    )
                    flow_dict[key][commod] = self.get_yearly_sum(
                        self.query_to_array(
                            query,
                            self.duration,
                            nucids=[],
                            time_label="time",
                            value_label="sum(quantity)",
                        )
                    )
                else:
                    # isotopics
                    query = self.sql_query(
                        f"""SELECT time, nucid, sum(quantity * massfrac)
                            AS nucmass
                            FROM transactions
                            JOIN resources
                            ON transactions.resourceid = resources.resourceid
                            JOIN compositions on
                            resources.qualid = compositions.qualid
                            WHERE {facility_type} in ({id_str})
                            AND commodity=="{commod}"
                            GROUP BY time, nucid"""
                    )
                    flow_dict[key][commod] = self.get_yearly_sum(
                        self.query_to_array(
                            query,
                            self.duration,
                            nucids=self.nucids,
                            time_label="time",
                            value_label="nucmass",
                        )
                    )

        # Calculate the stock for this prototype
        agent_stock = np.cumsum(
            sum(flow_dict["receiving"].values()) -
            sum(flow_dict["sending"].values())
        )

        return protos, flow_dict, agent_stock

    def process_agent(self, id, get_isotopics):
        """
        Process mass flows and compute stock over time for a given agent ID.

        Parameters:
        ----------
        id : int
            Agent ID to process.
        get_isotopics : bool
            If True, includes isotopic mass data; otherwise only total mass.

        Returns:
        -------
        tuple
            (agent ID, flow dictionary, cumulative stock array)
        """

        flow_dict = {}
        for facility_type in ["receiverid", "senderid"]:
            key = facility_type.replace("erid", "ing")
            flow_dict[key] = {}
            query = self.sql_query(
                f"""SELECT distinct(commodity)
                                   FROM transactions
                                   WHERE {facility_type}=={id}"""
            )
            trade_commods = [q["commodity"] for q in query]

            for commod in trade_commods:
                if not get_isotopics:
                    query = self.sql_query(
                        f"""SELECT sum(quantity), time
                            FROM transactions
                            INNER JOIN resources
                            ON transactions.resourceid = resources.resourceid
                            WHERE {facility_type}=={id}
                            AND commodity=="{commod}"
                            GROUP BY time"""
                    )
                    flow_dict[key][commod] = self.get_yearly_sum(
                        self.query_to_array(
                            query,
                            self.duration,
                            nucids=[],
                            time_label="time",
                            value_label="sum(quantity)",
                        )
                    )
                else:
                    # isotopics
                    query = self.sql_query(
                        f"""SELECT time, nucid, sum(quantity * massfrac)
                            AS nucmass
                            FROM transactions
                            JOIN resources
                            ON transactions.resourceid = resources.resourceid
                            JOIN compositions on
                            resources.qualid = compositions.qualid
                            WHERE {facility_type}=={id}
                            AND commodity=="{commod}"
                            GROUP BY time, nucid"""
                    )
                    flow_dict[key][commod] = self.get_yearly_sum(
                        self.query_to_array(
                            query,
                            self.duration,
                            nucids=self.nucids,
                            time_label="time",
                            value_label="nucmass",
                        )
                    )

        # Calculate the stock for this agent
        agent_stock = np.cumsum(
            sum(flow_dict["receiving"].values()) -
            sum(flow_dict["sending"].values())
        )

        return id, flow_dict, agent_stock

    def get_agent_flow_and_stock_dict(self, by_proto, get_isotopics=False):
        """
        Returns flow and stock dictionaries by prototype or agent.

        Parameters:
        ----------
        by_proto : bool
            If True, groups by prototype; otherwise, by individual agent.
        get_isotopics : bool, optional
            If True, includes isotopic mass data. Default is False

        Returns:
        -------
        tuple
            (flow_dict, stock_dict) indexed by prototype or agent ID.
        """

        agent_flow_dict = {}
        agent_stock_dict = {}

        count = 1
        uniq_protos = set(self.agent_dict.values())

        if by_proto:
            print(f"Going through {len(uniq_protos)} prototypes.")
            for proto in uniq_protos:
                proto, flow_dict, agent_stock = self.process_prototype(
                    proto, get_isotopics
                )
                agent_flow_dict[proto] = flow_dict
                agent_stock_dict[proto] = flow_dict
                print(f"\tCompleted prototype {count}/{len(uniq_protos)}")
                count += 1
        else:
            print(f"Going through {len(self.agent_dict)} agents.")
            for id, proto in self.agent_dict.items():
                id, flow_dict, agent_stock = self.process_agent(
                    id, proto, get_isotopics
                )
                agent_flow_dict[id] = flow_dict
                agent_stock_dict[id] = flow_dict
                print(f"\tCompleted agent {count}/{len(self.agent_dict)}")
                count += 1

        return agent_flow_dict, agent_stock_dict

    # --------------- Global Utility Functions ---------------

    def sql_query(self, query_str: str):
        """
        Execute a SQL query linked to the current database and return the result

        Parameters:
        -----------
        query_str: str
            SQL query to be executed
        """
        query = self.cur.execute(query_str).fetchall()
        return query

    @staticmethod
    def query_to_array(
        query_result,
        duration,
        nucids=[],
        time_label="entertime",
        value_label=""
    ):
        """
        Transform the results from a specified data query of the SQLite
        into a numpy array.
        Parameters:
        -----------
        query_result: list
            SQLite query for database
        duration: int
            number of time steps
        nucids: list
            list of nuclide keys
        time_label: str
            name of column to indicate time in the table
            default = 'entertime'
        value_label: str
            how to treat the values of interest, default = '',
            potential input is 'sum(quantity)'

        Returns:
        -------
        np.ndarray
            Array of shape (duration,) or (duration, len(nucids)), depending on
            whether isotopic resolution is requested.
        """
        if len(nucids) != 0:
            # isotopic mass
            nucids = list(nucids)
            val = np.zeros((duration, len(nucids)))
            assert "NucId" in query_result[0].keys(), print(
                query_result[0].keys())
            assert value_label != ""
            for row in query_result:
                val[row[time_label], nucids.index(
                    row["NucId"])] += row[value_label]
        else:
            val = np.zeros(duration)
            for row in query_result:
                if not value_label:
                    val[row[time_label]] += 1
                else:
                    val[row[time_label]] += row[value_label]
        return np.array(val)

    @staticmethod
    def get_yearly_sum(arr):
        """
        Convert monthly time series data into yearly sums, with
        initial alignment.

        This function:
        - Sums values over consecutive 12-month periods
        - Prepends an initial 0.0 as a placeholder for the year
          before data begins
        - Returns one value per year, excluding the final year
          of data

        Parameters:
        ----------
        arr : array-like
            1D array of monthly values

        Returns:
        -------
        np.ndarray
            1D array of yearly sums, length = floor(len(arr) / 12),
            plus one initial 0
        """
        arr = np.asarray(arr)
        num_years = (len(arr) // 12) * 12  # truncate to full years
        yearly = arr[:num_years].reshape(-1, 12).sum(axis=1)
        return np.insert(yearly[:-1], 0, 0.0)  # remove last year, prepend 0

    # --------------- Basic data extraction functions ---------------

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
        duration = self.sql_query(
            """SELECT InitialYear, InitialMonth, Duration
                                  FROM Info"""
        )[0]
        init_year = duration["InitialYear"]
        init_month = duration["InitialMonth"]
        duration = duration["Duration"]
        time = init_year + (np.arange(duration) + init_month - 1) / 12
        years = time
        return {
            "init_year": init_year,
            "init_month": init_month,
            "duration": duration,
            "years": years,
        }

    def get_nucids(self):
        """
        Returns the set of all nuclide IDs present in the flow dictionary.

        Parameters:
        ----------
        flow_dict : dict
            Dictionary of flow data, typically from
            `get_agent_flow_and_stock_dict`.

        Returns:
        -------
        set
            Set of integer nuclide IDs appearing in any time step
            of the flow data.
        """
        query = self.sql_query(
            """SELECT distinct(nucid)
                                FROM compositions"""
        )
        nucids = np.array(sorted([q["nucid"] for q in query]))
        return nucids

    def get_fuel_demands(self, fuel_forms=[]):
        """

        Parameters:
        -----------
        fuel_forms: list of strs
            name of the different commodities for reactor fuel

        Returns:
        --------
        fuel_flow_array: 2D numpy array
            each row (axis 0) corresponds to a fuel form in the
            fuel_forms list (index in fuel_forms corresponds to
            the 0 axis location in fuel_flow_array), the columns
            (axis 1) correspond to each year of the simulation,
            with the data being the yearly totals of
            each fuel form
        """
        num_years = len(self.get_yearly_sum(np.zeros(self.duration)))
        fuel_flow_array = np.zeros((len(fuel_forms), num_years))
        for indx, ff in enumerate(fuel_forms):
            query = self.sql_query(
                """SELECT sum(quantity), time
                FROM transactions
                INNER JOIN resources
                ON transactions.resourceid = resources.resourceid
                WHERE Commodity="%s"
                GROUP BY time"""
                % ff
            )
            fuel_flow_array[indx, :] = np.array(
                self.get_yearly_sum(
                    self.query_to_array(
                        query,
                        self.duration,
                        time_label="time",
                        value_label="sum(quantity)",
                    )
                )
            )
        return fuel_flow_array

    def get_commodity_into(self, proto_name=None, agentids=None):
        """
        Get the list of unique incoming commodity names for a
        given prototype or agent ID.

        Parameters:
        ----------
        proto_name : str, optional
            Name of the prototype. If specified, `agentid` must be None.
        agentids : int or list of int, optional
            Agent ID(s). If specified, `proto_name` must be None.

        Returns:
        -------
        list of str
            List of commodity names received by the specified agent(s).
        """
        # there can only be one
        assert (proto_name is not None) != (agentids is not None)
        if proto_name:
            # get the agentids
            agentids = self.get_proto_ids(proto_name)
        else:
            if not isinstance(agentids, list):
                agentids = [agentids]
        assert len(agentids) > 0, "No agentid found"
        csv = ",".join([str(agentid) for agentid in agentids])
        query = self.sql_query(
            f"""SELECT distinct(commodity)
            FROM transactions
            WHERE receiverid
            IN ({csv})"""
        )
        return [q["commodity"] for q in query]

    def get_commodity_out_of(self, proto_name=None, agentids=None):
        """
        Get the list of unique outgoing commodity names for a given
        prototype or agent ID.

        Parameters:
        ----------
        proto_name : str, optional
            Name of the prototype. If specified, `agentid` must be None.
        agentids : int or list of int, optional
            Agent ID(s). If specified, `proto_name` must be None.

        Returns:
        -------
        list of str
            List of commodity names sent by the specified agent(s).
        """
        # there can only be one
        assert (proto_name is not None) != (agentids is not None)
        if proto_name:
            # get the agentids
            agentids = self.get_proto_ids(proto_name)
        else:
            if not isinstance(agentids, list):
                agentids = [agentids]
        assert len(agentids) > 0, "No agentid found"
        csv = ",".join([str(agentid) for agentid in agentids])
        query = self.sql_query(
            f"""SELECT distinct(commodity)
            FROM transactions
            WHERE senderid IN ({csv})"""
        )
        return [q["commodity"] for q in query]

    def get_proto_ids(self, proto_name):
        """
        Get agent IDs corresponding to one or more prototype names.

        Parameters:
        ----------
        proto_name : str or list of str
            Prototype name or list of names.

        Returns:
        -------
        list of int or dict of list[int]
            If input is a single prototype, returns a flat list of agent IDs.
            If input is a list, returns a dictionary mapping prototype names
            to lists of agent IDs.
        """

        want_flat = isinstance(proto_name, str)
        prototypes = [proto_name] if want_flat else list(proto_name)

        if not prototypes:  # handles None, "", empty list
            return [] if want_flat else {}

        # Build a CSV of quoted prototype names:  "rx1", "rx2", …
        proto_csv = ", ".join(f'"{prototype}"' for prototype in prototypes)

        # Query the database for agent IDs associated with the prototypes
        rows = self.sql_query(
            f"""
            SELECT prototype, agentid
            FROM agententry
            WHERE prototype IN ({proto_csv})
        """
        )

        # If we want a flat list, return it directly
        if want_flat:
            return [r["agentid"] for r in rows]

        # Otherwise, return a dict mapping prototypes to lists of agent IDs
        out = {prototype: [] for prototype in prototypes}
        for row in rows:
            out[row["prototype"]].append(row["agentid"])
        return out

    def get_commodities(self):
        """
        Return all unique commodity names used in the simulation.

        Returns:
        -------
        list of str
            List of distinct commodity names from the transactions table.
        """
        query = self.sql_query(
            """SELECT distinct(commodity)
            FROM transactions"""
        )
        return [q["commodity"] for q in query]

    def get_mass_flow(self, commodity_name):
        """
        Get the mass flow of a commodity in the simulation

        Parameters:
        -----------
        commodity_name: str
            name of the commodity of interest

        Returns:
        --------
        mass_flow: numpy array
            length is the number of years in a simulations (i.e.,
            length of arr/12) with the data from arr summed up for each
            year
        """
        query = self.sql_query(
            f"""SELECT sum(quantity), time
                FROM transactions
                INNER JOIN resources
                ON transactions.resourceid = resources.resourceid
                WHERE Commodity="{commodity_name}"
                GROUP BY time"""
        )
        return np.array(
            self.get_yearly_sum(
                self.query_to_array(query, self.duration,
                                    "time", "sum(quantity)")
            )
        )

    # --------------- Direct fuel-related functions ---------------

    def get_deployment_dict(
        self,
        prototypes: str | list[str] | None = None,
        return_sum: bool = False,
        yearly: bool = True,
        reactors: str | list[str] | None = None,
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Determines the amount of deployed power for each time step for
        each reactor prototype

        Parameters:
        -----------
        prototypes: list of str
            names of reactor prototypes in the simulation
        return_sum: bool
            if True, returns a single array summed over all prototypes,
        yearly: bool
            if True, returns yearly sums instead of monthly
        reactors: list of str
            alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.

        Returns:
        --------
        power_dict: dictionary
            keys are strings, the reactor names and 'legacy',
            the values are a numpy array with one element for
            each time step in the scenario, indicating how
            much power is deployed for each key during the
            simulation.
        """
        # Convert reactors/prototypes to a numpy array
        assert (
            prototypes is None or reactors is None
        ), f"Either 'prototypes' or 'reactors' must be specified, \
            but not both: prototypes={prototypes}, reactors={reactors}"
        if prototypes is None and reactors is None:
            prototypes = self.reactors
        elif reactors is not None:
            prototypes = reactors
        prototypes = np.atleast_1d(prototypes)

        # Query the database for reactor deployments with non-zero power
        query = self.sql_query(
            """SELECT prototype, entertime, lifetime, Spec, value
               FROM agententry
               INNER JOIN timeseriespower
               ON agententry.agentid = timeseriespower.agentid
               WHERE agententry.spec
               LIKE "%Reactor"
               AND value != 0
               GROUP BY agententry.agentid"""
        )

        power_dict = {prototype: np.zeros(
            self.duration) for prototype in prototypes}
        pow_cap_dict = {prototype: 0 for prototype in prototypes}

        for row in query:
            proto = row["prototype"]
            t0 = row["entertime"]
            t1 = row["lifetime"]

            for reactor in prototypes:
                if reactor in proto:
                    key = reactor
                    if reactor == proto:
                        # Want powers in GW
                        pow_cap_dict[reactor] = row["value"] * 1e-3
                    power_dict[key][t0 - 1: t0 + t1 - 1] += row["value"] * 1e-3

        # If yearly is True, convert monthly data to yearly data
        if yearly:
            power_dict = {
                k: np.mean(v.reshape(-1, 12), axis=1)
                for k, v in power_dict.items()
            }

        # If return_sum is True, sum the power across all reactors
        if return_sum:
            # Sum all power arrays in the dictionary
            power_dict = np.sum(list(power_dict.values()), axis=0)
        return power_dict

    def get_fuel_mass_and_enrichment(
        self,
        prototypes: str | list[str] | None = None,
        return_sum: bool = True,
        reactors: str | list[str] | None = None,
    ) -> tuple[np.ndarray, np.ndarray] | \
            dict[str, tuple[np.ndarray, np.ndarray]]:
        """
        Get fuel mass and enrichment over time for one or more prototypes.

        Parameters:
        ----------
        prototypes : str, list of str, or None
            Reactor prototype(s) to analyze. If None, use all reactor types
            in the simulation.
        return_sum : bool
            If True, return summed arrays across all prototypes.
            If False, return per-prototype dict.
        reactors : str or list of str, optional
            alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.

        Returns:
        -------
        tuple or dict
            If return_sum=True, returns
                (fuel_mass_array), {proto: enrichment_array}.
            If return_sum=False, returns
                {proto: (fuel_mass_array, enrichment_array)}.
        """
        fuel_mass = self.stock_fuel_demand(
            prototypes, return_sum=return_sum, reactors=reactors
        )
        enrichment = self.get_enrichments(prototypes, reactors=reactors)
        return fuel_mass, enrichment

    def stock_fuel_demand(
        self,
        prototypes: str | list[str] | None = None,
        return_sum: bool = True,
        reactors: str | list[str] | None = None,
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Annual fuel mass demand from one or more prototypes.

        Parameters:
        ----------
        prototypes : str or list of str
            Reactor prototype(s).
        return_sum : bool
            If True, returns a single array summed over all prototypes.
        reactors : str or list of str, optional
            alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.

        Returns:
        -------
        fuel_mass : np.ndarray or dict[str, np.ndarray]
            Yearly fuel mass per prototype, or total if return_sum=True.
        """
        # Convert reactors/prototypes to a numpy array
        assert (
            prototypes is None or reactors is None
        ), f"Either 'prototypes' or 'reactors' must be specified, \
            but not both: prototypes={prototypes}, reactors={reactors}"
        if prototypes is None and reactors is None:
            prototypes = self.reactors
        elif reactors is not None:
            prototypes = reactors
        prototypes = np.atleast_1d(prototypes)

        # Get agent IDs for the specified prototypes (flat list)
        ids_by_proto = self.get_proto_ids(prototypes)
        all_ids = [aid for ids in ids_by_proto.values()
                   for aid in ids]  # flatten
        id_csv = ",".join(map(str, all_ids))

        # If no IDs found, return empty arrays of the appropriate size
        if not all_ids:
            return (
                np.zeros(self.duration // 12)
                if return_sum
                else {p: np.zeros(self.duration // 12) for p in prototypes}
            )

        # Get relevant commodities (fuel=into) for each prototype
        commods = self.get_commodity_into(agentids=all_ids)
        commod_csv = ",".join(f'"{c}"' for c in commods)

        # Get total received fuel mass per agent per time step
        # Filters transactions by receiver IDs and fuel-related commodities,
        # and groups results by receiver ID and time to get the total quantity
        rows = self.sql_query(
            f"""
            SELECT receiverid, time, SUM(quantity) AS q
            FROM transactions
            JOIN resources USING (resourceid)
            WHERE receiverid IN ({id_csv})
            AND commodity IN ({commod_csv})
            GROUP BY receiverid, time
        """
        )

        # Accumulate monthly quantities
        out = {p: np.zeros(self.duration) for p in prototypes}
        for row in rows:
            rec_id, time, quantity = row["receiverid"], row["time"], row["q"]
            if time >= self.duration:
                continue
            for p, ids in ids_by_proto.items():
                if rec_id in ids:
                    out[p][time] += quantity
                    break

        # Convert to yearly totals
        fuel_mass = {p: self.get_yearly_sum(arr) for p, arr in out.items()}

        # Sum over all prototypes if requested
        if return_sum:
            fuel_mass = np.sum(list(fuel_mass.values()), axis=0)
        return fuel_mass

    def stock_fuel_discharged(
        self,
        prototypes: str | list[str] | None = None,
        return_sum: bool = True,
        reactors: str | list[str] | None = None,
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Annual discharged fuel mass from one or more prototypes.

        Parameters:
        ----------
        prototypes : str or list of str
            Reactor prototype(s).
        return_sum : bool
            If True, returns a single array summed over all prototypes.
        reactors : str or list of str, optional
            alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.

        Returns:
        -------
        discharged_mass : np.ndarray or dict[str, np.ndarray]
            Yearly discharged fuel mass per prototype,
            or total if return_sum=True.
        """
        # Convert reactors/prototypes to a numpy array
        assert (
            prototypes is None or reactors is None
        ), f"Either 'prototypes' or 'reactors' must be specified, \
            but not both: prototypes={prototypes}, reactors={reactors}"
        if prototypes is None and reactors is None:
            prototypes = self.reactors
        elif reactors is not None:
            prototypes = reactors
        prototypes = np.atleast_1d(prototypes)

        # Get agent IDs for the specified prototypes (flat list)
        ids_by_proto = self.get_proto_ids(prototypes)
        all_ids = [aid for ids in ids_by_proto.values()
                   for aid in ids]  # flatten
        id_csv = ",".join(map(str, all_ids))

        # If no IDs found, return empty arrays of the appropriate size
        if not all_ids:
            return (
                np.zeros(self.duration // 12)
                if return_sum
                else {p: np.zeros(self.duration // 12) for p in prototypes}
            )

        # Get relevant commodities (discharged=out of) for each prototype
        commods = self.get_commodity_out_of(agentids=all_ids)
        commod_csv = ",".join(f'"{c}"' for c in commods)

        # Get total discharged fuel mass per agent per time step
        # Filters transactions by sender IDs and fuel-related commodities,
        # and groups results by sender ID and time to get the total quantity
        rows = self.sql_query(
            f"""
            SELECT senderid, time, SUM(quantity) AS q
            FROM transactions
            JOIN resources USING (resourceid)
            WHERE senderid IN ({id_csv})
            AND commodity IN ({commod_csv})
            GROUP BY senderid, time
        """
        )

        # Accumulate monthly quantities
        out = {p: np.zeros(self.duration) for p in prototypes}
        for row in rows:
            rid, t, q = row["senderid"], row["time"], row["q"]
            if t >= self.duration:
                continue
            for p, ids in ids_by_proto.items():
                if rid in ids:
                    out[p][t] += q
                    break

        # Convert to yearly totals
        discharged = {p: self.get_yearly_sum(arr) for p, arr in out.items()}

        # Sum over all prototypes if requested
        if return_sum:
            discharged = np.sum(list(discharged.values()), axis=0)
        return discharged

    def get_enrichments(
        self,
        prototypes: str | list[str] | None = None,
        reactors: str | list[str] | None = None
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Annual enrichment (U-235 mass fraction) for fuel delivered
        to one or more prototypes.
        Always returns one array per prototypes.

        Parameters:
        ----------
        prototypes : str or list of str
            Name(s) of the prototypes to analyze.
        reactors : str or list of str, optional
            alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.

        Returns:
        -------
        enrichment : dict[str, np.ndarray]
            Annual enrichment time series for each prototype, or a total array.
        """
        # Convert reactors/prototypes to a numpy array
        assert (
            prototypes is None or reactors is None
        ), f"Either 'prototypes' or 'reactors' must be specified, \
            but not both: prototypes={prototypes}, reactors={reactors}"
        if prototypes is None and reactors is None:
            prototypes = self.reactors
        elif reactors is not None:
            prototypes = reactors
        prototypes = np.atleast_1d(prototypes)

        # Get agent IDs for the specified prototypes (flat list)
        ids_by_proto = self.get_proto_ids(prototypes)
        all_ids = [aid for ids in ids_by_proto.values()
                   for aid in ids]  # flatten
        id_csv = ",".join(map(str, all_ids))

        # If no IDs found, return empty arrays of the appropriate size
        if not all_ids:
            return {p: np.zeros(self.duration // 12) for p in prototypes}

        # Get relevant commodities (fuel=into) for each prototype
        commods = self.get_commodity_into(agentids=all_ids)
        commod_csv = ",".join(f'"{c}"' for c in commods)

        # SQL: sum total quantity and U-235 mass per receiver and time
        rows = self.sql_query(
            f"""
            SELECT receiverid,
                time,
                SUM(CASE WHEN nucid BETWEEN 922000000 AND 922999999
                            THEN quantity * massfrac ELSE 0 END) AS u_mass,
                SUM(CASE WHEN nucid = 922350000
                            THEN quantity * massfrac ELSE 0 END) AS u235
            FROM transactions
            JOIN resources    USING (resourceid)
            JOIN compositions ON
            resources.qualid = compositions.qualid
            WHERE receiverid IN ({id_csv})
            AND commodity  IN ({commod_csv})
            GROUP BY receiverid, time
        """
        )

        # Accumulate monthly quantities
        u235_by_proto = {p: np.zeros(self.duration) for p in prototypes}
        mass_by_proto = {p: np.zeros(self.duration) for p in prototypes}
        for row in rows:
            rid, t, u_mass, u235 = (
                row["receiverid"],
                row["time"],
                row["u_mass"],
                row["u235"],
            )
            if t >= self.duration:
                continue
            for p, ids in ids_by_proto.items():
                if rid in ids:
                    mass_by_proto[p][t] += u_mass
                    u235_by_proto[p][t] += u235
                    break

        # Convert to yearly total
        for p in prototypes:
            mass_by_proto[p] = self.get_yearly_sum(mass_by_proto[p])
            u235_by_proto[p] = self.get_yearly_sum(u235_by_proto[p])

        enrich = {}
        # Calculate enrichment (U-235 mass fraction)
        for p in prototypes:
            # to remove warnings when dividing by zero
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = np.zeros_like(u235_by_proto[p])
                nonzero = mass_by_proto[p] > 0
                ratio[nonzero] = u235_by_proto[p][nonzero] / \
                    mass_by_proto[p][nonzero]
                enrich[p] = ratio

        return enrich

    # --------------- Advanced data extraction functions ---------------

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
            Enrichment of the feed (typically natural uranium).
        tails_assay : float
            Enrichment of the tails material.
        return_sum : bool, optional
            If True, returns the sum across reactors (default True).
        split_cat : bool, optional
            If True, return tails and SWU split by cascade stage;
            otherwise return totals (default False).
        cascade_splits : list of float
            Intermediate enrichments that define cascade stages.
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
        for p in reactors:
            for e in enr[p]:
                if e > 0:
                    key = round(float(e), 8)
                    if key not in cache:
                        c = enrichment_cascade(
                            feed_enr=natu_assay,
                            prod_enr=e,
                            tail_enr=tails_assay,
                            cascade_splits=cascade_splits,
                        )
                        # For natural uranium, use only the first stage,
                        # because the rest is reused by the next stage
                        cache[key] = {
                            "natu": c["feed"][0],
                            "tails": np.asarray(c["tails"], dtype=float),
                            "swu": np.asarray(c["swu"], dtype=float),
                        }

        # Ensure a consistent number of stages
        lengths = [len(v["tails"]) for v in cache.values()]
        assert (
            len(set(lengths)) == 1
        ), "All cascades must have the same number of stages."
        n_stages = lengths[0]
        zeros = np.zeros(n_stages)

        res = {"natu": {}, "tails": {}, "swu": {}}

        for p in reactors:
            # Natural-uranium feed
            r_natu = np.array(
                [
                    cache.get(round(float(e), 8), {"natu": 0})[
                        "natu"] if e > 0 else 0
                    for e in enr[p]
                ],
                dtype=float,
            )
            res["natu"][p] = r_natu.T * fuel_mass[p]

            # Tails
            r_tails = np.array(
                [
                    (
                        cache.get(round(float(e), 8), {
                                  "tails": zeros})["tails"]
                        if e > 0
                        else zeros
                    )
                    for e in enr[p]
                ],
                dtype=float,
            )
            tails_val = r_tails.T * fuel_mass[p]
            if not split_cat:
                tails_val = np.sum(tails_val, axis=0)
            res["tails"][p] = tails_val

            # SWU
            r_swu = np.array(
                [
                    (
                        cache.get(round(float(e), 8), {"swu": zeros})["swu"]
                        if e > 0
                        else zeros
                    )
                    for e in enr[p]
                ],
                dtype=float,
            )
            swu_val = r_swu.T * fuel_mass[p]
            if not split_cat:
                swu_val = np.sum(swu_val, axis=0)
            res["swu"][p] = swu_val

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
            Enrichment of the feed (typically natural uranium).
        tails_assay : float
            Enrichment of the tails material.
        return_sum : bool, optional
            If True, returns the sum across reactors (default True).
        cascade_splits : list of float
            Intermediate enrichments that define cascade stages.
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
            Enrichment of the feed (typically natural uranium).
        tails_assay : float
            Enrichment of the tails material.
        return_sum : bool, optional
            If True, returns the sum across reactors (default True).
        split_cat : bool, optional
            If True, return tails split by cascade stage; otherwise
            return total tails per reactor (default False).
        cascade_splits : list of float
            Intermediate enrichments that define cascade stages.
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
            Enrichment of the feed (typically natural uranium).
        tails_assay : float
            Enrichment of the tails material.
        return_sum : bool, optional
            If True, returns the sum across reactors (default True).
        split_cat : bool, optional
            If True, return SWU split by cascade stage; otherwise
            return total SWU per reactor (default False).
        cascade_splits : list of float
            Intermediate enrichments that define cascade stages.
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
