# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
from typing import List
import os

import sqlite3 as lite
import xml.etree.ElementTree as ET
import numpy as np
from copy import deepcopy

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import PluginGeneric
from .results import Results, ExecInfo
from .enrichment_utils import enrichment_cascade


class ResultsCyclus(Results):
    """Cyclus simulation results

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
    obj
        CyclusOutput object linked to the output SQLite file.
    sqlite_file
        Path to the Cyclus SQLite output file.
    prototypes
        Unique prototype names from the simulation.
    reactors
        Reactor agent IDs mapped to prototype names.
    commodities
        Unique commodity names used in transactions.
    time_dict
        Simulation time metadata.
    mass_flow_dict
        Yearly mass flows by commodity.
    input_text
        Cyclus input text stored in the output database.
    input_dict
        Cyclus input parsed from XML into a dictionary.
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

    @property
    def input_text(self) -> str:
        """Return the Cyclus input text stored in the output SQLite file."""
        return self.obj.get_input_text()

    @property
    def input_dict(self) -> dict:
        """Return the Cyclus input as a dictionary parsed from XML."""
        return self.obj.get_input_dict()


class PluginCyclus(PluginGeneric):
    """Plugin for running Cyclus

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
        Path to Cyclus executable
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
        output_name = Path(template_file).with_suffix(".sqlite").name
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
    """Access and cache data from a Cyclus SQLite output file.

    Cyclus output databases are immutable for normal analysis. This class
    therefore caches SQL rows and shared monthly intermediate arrays. Public
    return values are copied from the cache before they are returned, so caller
    mutation does not corrupt cached state.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to a Cyclus SQLite database output file. The extension must be
        ``.sqlite``.
    """

    _CACHE_MISS = object()

    # --------------- Initialization and input metadata ---------------

    def __init__(self, path):
        """
        Class to access and browse an output file from Cyclus.
        Output file MUST be an SQLite database (.sqlite)

        Parameters:
        -----------
        path: str
            path to output file, including file name
        """
        self._cache = {}
        assert os.path.exists(path), "File does not exist."
        ext = os.path.splitext(path)
        assert ext[-1] == ".sqlite", "File extension has to be .sqlite"
        self.path = path
        con = lite.connect(self.path)
        con.row_factory = lite.Row
        self.cur = con.cursor()

        # The analysis routines are read-only and often run several large
        # grouped queries. These pragmas keep temporary grouping structures in
        # memory when SQLite can do so and give the page cache more room. They
        # do not change query results.
        self.cur.execute("PRAGMA temp_store = MEMORY")
        self.cur.execute("PRAGMA cache_size = -200000")

        # Store input text and input dict
        self.input_text = self.get_input_text()
        self.input_dict = self.get_input_dict()

        # Store times
        td = self.get_times()
        self.duration = None
        self.init_year = None
        self.init_month = None
        self.years = None
        self.years_int = None
        self.n_yearly_points = None
        for k, v in td.items():
            setattr(self, k, v)

        # Store agents and reactors. Nuclides are loaded lazily because the
        # distinct-composition query is expensive and only needed by the
        # isotopic process_* helpers, not by the WATTS fuel-cycle path.
        self._nucids = None
        self.agent_dict = self.get_facility_agents()
        self.reactor_types = np.unique(
            list(self.get_facility_agents("reactor").values()))

    def get_input_text(self) -> str:
        """
        Returns the Cyclus input file text stored in the SQLite database.

        Returns:
        -------
        str
            Cyclus input file content as a string.
        """
        rows = self.sql_query("SELECT * FROM InputFiles")
        assert len(rows) == 1, \
            f"Expected 1 row in InputFiles, found {len(rows)}"
        row = rows[0]
        keys = list(row.keys())
        assert "Data" in keys, \
            f"'Data' key not found in InputFiles. Keys: {keys}"
        return row["Data"].decode("utf-8")

    def get_input_dict(self) -> dict:
        """
        Returns the Cyclus input file parsed as a nested dictionary
        from XML.

        Returns:
        -------
        dict
            Cyclus input file content as a dictionary.
        """
        input_text = self.get_input_text()
        xml = ET.fromstring(input_text)

        def xml_to_dict(elem):
            """Recursively convert XML element to dictionary.
                Rules:
                - Child tags become keys
                - Repeated tags become lists
                - Attributes are stored under '@attributes'
                - Text content stored under '#text' if mixed
            """
            result = {}

            # Attributes
            if elem.attrib:
                result["@attributes"] = dict(elem.attrib)

            # Children
            children = list(elem)
            if children:
                grouped = {}
                for child in children:
                    child_result = xml_to_dict(child)
                    tag, value = next(iter(child_result.items()))
                    grouped.setdefault(tag, []).append(value)

                # Post-process groups
                for tag, values in grouped.items():
                    # If every entry has a 'name', key by name
                    if all(isinstance(v, dict) and "name" in v for v in values):
                        result[tag] = {
                            v["name"]: {
                                k: val for k, val in v.items() if k != "name"
                            }
                            for v in values
                        }
                    else:
                        # Single element -> unwrap
                        result[tag] = values[0] if len(values) == 1 else values

            # Text
            text = (elem.text or "").strip()
            if text:
                if result:
                    result["#text"] = text
                else:
                    return {elem.tag: text}

            return {elem.tag: result}

        return xml_to_dict(xml)

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
        rows = self._query_facility_agents(spec_keywords=spec_keywords)
        return {row["agentid"]: row["prototype"] for row in rows}

    # --------------- Legacy agent/prototype flow helpers ---------------

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
            id_str = ", ".join([str(aid) for aid in ids])
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

    def process_agent(self, agent_id, get_isotopics):
        """
        Process mass flows and compute stock over time for a given agent ID.

        Parameters:
        ----------
        agent_id : int
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
                                   WHERE {facility_type}=={agent_id}"""
            )
            trade_commods = [q["commodity"] for q in query]

            for commod in trade_commods:
                if not get_isotopics:
                    query = self.sql_query(
                        f"""SELECT sum(quantity), time
                            FROM transactions
                            INNER JOIN resources
                            ON transactions.resourceid = resources.resourceid
                            WHERE {facility_type}=={agent_id}
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
                            WHERE {facility_type}=={agent_id}
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

        return agent_id, flow_dict, agent_stock

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
                agent_stock_dict[proto] = agent_stock
                print(f"\tCompleted prototype {count}/{len(uniq_protos)}")
                count += 1
        else:
            print(f"Going through {len(self.agent_dict)} agents.")
            for agent_id, proto in self.agent_dict.items():
                agent_id, flow_dict, agent_stock = self.process_agent(
                    agent_id, get_isotopics
                )
                agent_flow_dict[agent_id] = flow_dict
                agent_stock_dict[agent_id] = agent_stock
                print(f"\tCompleted agent {count}/{len(self.agent_dict)}")
                count += 1

        return agent_flow_dict, agent_stock_dict

    # --------------- Global Utility Functions ---------------

    def sql_query(self, query_str: str):
        """
        Execute a SQL query linked to the current database and return the
        result

        Parameters:
        -----------
        query_str: str
            SQL query to be executed
        """
        if not hasattr(self, "cur"):
            con = lite.connect(self.path)
            con.row_factory = lite.Row
            self.cur = con.cursor()
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
            assert len(query_result) > 0, \
                "Query result is empty; cannot extract nuclides."
            assert "nucid" in query_result[0].keys(), \
                "Expected 'nucid' column in query result for isotopic data."
            assert value_label != "", \
                "Value label must be provided for isotopic data."
            for row in query_result:
                val[row[time_label], nucids.index(
                    row["nucid"])] += row[value_label]
        else:
            val = np.zeros(duration)
            for row in query_result:
                if not value_label:
                    val[row[time_label]] += 1
                else:
                    val[row[time_label]] += row[value_label]
        return np.array(val)

    def _aggregate_calendar_years(self, arr, how: str) -> np.ndarray:
        """
        Aggregate monthly data by calendar year and align the result to
        integer year starts.

        Cyclus defines a simulation by its start year, start month, and a
        duration in monthly time steps. In the output database,
        InitialYear and InitialMonth identify the calendar year and
        month represented by time step 0. Accordingly, yearly aggregation
        must assign each monthly entry to the calendar year implied by
        (self.init_year, self.init_month, time_index).

        After aggregation, the yearly values are shifted by one entry.
        We use start-of-year alignment: the value stored at integer
        year Y represents the aggregate over the completed calendar year
        Y - 1. In other words, the first entry is a zero placeholder, and
        the final aggregated year is dropped.

        Parameters
        ----------
        arr : array-like
            Monthly data indexed by time step. For one-dimensional input,
            arr[t] is the value at monthly time step t. For
            higher-dimensional input, time is along the first dimension and
            any trailing dimensions are preserved.
        how : {"sum", "max", "end"}
            Aggregation applied within each calendar year:
            - "sum": sum over all months in the year
            - "max": maximum over all months in the year
            - "end": value in the final month of the year

        Returns
        -------
        np.ndarray
            Array aligned to integer year starts. The first entry is a zero
            placeholder. Entry i for i > 0 contains the aggregation
            over calendar year self.years_int[i - 1].
        """
        # Convert to array and validate shape
        arr = np.asarray(arr)
        if arr.ndim == 0:
            raise ValueError(
                "Expected an array of monthly values indexed by time step; "
                "got a scalar."
            )

        if arr.shape[0] == 0:
            return np.zeros((0, *arr.shape[1:]), dtype=arr.dtype)

        # Determine calendar year for each time step, starting from
        # self.init_year and self.init_month
        calendar_years = (
            self.init_year
            + (self.init_month - 1 + np.arange(arr.shape[0])) // 12
        )

        # Identify indices where the calendar year changes and split the array
        split_idx = np.flatnonzero(np.diff(calendar_years)) + 1
        year_blocks = np.split(arr, split_idx, axis=0)

        # Aggregate each calendar year's block according to the user's choice
        if how == "sum":
            yearly = np.stack([block.sum(axis=0)
                              for block in year_blocks], axis=0)
        elif how == "max":
            yearly = np.stack([block.max(axis=0)
                              for block in year_blocks], axis=0)
        elif how == "end":
            yearly = np.stack([block[-1] for block in year_blocks], axis=0)
        else:
            raise ValueError(
                f"Unknown yearly aggregation '{how}'. "
                "Expected one of: 'sum', 'max', or 'end'."
            )

        # Prepend a zero entry to align with self.years_int,
        # and drop the final aggregated year
        zeros = np.zeros((1, *yearly.shape[1:]), dtype=yearly.dtype)
        return np.concatenate((zeros, yearly[:-1]), axis=0)

    def get_yearly_sum(self, arr) -> np.ndarray:
        """
        Return calendar-year sums for monthly data, aligned to self.years_int.
        """
        return self._aggregate_calendar_years(arr, how="sum")

    def get_yearly_max(self, arr) -> np.ndarray:
        """
        Return calendar-year maximums for monthly data, aligned to
        self.years_int.
        """
        return self._aggregate_calendar_years(arr, how="max")

    def get_yearly_end(self, arr) -> np.ndarray:
        """
        Return end-of-calendar-year values for monthly data, aligned to
        self.years_int.
        """
        return self._aggregate_calendar_years(arr, how="end")

    def get_yearly_avg(self, arr) -> np.ndarray:
        """
        Return calendar-year averages for monthly data, aligned to
        self.years_int.

        The yearly value is computed as the calendar-year sum divided by 12.
        For partial first or last calendar years, this gives a 12-month
        normalized average rather than the mean over only the represented
        months.
        """
        return self.get_yearly_sum(arr) / 12.0

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
             'duration':int, 'years':float, 'years_int':int}
        """
        duration = self.sql_query(
            """SELECT InitialYear, InitialMonth, Duration
                                  FROM Info"""
        )[0]

        # If the dt is not months, raise a non-implemented error because the
        # time handling  in this module assumes monthly time steps.
        dt = self.sql_query(
            """SELECT DurationSecs FROM TimeStepDur"""
        )[0]["DurationSecs"]

        # Using 0.01 day tolerance
        lo = 364.99/12 * 24 * 3600  # Lower bound for monthly time step in s
        # Upper bound for monthly time step in s (w/ leap years)
        hi = 365.26/12 * 24 * 3600
        if dt < lo or dt > hi:
            raise NotImplementedError(
                "Time steps other than monthly are not implemented: "
                f"dt={dt} seconds"
            )

        init_year = duration["InitialYear"]
        init_month = duration["InitialMonth"]
        duration = duration["Duration"]

        # Assume each time step is one month, and calculate the
        # calendar year for each time step accordingly
        time = init_year + (np.arange(duration) + init_month - 1) / 12
        years = time

        # If we only want purely integer years,
        # we create an array of the unique years represented
        # in the time array.
        years_int = np.unique(np.floor(years).astype(int))
        n_yearly_points = len(years_int)
        return {
            "init_year": init_year,
            "init_month": init_month,
            "duration": duration,
            "years": years,
            "years_int": np.unique(np.floor(years).astype(int)),
            "n_yearly_points": n_yearly_points,
            "timestep_seconds": dt,
            "timestep_years": dt / (365.25 * 24 * 3600)
        }

    @property
    def nucids(self):
        """
        Return the cached set of nuclide IDs, loading it on first use.

        The full ``SELECT DISTINCT nucid FROM compositions`` query can be one
        of the most expensive parts of initialization for large Cyclus outputs.
        Most WATTS-facing extraction paths do not need ``self.nucids`` because
        their uranium and U-235 masses are computed directly in SQL. The query
        is therefore delayed until isotopic flow processing actually requests
        it.

        Returns
        -------
        numpy.ndarray
            Sorted array of nuclide IDs present in the compositions table.
        """
        if self._nucids is None:
            self._nucids = self.get_nucids()
        return np.array(self._nucids, copy=True)

    @nucids.setter
    def nucids(self, value):
        """
        Set the cached nuclide IDs.

        This setter preserves compatibility with code that assigns
        ``self.nucids`` directly.
        """
        self._nucids = np.array(value, copy=True)

    def get_nucids(self):
        """
        Return all nuclide IDs present in the compositions table.

        Returns:
        -------
        numpy.ndarray
            Sorted array of distinct integer nuclide IDs.
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
        n_yearly_points = self.n_yearly_points
        fuel_flow_array = np.zeros((len(fuel_forms), n_yearly_points))
        for indx, ff in enumerate(fuel_forms):
            query = self._query_mass_flow_by_commodity(ff)
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
            agentids = self._normalize_agent_ids(agentids)
        assert len(agentids) > 0, "No agentid found"
        rows = self._query_commodities_received_by_agent_ids(agentids)
        return [row["commodity"] for row in rows]

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
            agentids = self._normalize_agent_ids(agentids)
        assert len(agentids) > 0, "No agentid found"
        rows = self._query_commodities_sent_by_agent_ids(agentids)
        return [row["commodity"] for row in rows]

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

        rows = self._query_proto_ids(prototypes)

        # If we want a flat list, return it directly
        if want_flat:
            return [row["agentid"] for row in rows]

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
        query = self._query_commodities()
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
            length is the number of years in a simulations
            with the data from arr summed up for each
            year
        """
        query = self._query_mass_flow_by_commodity(commodity_name)
        return np.array(
            self.get_yearly_sum(
                self.query_to_array(query, self.duration,
                                    time_label="time",
                                    value_label="sum(quantity)")
            )
        )

    # --------------- Deployment-related functions ---------------

    def _reactor_power_query(self, prototypes=None) -> str:
        """
        Build the SQL query used to retrieve reactor power history from
        the Cyclus timeseriespower table.

        Parameters
        ----------
        prototypes : str or array-like of str, optional
            Reactor prototype names to include. If None, include all reactor
            facilities with entries in timeseriespower.

        Returns
        -------
        str
            SQL query returning one row per reactor agent and time step,
            with columns:
            - agentid
            - prototype
            - entertime
            - lifetime
            - time
            - power
        """
        if prototypes is None:
            proto_filter = ""
        else:
            prototypes = np.atleast_1d(prototypes)
            proto_csv = ", ".join(f'"{prototype}"' for prototype in prototypes)
            proto_filter = f"\n            AND a.prototype IN ({proto_csv})"

        return f"""
            SELECT
                a.agentid,
                a.prototype,
                a.entertime,
                a.lifetime,
                a.parentid,
                p.time AS time,
                p.value AS power
            FROM agententry a
            JOIN timeseriespower p
                ON a.agentid = p.agentid
            WHERE a.spec LIKE "%Reactor"{proto_filter}
        """

    def _get_power_agents(self):
        """
        Return one summary row per power-producing reactor agent.

        The summary is derived from the reactor power history and provides
        the quantities needed by the deployment and capacity helpers:
        - first positive power time
        - last positive power time
        - maximum positive power

        Returns
        -------
        list
            SQLite rows containing:
            - agentid
            - prototype
            - entertime
            - lifetime
            - first_power_time
            - last_power_time
            - power_cap

        Raises
        ------
        ValueError
            If any reactor has a lifetime of -1 in the AgentEntry table but
            produces positive power, which causes issues for deployment and
            retirement calculations.
        """
        rows = self._query_power_agents()
        self._validate_no_infinite_lifetime_rows(rows, power_column="power_cap")
        return rows

    def get_new_deployments(
        self,
        prototypes: str | list[str] | None = None,
        return_sum: bool = False,
        yearly: bool = True,
        reactors: str | list[str] | None = None,
        rest_key: str = "legacy",
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Determine the number of newly active reactors for each time step
        for each reactor prototype.

        A reactor is considered newly deployed at the first time step
        where it produces strictly positive power.

        Parameters:
        -----------
        prototypes: str | list[str] | None
            Names of reactor prototypes in the simulation. If None and reactors
            is None, uses all reactor types in the simulation.
        return_sum: bool
            If True, returns a single array summed over requested prototypes.
        yearly: bool
            If True, returns yearly counts instead of monthly counts.
        reactors: str | list[str] | None
            Alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.
        rest_key: str
            When return_sum is False, key used to group power-producing
            prototypes not in the requested `prototypes` list.

        Returns:
        --------
        deploy_dict: dict[str, np.ndarray] or np.ndarray
            Keys are strings (reactor prototypes and possibly `rest_key`),
            values are arrays giving the count of new deployments at each
            time step (monthly) or each year (yearly=True).

            If return_sum=True, returns a single array summed over requested
            prototypes only.
        """
        prototypes = self._normalize_prototypes(prototypes, reactors)
        self._validate_new_deployment_rows(self._get_power_agents())
        stores = self._power_lifecycle_arrays(prototypes, rest_key=rest_key)
        return self._finalize_prototype_series(
            stores["new_deployments"],
            prototypes=prototypes,
            return_sum=return_sum,
            yearly=yearly,
            yearly_method="sum",
        )

    def get_retirements(
        self,
        prototypes: str | list[str] | None = None,
        return_sum: bool = False,
        yearly: bool = True,
        reactors: str | list[str] | None = None,
        rest_key: str = "legacy",
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Determine the number of reactor retirements for each time step
        for each reactor prototype.

        A reactor is considered retired at the time step immediately after
        its last strictly positive power production time.

        Parameters:
        -----------
        prototypes: str | list[str] | None
            Names of reactor prototypes in the simulation. If None and reactors
            is None, uses all reactor types in the simulation.
        return_sum: bool
            If True, returns a single array summed over requested prototypes.
        yearly: bool
            If True, returns yearly counts instead of monthly counts.
        reactors: str | list[str] | None
            Alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.
        rest_key: str
            When return_sum is False, key used to group power-producing
            prototypes not in the requested `prototypes` list.

        Returns:
        --------
        retire_dict: dict[str, np.ndarray] or np.ndarray
            Keys are strings (reactor prototypes and possibly `rest_key`),
            values are arrays giving the count of retirements at each
            time step (monthly) or each year (yearly=True).

            If return_sum=True, returns a single array summed over requested
            prototypes only.
        """
        prototypes = self._normalize_prototypes(prototypes, reactors)
        self._validate_retirement_rows(self._get_power_agents())
        stores = self._power_lifecycle_arrays(prototypes, rest_key=rest_key)
        return self._finalize_prototype_series(
            stores["retirements"],
            prototypes=prototypes,
            return_sum=return_sum,
            yearly=yearly,
            yearly_method="sum",
        )

    def get_fleet_size(
        self,
        prototypes: str | list[str] | None = None,
        return_sum: bool = False,
        yearly: bool = True,
        reactors: str | list[str] | None = None,
        rest_key: str = "legacy",
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Determine the size of the power-active reactor fleet for each time step
        for each reactor prototype.

        Fleet size is computed from power-based deployment and retirement
        events:
            fleet[t] = fleet[t-1] + new_deployments[t] - retirements[t]

        A reactor enters the fleet at its first strictly positive-power time
        and exits the fleet immediately after its last strictly positive-power
        time.

        Parameters:
        -----------
        prototypes: str | list[str] | None
            Names of reactor prototypes in the simulation. If None and reactors
            is None, uses all reactor types in the simulation.
        return_sum: bool
            If True, returns a single array summed over requested prototypes.
        yearly: bool
            If True, returns yearly fleet size instead of monthly.
            The yearly fleet size is the end-of-year fleet count, aligned to
            the same year-binning convention used by get_yearly_sum()
            (prepends an initial 0.0 and drops the final year).
        reactors: str | list[str] | None
            Alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.
        rest_key: str
            When return_sum is False, key used to group power-producing
            prototypes not in the requested `prototypes` list.

        Returns:
        --------
        fleet_dict: dict[str, np.ndarray] or np.ndarray
            Keys are strings (reactor prototypes and possibly `rest_key`),
            values are arrays giving fleet size at each time step (monthly)
            or each year-end (yearly=True).

            If return_sum=True, returns a single array summed over requested
            prototypes only.
        """
        prototypes = self._normalize_prototypes(prototypes, reactors)

        cached = self._cache_get(
            "get_fleet_size",
            prototypes=prototypes,
            return_sum=return_sum,
            yearly=yearly,
            rest_key=rest_key,
        )
        if cached is not self._CACHE_MISS:
            return cached

        # Preserve the legacy validation path: fleet size is defined in terms
        # of deployment and retirement events.
        new_m = self.get_new_deployments(
            prototypes=prototypes,
            return_sum=False,
            yearly=False,
            reactors=None,
            rest_key=rest_key,
        )
        ret_m = self.get_retirements(
            prototypes=prototypes,
            return_sum=False,
            yearly=False,
            reactors=None,
            rest_key=rest_key,
        )

        # Union of keys (should typically match, but be robust)
        keys = sorted(set(new_m.keys()) | set(ret_m.keys()))
        fleet = {}
        for key in keys:
            deployments = new_m.get(key, None)
            retirements = ret_m.get(key, None)
            if deployments is None:
                deployments = np.zeros_like(retirements)
            if retirements is None:
                retirements = np.zeros_like(deployments)
            fleet[key] = np.cumsum(deployments - retirements)

        result = self._finalize_prototype_series(
            fleet,
            prototypes=prototypes,
            return_sum=return_sum,
            yearly=yearly,
            yearly_method="end",
        )

        return self._cache_set(
            result,
            "get_fleet_size",
            prototypes=prototypes,
            return_sum=return_sum,
            yearly=yearly,
            rest_key=rest_key,
        )

    def get_deployed_capacity(
        self,
        prototypes: str | list[str] | None = None,
        return_sum: bool = False,
        yearly: bool = True,
        reactors: str | list[str] | None = None,
        rest_key: str = "legacy"
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Determine the amount of deployed power (GW) for each time step
        for each reactor prototype.

        Deployed capacity is based on the actual positive-power window of
        each reactor agent.

        For each reactor agent:
        - the active interval begins at first_power_time
        - the active interval ends at last_power_time
        - the deployed capacity is taken as the maximum positive power
        observed for that agent

        Parameters:
        -----------
        prototypes: str | list[str] | None
            Names of reactor prototypes in the simulation. If None and reactors
            is None, uses all reactor types in the simulation.
        return_sum: bool
            If True, returns a single array summed over requested prototypes.
        yearly: bool
            If True, returns end-of-year deployed capacity instead
            of monthly deployed capacity.
        reactors: str | list[str] | None
            Alias for prototypes, used for compatibility with DYMOND plugin.
            Reactors and prototypes cannot both be specified.
        rest_key: str
            When return_sum is False, key used to group power-producing
            prototypes not in the requested `prototypes` list.

        Returns:
        --------
        power_dict: dict[str, np.ndarray] or np.ndarray
            Keys are strings (reactor prototypes and possibly `rest_key`),
            values are numpy arrays giving deployed capacity in GW at each
            time step (monthly) or year-end capacity (yearly=True).

            If return_sum=True, returns a single array summed over requested
            prototypes only.
        """
        prototypes = self._normalize_prototypes(prototypes, reactors)
        self._validate_deployed_capacity_rows(self._get_power_agents())
        stores = self._power_lifecycle_arrays(prototypes, rest_key=rest_key)
        return self._finalize_prototype_series(
            stores["deployed_capacity"],
            prototypes=prototypes,
            return_sum=return_sum,
            yearly=yearly,
            yearly_method="end",
        )

    def get_capacity_factors(
        self,
        prototypes: str | list[str] | None = None,
        reactors: str | list[str] | None = None,
    ) -> dict[str, float]:
        """
        Return design capacity factors by reactor prototype.

        Capacity factors are computed from reactor cycle time c and refueling
        time r: CF = c / (r + c). Prototypes without reactor-info rows are
        omitted from the returned dictionary.

        Parameters:
        -----------
        prototypes: str | list[str] | None
            Names of reactor prototypes in the simulation. If None and reactors
            is None, uses all reactor types in the simulation.
        reactors: str | list[str] | None
            Alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.

        Returns:
        --------
        dict[str, float]
            Design capacity factor keyed by prototype.
        """
        prototypes = self._normalize_prototypes(prototypes, reactors)

        cached = self._cache_get("get_capacity_factors", prototypes=prototypes)
        if cached is not self._CACHE_MISS:
            return cached

        if len(prototypes) == 0:
            return self._cache_set({}, "get_capacity_factors", prototypes=prototypes)

        rows = self._query_capacity_factors_from_cycle_times(prototypes)
        result = {row["prototype"]: row["capacity_factor"] for row in rows}
        return self._cache_set(result, "get_capacity_factors", prototypes=prototypes)

    def get_avg_capacity_factors(
        self,
        prototypes: str | list[str] | None = None,
        reactors: str | list[str] | None = None,
        return_avg: bool = False,
    ) -> dict[str, float] | float:
        """
        Realized capacity factor per reactor prototype computed over the full
        simulation timeline from time series:
            CF = sum_over_agents( sum_over_time P(agent,time) )
                 / sum_over_agents( power_cap(agent) * n_steps_agent )

        Parameters:
        -----------
        prototypes: str | list[str] | None
            names of reactor prototypes in the simulation
        reactors: str | list[str] | None
            alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.
        return_avg: bool
            If True, return a single fleet-averaged capacity factor (float)
            over the full timeline.
            If False, return a dict of floats keyed by prototype.

        Returns:
        --------
        dict[str, float] | float
            Either a dict of floats (one per prototype) or a single float
            (fleet average over the full timeline).

        Notes:
        ------
        Prototypes with no power-producing agents are not returned; they do not
        participate in the capacity factor.
        """
        prototypes = self._normalize_prototypes(prototypes, reactors)

        cached = self._cache_get(
            "get_avg_capacity_factors",
            prototypes=prototypes,
            return_avg=return_avg,
        )
        if cached is not self._CACHE_MISS:
            return cached

        if len(prototypes) == 0:
            result = 0.0 if return_avg else {}
            return self._cache_set(
                result,
                "get_avg_capacity_factors",
                prototypes=prototypes,
                return_avg=return_avg,
            )

        if return_avg:
            rows = self._query_avg_capacity_factor(prototypes)
            result = rows[0][0] if rows and rows[0][0] is not None else 0.0
            result = max(0.0, min(1.0, float(result)))
        else:
            rows = self._query_avg_capacity_factors_by_prototype(prototypes)
            result = {}
            for row in rows:
                cf = row["capacity_factor"]
                result[row["prototype"]] = 0.0 if cf is None else float(cf)

        return self._cache_set(
            result,
            "get_avg_capacity_factors",
            prototypes=prototypes,
            return_avg=return_avg,
        )

    def get_generated_power(
        self,
        prototypes: str | list[str] | None = None,
        return_sum: bool = True,
        yearly: bool = True,
        reactors: str | list[str] | None = None,
        capacity_factors: dict[str, float] | None = None,
        default_capacity_factor: float = 0.9,
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Get generated power (GW) over time for one or more prototypes.

        Parameters:
        ----------
        prototypes : str, list of str, or None
            Reactor prototype(s) to analyze. If None, use all reactor types
            in the simulation.
        return_sum : bool
            If True, return summed arrays across all prototypes.
            If False, return per-prototype dict.
        yearly : bool
            If True, return yearly averages instead of monthly data.
        reactors : str or list of str, optional
            alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.
        capacity_factors : dict[str, float] or None
            If None, compute generated power directly from timeseriespower.
            If provided, use deployed capacity (GW) multiplied by capacity
            factor(s) to compute generated power.
        default_capacity_factor : float
            If capacity_factors is provided but missing entries for some
            prototypes, use this value as the default capacity factor.

        Returns:
        -------
        np.ndarray or dict
            If return_sum=True, returns summed array.
            If return_sum=False, returns dict of arrays per prototype.
            Arrays represent generated power in GW for each time step
            (monthly), or yearly mean power if yearly=True.
        """
        prototypes = self._normalize_prototypes(prototypes, reactors)

        cached = self._cache_get(
            "get_generated_power",
            prototypes=prototypes,
            return_sum=return_sum,
            yearly=yearly,
            capacity_factors=capacity_factors,
            default_capacity_factor=default_capacity_factor,
        )
        if cached is not self._CACHE_MISS:
            return cached

        if len(prototypes) == 0:
            result = {} if not return_sum else np.zeros(0)
            return self._cache_set(
                result,
                "get_generated_power",
                prototypes=prototypes,
                return_sum=return_sum,
                yearly=yearly,
                capacity_factors=capacity_factors,
                default_capacity_factor=default_capacity_factor,
            )

        if capacity_factors is not None:
            deployed_power = self.get_deployed_capacity(
                prototypes,
                return_sum=False,
                yearly=False,
                reactors=None,
            )
            gen_dict = {}
            for proto, power in deployed_power.items():
                gen_dict[proto] = power * float(
                    capacity_factors.get(proto, default_capacity_factor)
                )
        else:
            gen_dict = self._generated_power_arrays(prototypes)

        result = self._finalize_prototype_series(
            gen_dict,
            prototypes=prototypes,
            return_sum=return_sum,
            yearly=yearly,
            yearly_method="avg",
        )

        return self._cache_set(
            result,
            "get_generated_power",
            prototypes=prototypes,
            return_sum=return_sum,
            yearly=yearly,
            capacity_factors=capacity_factors,
            default_capacity_factor=default_capacity_factor,
        )

    def get_generated_electricity(
        self,
        prototypes: str | list[str] | None = None,
        return_sum: bool = True,
        yearly: bool = True,
        reactors: str | list[str] | None = None,
        capacity_factors: dict[str, float] | None = None,
        default_capacity_factor: float = 0.9,
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Get generated electricity (GW-yr) over time for one or more
        prototypes.

        Parameters:
        ----------
        prototypes : str, list of str, or None
            Reactor prototype(s) to analyze. If None, use all reactor types
            in the simulation.
        return_sum : bool
            If True, return summed arrays across all prototypes.
            If False, return per-prototype dict.
        yearly : bool
            If True, return yearly sums instead of monthly data.
        reactors : str or list of str, optional
            alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.
        capacity_factors : dict[str, float] or None
            If None, compute generated electricity from timeseriespower-derived
            generated power.
            If provided, compute generated power from deployed capacity
            multiplied by capacity factors, then convert to electricity.

        Returns:
        -------
        np.ndarray or dict
            If return_sum=True, returns summed array.
            If return_sum=False, returns dict of arrays per prototype.
            Arrays represent generated electricity in GW-yr for each period.
        """
        prototypes = self._normalize_prototypes(prototypes, reactors)

        cached = self._cache_get(
            "get_generated_electricity",
            prototypes=prototypes,
            return_sum=return_sum,
            yearly=yearly,
            capacity_factors=capacity_factors,
            default_capacity_factor=default_capacity_factor,
        )
        if cached is not self._CACHE_MISS:
            return cached

        power_dict = self.get_generated_power(
            prototypes,
            return_sum=False,
            yearly=yearly,
            reactors=None,
            capacity_factors=capacity_factors,
            default_capacity_factor=default_capacity_factor,
        )

        electricity_dict = {}
        for reactor, power in power_dict.items():
            # Convert power (GW) to electricity (GW-yr)
            # If monthly data, multiply by 1/12
            electricity_dict[reactor] = power * (1.0 if yearly else 1.0 / 12.0)

        result = self._sum_selected_series(electricity_dict, prototypes) \
            if return_sum else electricity_dict

        return self._cache_set(
            result,
            "get_generated_electricity",
            prototypes=prototypes,
            return_sum=return_sum,
            yearly=yearly,
            capacity_factors=capacity_factors,
            default_capacity_factor=default_capacity_factor,
        )

    # --------------- Direct fuel-related functions ---------------

    def get_fuel_mass_and_enrichment(
        self,
        prototypes: str | list[str] | None = None,
        return_sum: bool = True,
        reactors: str | list[str] | None = None,
    ) -> tuple[np.ndarray | dict[str, np.ndarray], dict[str, np.ndarray]]:
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
        tuple
            ``(fuel_mass, enrichment)``. ``fuel_mass`` is either a summed array
            or a dictionary keyed by prototype, depending on ``return_sum``.
            ``enrichment`` is always a dictionary keyed by prototype.
        """
        prototypes = self._normalize_prototypes(prototypes, reactors)

        cached = self._cache_get(
            "get_fuel_mass_and_enrichment",
            prototypes=prototypes,
            return_sum=return_sum,
        )
        if cached is not self._CACHE_MISS:
            return cached

        fuel_mass = self.stock_fuel_demand(
            prototypes,
            return_sum=return_sum,
            reactors=None,
        )
        enrichment = self.get_enrichments(
            prototypes,
            reactors=None,
        )
        result = fuel_mass, enrichment
        return self._cache_set(
            result,
            "get_fuel_mass_and_enrichment",
            prototypes=prototypes,
            return_sum=return_sum,
        )

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
        prototypes = self._normalize_prototypes(prototypes, reactors)

        cached = self._cache_get(
            "stock_fuel_demand",
            prototypes=prototypes,
            return_sum=return_sum,
        )
        if cached is not self._CACHE_MISS:
            return cached

        # Fuel demand is already aggregated by calendar year in the shared
        # received-fuel store. This avoids building large per-agent monthly
        # intermediate arrays when the public result is annual.
        received = self._received_fuel_yearly_arrays(prototypes)
        fuel_mass = received["fuel_mass"]
        result = self._sum_selected_series(fuel_mass, prototypes) \
            if return_sum else fuel_mass

        return self._cache_set(
            result,
            "stock_fuel_demand",
            prototypes=prototypes,
            return_sum=return_sum,
        )

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
        prototypes = self._normalize_prototypes(prototypes, reactors)

        cached = self._cache_get(
            "stock_fuel_discharged",
            prototypes=prototypes,
            return_sum=return_sum,
        )
        if cached is not self._CACHE_MISS:
            return cached

        # Discharged fuel is already aggregated by calendar year in the shared
        # sent-fuel store. This avoids building large per-agent monthly
        # intermediate arrays when the public result is annual.
        sent = self._sent_fuel_yearly_arrays(prototypes)
        discharged = sent["fuel_mass"]
        result = self._sum_selected_series(discharged, prototypes) \
            if return_sum else discharged

        return self._cache_set(
            result,
            "stock_fuel_discharged",
            prototypes=prototypes,
            return_sum=return_sum,
        )

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
            Enrichments are expressed as decimals.
        """
        prototypes = self._normalize_prototypes(prototypes, reactors)

        cached = self._cache_get("get_enrichments", prototypes=prototypes)
        if cached is not self._CACHE_MISS:
            return cached

        # Uranium and U-235 masses are already aggregated by calendar year in
        # the shared received-fuel store. This keeps enrichment consistent with
        # annual fuel demand while avoiding large monthly intermediate arrays.
        received = self._received_fuel_yearly_arrays(prototypes)
        u_mass_by_proto = received["u_mass"]
        u235_by_proto = received["u235"]

        enrich = {}
        # Calculate enrichment (U-235 mass fraction)
        for prototype in prototypes:
            # to remove warnings when dividing by zero
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = np.zeros_like(u235_by_proto[prototype])
                nonzero = u_mass_by_proto[prototype] > 0
                ratio[nonzero] = (
                    u235_by_proto[prototype][nonzero]
                    / u_mass_by_proto[prototype][nonzero]
                )
                enrich[prototype] = ratio

        return self._cache_set(enrich, "get_enrichments", prototypes=prototypes)

    # --------------- Advanced data extraction functions ---------------

    def stock_fuel_resources(
        self,
        prototypes: str | list[str] | None = None,
        natu_assay: float = None,
        tails_assay: float = None,
        return_sum: bool = True,
        split_cat: bool = False,
        cascade_splits: list[float] | None = None,
        reactors: str | list[str] | None = None,
    ):
        """
        Compute natural-uranium feed, enrichment tails, and SWU
        requirements for one or more reactors.

        Parameters:
        ----------
        prototypes : str or list[str]
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
            Intermediate enrichments that define cascade stages, expressed as
            decimals.
            Defaults to [0.1, 0.2]. An empty list requests a single
            unconstrained cascade stage.
        reactors : str or list[str], optional
            Alias for prototypes, used for compatibility with DYMOND plugin.

        Returns:
        -------
        dict[str, dict[str, np.ndarray] | np.ndarray]
            Dictionary with keys 'natu', 'tails', and 'swu'.
            Natural uranium is always a one-dimensional array. Tails and SWU
            are one-dimensional arrays when split_cat is False and arrays with
            shape (stages, years) when split_cat is True.
        """
        assert natu_assay is not None and 0 <= natu_assay <= 1, \
            f"natu_assay must be a number between 0 and 1, got {natu_assay!r}"
        assert tails_assay is not None and 0 <= tails_assay <= 1, \
            f"tails_assay must be a number between 0 and 1, got " \
            f"{tails_assay!r}"

        if cascade_splits is None:
            cascade_splits = [0.1, 0.2]
        elif not cascade_splits:
            cascade_splits = [np.inf]
        else:
            cascade_splits = list(cascade_splits)

        prototypes = self._normalize_prototypes(prototypes, reactors)

        cached = self._cache_get(
            "stock_fuel_resources",
            prototypes=prototypes,
            natu_assay=natu_assay,
            tails_assay=tails_assay,
            return_sum=return_sum,
            split_cat=split_cat,
            cascade_splits=cascade_splits,
        )
        if cached is not self._CACHE_MISS:
            return cached

        # Mass and enrichment arrays. This call is itself cached, so repeated
        # calls to stock_fuel_natu(), stock_fuel_tails(), and stock_fuel_swu()
        # do not repeat the expensive fuel-demand and enrichment SQL queries.
        fuel_mass, enr = self.get_fuel_mass_and_enrichment(
            prototypes,
            return_sum=False,
            reactors=None,
        )

        # Reuse cascade calculations for repeated enrichment values.
        cascade_cache = {}
        for prototype in prototypes:
            for enrichment in enr[prototype]:
                if enrichment > 0:
                    key = round(float(enrichment), 8)
                    if key not in cascade_cache:
                        cascade = enrichment_cascade(
                            feed_enr=natu_assay,
                            prod_enr=enrichment,
                            tail_enr=tails_assay,
                            cascade_splits=cascade_splits,
                        )
                        # For natural uranium, use only the first stage,
                        # because the rest is reused by the next stage
                        cascade_cache[key] = {
                            "natu": cascade["feed"][0],
                            "tails": np.asarray(cascade["tails"], dtype=float),
                            "swu": np.asarray(cascade["swu"], dtype=float),
                        }

        # Ensure a consistent number of stages. If no positive enrichment is
        # present, return zeros with the stage count implied by cascade_splits.
        if cascade_cache:
            lengths = [len(v["tails"]) for v in cascade_cache.values()]
            assert len(set(lengths)) == 1, \
                "All cascades must have the same number of stages."
            n_stages = lengths[0]
        else:
            n_stages = len(cascade_splits)
        zeros = np.zeros(n_stages)

        results = {"natu": {}, "tails": {}, "swu": {}}
        for prototype in prototypes:
            # Natural-uranium feed
            res_natu = np.array(
                [
                    cascade_cache.get(round(float(e), 8), {"natu": 0})[
                        "natu"] if e > 0 else 0
                    for e in enr[prototype]
                ],
                dtype=float,
            )
            results["natu"][prototype] = res_natu.T * fuel_mass[prototype]

            # Tails
            res_tails = np.array(
                [
                    (
                        cascade_cache.get(
                            round(float(e), 8), {"tails": zeros})["tails"]
                        if e > 0 else zeros
                    )
                    for e in enr[prototype]
                ],
                dtype=float,
            )
            tails_val = res_tails.T * fuel_mass[prototype]
            if not split_cat:
                tails_val = np.sum(tails_val, axis=0)
            results["tails"][prototype] = tails_val

            # SWU
            res_swu = np.array(
                [
                    (
                        cascade_cache.get(
                            round(float(e), 8), {"swu": zeros})["swu"]
                        if e > 0 else zeros
                    )
                    for e in enr[prototype]
                ],
                dtype=float,
            )
            swu_val = res_swu.T * fuel_mass[prototype]
            if not split_cat:
                swu_val = np.sum(swu_val, axis=0)
            results["swu"][prototype] = swu_val

        if return_sum:
            results = {
                key: self._sum_selected_series(values, prototypes)
                for key, values in results.items()
            }

        return self._cache_set(
            results,
            "stock_fuel_resources",
            prototypes=prototypes,
            natu_assay=natu_assay,
            tails_assay=tails_assay,
            return_sum=return_sum,
            split_cat=split_cat,
            cascade_splits=cascade_splits,
        )

    def stock_fuel_natu(
        self,
        prototypes: str | list[str] | None = None,
        natu_assay: float = None,
        tails_assay: float = None,
        return_sum: bool = True,
        cascade_splits: list[float] | None = None,
        reactors: str | list[str] | None = None,
    ):
        """
        Compute natural uranium requirements for one or more reactors.

        Parameters:
        ----------
        prototypes : str or list[str]
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
            Defaults to [0.1, 0.2].
        reactors : str or list[str], optional
            Alias for prototypes, used for compatibility with DYMOND plugin.

        Returns:
        -------
        dict[str, np.ndarray] or np.ndarray
            Natural-uranium feed per reactor (or summed).
        """
        return self.stock_fuel_resources(
            prototypes=prototypes,
            natu_assay=natu_assay,
            tails_assay=tails_assay,
            return_sum=return_sum,
            cascade_splits=cascade_splits,
            reactors=reactors,
        )["natu"]

    def stock_fuel_tails(
        self,
        prototypes: str | list[str] | None = None,
        natu_assay: float = None,
        tails_assay: float = None,
        return_sum: bool = True,
        split_cat: bool = False,
        cascade_splits: list[float] | None = None,
        reactors: str | list[str] | None = None,
    ):
        """
        Compute enrichment tails for one or more reactors.

        Parameters:
        ----------
        prototypes : str or list[str]
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
            If True, return tails split by cascade stage; otherwise
            return total tails per reactor (default False).
        cascade_splits : list of float
            Intermediate enrichments (as decimals) that define cascade stages.
            Defaults to [0.1, 0.2].
        reactors : str or list[str], optional
            Alias for prototypes, used for compatibility with DYMOND plugin.

        Returns:
        -------
        dict[str, np.ndarray] or np.ndarray
            Tails per reactor (or summed), either total arrays or arrays with
            shape (stages, years) when split_cat is True.
        """
        return self.stock_fuel_resources(
            prototypes=prototypes,
            natu_assay=natu_assay,
            tails_assay=tails_assay,
            return_sum=return_sum,
            split_cat=split_cat,
            cascade_splits=cascade_splits,
            reactors=reactors,
        )["tails"]

    def stock_fuel_swu(
        self,
        prototypes: str | list[str] | None = None,
        natu_assay: float = None,
        tails_assay: float = None,
        return_sum: bool = True,
        split_cat: bool = False,
        cascade_splits: list[float] | None = None,
        reactors: str | list[str] | None = None,
    ):
        """
        Compute SWU requirements for one or more reactors.

        Parameters:
        ----------
        prototypes : str or list[str]
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
            If True, return SWU split by cascade stage; otherwise
            return total SWU per reactor (default False).
        cascade_splits : list of float
            Intermediate enrichments (as decimals) that define cascade stages.
            Defaults to [0.1, 0.2].
        reactors : str or list[str], optional
            Alias for prototypes, used for compatibility with DYMOND plugin.

        Returns:
        -------
        dict[str, np.ndarray] or np.ndarray
            SWU per reactor (or summed), either total arrays or arrays with
            shape (stages, years) when split_cat is True.
        """
        return self.stock_fuel_resources(
            prototypes=prototypes,
            natu_assay=natu_assay,
            tails_assay=tails_assay,
            return_sum=return_sum,
            split_cat=split_cat,
            cascade_splits=cascade_splits,
            reactors=reactors,
        )["swu"]

    # --------------- Shared cached intermediate stores ---------------

    def _received_fuel_yearly_arrays(self, prototypes):
        """
        Return cached yearly received-fuel, uranium, and U-235 arrays.

        This shared intermediate store feeds both ``stock_fuel_demand`` and
        ``get_enrichments``. It preserves the previous public behavior by using
        the same prototype-to-agent relationship, commodity handling, and
        calendar-year alignment as the legacy monthly path.

        The legacy implementation first queried the set of commodities received
        by exactly these agent IDs and then filtered the received-fuel query to
        that same set. That commodity filter is tautological for non-null
        commodities, so this helper intentionally bypasses the extra
        ``get_commodity_into`` query on the WATTS-facing path while keeping the
        public ``get_commodity_into`` method unchanged.

        The public fuel-demand and enrichment helpers return annual data. To
        avoid fetching and caching very large per-agent monthly row sets, the
        SQL query groups directly by prototype and aligned calendar-year index.
        This is equivalent to filling monthly arrays and then applying
        ``get_yearly_sum`` to each prototype.

        Parameters
        ----------
        prototypes : array-like of str
            Reactor prototype names.

        Returns
        -------
        dict
            Dictionary with keys ``fuel_mass``, ``u_mass``, and ``u235``. Each
            value is a dictionary from prototype name to yearly array.
        """
        cached = self._cache_get_shared(
            "_received_fuel_yearly_arrays",
            prototypes=prototypes,
        )
        if cached is not self._CACHE_MISS:
            return cached

        result = {
            "fuel_mass": self._zero_yearly_dict(prototypes),
            "u_mass": self._zero_yearly_dict(prototypes),
            "u235": self._zero_yearly_dict(prototypes),
        }

        if len(prototypes) > 0:
            rows = self._query_received_fuel_by_prototype_year(prototypes)
            for row in rows:
                prototype = row["prototype"]
                year_index = int(row["year_index"])
                if prototype not in result["fuel_mass"]:
                    continue
                if year_index < 0 or year_index >= self.n_yearly_points:
                    continue
                result["fuel_mass"][prototype][year_index] += row["q"] or 0.0
                result["u_mass"][prototype][year_index] += row["u_mass"] or 0.0
                result["u235"][prototype][year_index] += row["u235"] or 0.0

        return self._cache_set_shared(
            result,
            "_received_fuel_yearly_arrays",
            prototypes=prototypes,
        )

    def _sent_fuel_yearly_arrays(self, prototypes):
        """
        Return cached yearly discharged-fuel arrays.

        This shared intermediate store feeds ``stock_fuel_discharged`` and
        keeps the previous public behavior by using the same prototype-to-agent
        relationship, commodity handling, and calendar-year alignment as the
        legacy monthly path.

        The legacy implementation first queried the set of commodities sent by
        exactly these agent IDs and then filtered the discharged-fuel query to
        that same set. That commodity filter is tautological for non-null
        commodities, so this helper intentionally bypasses the extra
        ``get_commodity_out_of`` query on the WATTS-facing path while keeping
        the public ``get_commodity_out_of`` method unchanged.

        The public discharged-fuel helper returns annual data. To avoid fetching
        and caching very large per-agent monthly row sets, the SQL query groups
        directly by prototype and aligned calendar-year index. This is
        equivalent to filling monthly arrays and then applying ``get_yearly_sum``
        to each prototype.

        Parameters
        ----------
        prototypes : array-like of str
            Reactor prototype names.

        Returns
        -------
        dict
            Dictionary with key ``fuel_mass`` containing a dictionary from
            prototype name to yearly array.
        """
        cached = self._cache_get_shared(
            "_sent_fuel_yearly_arrays",
            prototypes=prototypes,
        )
        if cached is not self._CACHE_MISS:
            return cached

        result = {"fuel_mass": self._zero_yearly_dict(prototypes)}

        if len(prototypes) > 0:
            rows = self._query_sent_fuel_by_prototype_year(prototypes)
            for row in rows:
                prototype = row["prototype"]
                year_index = int(row["year_index"])
                if prototype not in result["fuel_mass"]:
                    continue
                if year_index < 0 or year_index >= self.n_yearly_points:
                    continue
                result["fuel_mass"][prototype][year_index] += row["q"] or 0.0

        return self._cache_set_shared(
            result,
            "_sent_fuel_yearly_arrays",
            prototypes=prototypes,
        )

    def _power_lifecycle_arrays(self, prototypes, rest_key="legacy"):
        """
        Return cached monthly deployment, retirement, and capacity stores.

        The SQL query for power-producing agents is shared across deployment,
        retirement, fleet-size, and deployed-capacity calculations. This method
        converts those rows once into monthly arrays.

        Validation remains in the public methods, so public behavior matches the
        previous implementation: deployment validates deployment assumptions,
        retirement validates retirement assumptions, and deployed capacity
        validates power-capacity assumptions.

        Parameters
        ----------
        prototypes : array-like of str
            Reactor prototype names requested by the caller.
        rest_key : str, default "legacy"
            Key used to accumulate prototypes not explicitly requested.

        Returns
        -------
        dict
            Dictionary with ``new_deployments``, ``retirements``, and
            ``deployed_capacity`` monthly stores.
        """
        cached = self._cache_get_shared(
            "_power_lifecycle_arrays",
            prototypes=prototypes,
            rest_key=rest_key,
        )
        if cached is not self._CACHE_MISS:
            return cached

        rows = self._get_power_agents()
        prototype_set = set(prototypes)
        new_deployments = self._zero_monthly_dict(prototypes)
        retirements = self._zero_monthly_dict(prototypes)
        deployed_capacity = self._zero_monthly_dict(prototypes)
        assert rest_key not in new_deployments, \
            f"Key '{rest_key}' already exists in deploy dict"
        assert rest_key not in retirements, \
            f"Key '{rest_key}' already exists in retire dict"
        assert rest_key not in deployed_capacity, \
            f"Key '{rest_key}' already exists in power_dict"
        new_deployments[rest_key] = np.zeros(self.duration)
        retirements[rest_key] = np.zeros(self.duration)
        deployed_capacity[rest_key] = np.zeros(self.duration)

        for row in rows:
            proto = row["prototype"]
            key = proto if proto in prototype_set else rest_key
            first_power_time = row["first_power_time"]
            last_power_time = row["last_power_time"]
            power_cap = row["power_cap"]

            # Monthly deployment event
            if first_power_time is not None:
                idx = int(first_power_time)
                if 0 <= idx < self.duration:
                    new_deployments[key][idx] += 1.0

            # Monthly retirement event
            if last_power_time is not None:
                idx = int(last_power_time) + 1
                if 0 <= idx < self.duration:
                    retirements[key][idx] += 1.0

            # Monthly deployed capacity in GW
            if (first_power_time is not None
                    and last_power_time is not None
                    and power_cap is not None):
                i0 = int(first_power_time)
                i1 = int(last_power_time)
                if not (i1 < 0 or i0 >= self.duration):
                    i0 = max(i0, 0)
                    i1 = min(i1, self.duration - 1)
                    deployed_capacity[key][i0:i1 + 1] += float(power_cap) * 1e-3

        # Drop rest_key if unused, preserving the old public return structure.
        for store in [new_deployments, retirements, deployed_capacity]:
            if np.sum(store[rest_key]) == 0:
                store.pop(rest_key)

        result = {
            "new_deployments": new_deployments,
            "retirements": retirements,
            "deployed_capacity": deployed_capacity,
        }
        return self._cache_set_shared(
            result,
            "_power_lifecycle_arrays",
            prototypes=prototypes,
            rest_key=rest_key,
        )

    def _generated_power_arrays(self, prototypes):
        """
        Return cached monthly generated-power arrays by prototype.

        Parameters
        ----------
        prototypes : array-like of str
            Reactor prototype names.

        Returns
        -------
        dict
            Prototype name to monthly generated power in GW.
        """
        cached = self._cache_get_shared(
            "_generated_power_arrays",
            prototypes=prototypes,
        )
        if cached is not self._CACHE_MISS:
            return cached

        rows = self._query_generated_power_by_prototype_time(prototypes)
        gen_dict = self._zero_monthly_dict(prototypes)
        for row in rows:
            proto = row["prototype"]
            time_index = int(row["time"])
            if 0 <= time_index < self.duration and proto in gen_dict:
                gen_dict[proto][time_index] += float(row["sum_mwe"]) * 1e-3
        return self._cache_set_shared(
            gen_dict,
            "_generated_power_arrays",
            prototypes=prototypes,
        )

    # --------------- Shared transformation and validation helpers ---------------

    @staticmethod
    def _normalize_agent_ids(agentids):
        """
        Normalize scalar or sequence agent IDs to a flat list.

        Parameters
        ----------
        agentids : int or sequence[int]
            Agent IDs.

        Returns
        -------
        list
            Agent IDs as a list.
        """
        if isinstance(agentids, (list, tuple, np.ndarray)):
            return list(agentids)
        return [agentids]

    def _normalize_prototypes(self, prototypes, reactors):
        """
        Ensure that exactly one of prototypes or reactors is specified,
        and return a normalized array of prototypes.

        Parameters:
        ----------
        prototypes : str, list of str, or None
            Reactor prototype(s) to analyze. If None, use all reactor types
            in the simulation.
        reactors : str or list of str, optional
            alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.

        Returns:
        -------
        np.ndarray
            Normalized array of prototypes to analyze.
        """
        assert (prototypes is None or reactors is None), (
            "Either 'prototypes' or 'reactors' must be specified, "
            f"but not both: prototypes={prototypes}, reactors={reactors}"
        )
        if prototypes is None and reactors is None:
            prototypes = self.reactor_types
        elif reactors is not None:
            prototypes = reactors
        return np.atleast_1d(prototypes)

    def _zero_monthly_dict(self, prototypes):
        """
        Create a zero-valued monthly array for each prototype.

        Parameters
        ----------
        prototypes : sequence[str]
            Prototype names.

        Returns
        -------
        dict
            Prototype name to zero monthly array.
        """
        return {prototype: np.zeros(self.duration) for prototype in prototypes}

    def _zero_yearly_dict(self, prototypes):
        """
        Create a zero-valued yearly array for each prototype.

        Parameters
        ----------
        prototypes : sequence[str]
            Prototype names.

        Returns
        -------
        dict
            Prototype name to zero yearly array, aligned to ``self.years_int``.
        """
        return {
            prototype: np.zeros(self.n_yearly_points)
            for prototype in prototypes
        }

    def _yearly_method(self, values, method):
        """
        Apply a yearly aggregation method.

        Parameters
        ----------
        values : numpy.ndarray
            Monthly values.
        method : {"sum", "max", "end", "avg"}
            Yearly aggregation method.

        Returns
        -------
        numpy.ndarray
            Yearly values.
        """
        if method == "sum":
            return self.get_yearly_sum(values)
        if method == "max":
            return self.get_yearly_max(values)
        if method == "end":
            return self.get_yearly_end(values)
        if method == "avg":
            return self.get_yearly_avg(values)
        raise ValueError(f"Unknown yearly aggregation method '{method}'.")

    def _finalize_prototype_series(
        self,
        series_by_prototype,
        prototypes,
        return_sum,
        yearly,
        yearly_method,
    ):
        """
        Convert monthly prototype series to the requested public output shape.

        Parameters
        ----------
        series_by_prototype : dict[str, numpy.ndarray]
            Monthly values by prototype, possibly with a ``rest_key``.
        prototypes : sequence[str]
            Explicitly requested prototypes.
        return_sum : bool
            If True, return the sum over requested prototypes.
        yearly : bool
            If True, convert each series to yearly values.
        yearly_method : {"sum", "max", "end", "avg"}
            Aggregation used for yearly conversion.

        Returns
        -------
        numpy.ndarray or dict[str, numpy.ndarray]
            Public result.
        """
        result = {
            key: np.array(values, copy=True)
            for key, values in series_by_prototype.items()
        }
        if yearly:
            for key in list(result.keys()):
                result[key] = self._yearly_method(result[key], yearly_method)
        if return_sum:
            return self._sum_selected_series(result, prototypes)
        return result

    def _sum_selected_series(self, series_by_prototype, prototypes):
        """
        Sum series for explicitly requested prototypes.

        Parameters
        ----------
        series_by_prototype : dict[str, numpy.ndarray]
            Series keyed by prototype.
        prototypes : sequence[str]
            Requested prototype names.

        Returns
        -------
        numpy.ndarray
            Sum over the requested prototypes. If none are present, return a
            zero array with the same shape as the available series.
        """
        selected = [
            np.asarray(series_by_prototype[prototype])
            for prototype in prototypes
            if prototype in series_by_prototype
        ]
        if selected:
            return np.sum(selected, axis=0)
        if series_by_prototype:
            return np.zeros_like(next(iter(series_by_prototype.values())))
        return np.zeros(self.n_yearly_points)

    @staticmethod
    def _validate_new_deployment_rows(rows):
        """
        Validate power-agent rows for deployment calculations.

        Parameters
        ----------
        rows : list
            Power-agent summary rows.

        Returns
        -------
        None
        """
        for row in rows:
            first_power_time = row["first_power_time"]
            if first_power_time is None:
                raise ValueError(
                    f"agentid {row['agentid']} has no positive "
                    f"power time, but was included in _get_power_agents."
                )
            assert first_power_time == row["entertime"], \
                f"Agentid {row['agentid']} has enter time {row['entertime']}" \
                f" but first positive power time {first_power_time}."

    @staticmethod
    def _validate_retirement_rows(rows):
        """
        Validate power-agent rows for retirement calculations.

        Parameters
        ----------
        rows : list
            Power-agent summary rows.

        Returns
        -------
        None
        """
        for row in rows:
            if row["last_power_time"] is None:
                raise ValueError(
                    f"Agentid {row['agentid']} has no positive power time, "
                    f"but was included in _get_power_agents."
                )

    def _validate_deployed_capacity_rows(self, rows):
        """
        Validate power-agent rows for deployed-capacity calculations.

        Parameters
        ----------
        rows : list
            Power-agent summary rows.

        Returns
        -------
        None
        """
        pow_cap_dict = {}
        for row in rows:
            proto = row["prototype"]
            power_cap = row["power_cap"]
            assert power_cap is not None, \
                f"Agentid {row['agentid']} has no positive power time, but " \
                f"was included in _get_power_agents."
            power_cap = float(power_cap)
            if proto not in pow_cap_dict:
                pow_cap_dict[proto] = power_cap
            else:
                assert np.isclose(power_cap, pow_cap_dict[proto]), (
                    f"Power output for {proto} is not consistent: "
                    f"{power_cap} != {pow_cap_dict[proto]}"
                )

        for row in rows:
            first_power_time = row["first_power_time"]
            entertime = row["entertime"]
            last_power_time = row["last_power_time"]
            power_cap = row["power_cap"]
            assert first_power_time is not None, \
                f"Agentid {row['agentid']} has no first positive power time."
            assert last_power_time is not None, \
                f"Agentid {row['agentid']} has no last positive power time."
            assert power_cap is not None, \
                f"Agentid {row['agentid']} has no power capacity."
            assert first_power_time == entertime, \
                f"Agentid {row['agentid']} has enter time {entertime} " \
                f"but first positive power time {first_power_time}."
            i0 = int(first_power_time)
            i1 = int(last_power_time)
            if i1 < 0 or i0 >= self.duration:
                raise ValueError(
                    f"Power time window [{first_power_time}, "
                    f"{last_power_time}] for agentid {row['agentid']} "
                    f"is out of range."
                )

    @staticmethod
    def _validate_no_infinite_lifetime_rows(rows, power_column):
        """
        Validate that positive-power reactors do not have infinite lifetimes.

        Parameters
        ----------
        rows : list
            SQLite rows containing a ``lifetime`` column and a power column.
        power_column : str
            Column to check for positive power.

        Returns
        -------
        None
        """
        infinite_in_entry = [
            row for row in rows
            if (
                row["lifetime"] == -1
                and row[power_column] is not None
                and row[power_column] > 0
            )
        ]
        if infinite_in_entry:
            error = ", ".join(
                f"agentid {row['agentid']}, prototype {row['prototype']},"
                f"parentid {row['parentid']}"
                for row in infinite_in_entry
            )
            raise ValueError(
                "Reactors that have lifetime of -1 in AgentEntry table "
                "produce unexpected behavior in deployment and retirement "
                "calculations. Please specify their lifetimes in the "
                "institution that is deploying them in your Cyclus input "
                "file. Affected reactors: "
                f"{error}"
            )

    # --------------- Caching utilities ---------------

    def clear_cache(self):
        """
        Clear cached CyclusOutput results.

        Cyclus output databases are normally immutable after a run. This method
        is mainly useful during debugging, or after manually resetting derived
        attributes on the same object. It does not reopen the SQLite connection.
        """
        self._cache.clear()
        if hasattr(self, "_nucids"):
            self._nucids = None

    @staticmethod
    def _cache_value(value):
        """
        Convert common Python and NumPy containers into hashable cache-key values.
        """
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return tuple(CyclusOutput._cache_value(item) for item in value.tolist())
        if isinstance(value, dict):
            return tuple(
                sorted(
                    (CyclusOutput._cache_value(key), CyclusOutput._cache_value(subvalue))
                    for key, subvalue in value.items()
                )
            )
        if isinstance(value, (list, tuple)):
            return tuple(CyclusOutput._cache_value(item) for item in value)
        if isinstance(value, set):
            return tuple(sorted(CyclusOutput._cache_value(item) for item in value))
        if isinstance(value, Path):
            return str(value)
        return value

    def _cache_key(self, name, *args, **kwargs):
        """
        Build one stable cache key from a logical name and arguments.

        Parameters
        ----------
        name : str
            Logical cache namespace.
        *args
            Positional cache-key values.
        **kwargs
            Keyword cache-key values.

        Returns
        -------
        tuple
            Hashable key suitable for ``self._cache``.
        """
        return (
            name,
            tuple(self._cache_value(arg) for arg in args),
            tuple(sorted((key, self._cache_value(value)) for key, value in kwargs.items())),
        )

    @staticmethod
    def _copy_cache_result(value, copy_result="deep"):
        """
        Copy a cached result before returning it.

        Parameters
        ----------
        value : object
            Cached value.
        copy_result : {"deep", "list", "none"}, default "deep"
            Copy mode used when returning cached values.

        Returns
        -------
        object
            Copied or original cached value.
        """
        if copy_result == "deep":
            return deepcopy(value)
        if copy_result == "list":
            return list(value)
        if copy_result == "none":
            return value
        raise ValueError("copy_result must be one of 'deep', 'list', or 'none'")

    def _cache_get(self, name, *args, copy_result="deep", **kwargs):
        """
        Return a cached value or ``self._CACHE_MISS``.

        Parameters
        ----------
        name : str
            Logical cache namespace.
        *args
            Positional cache-key values.
        copy_result : {"deep", "list", "none"}, default "deep"
            Copy mode used when returning cached values.
        **kwargs
            Keyword cache-key values.

        Returns
        -------
        object
            Cached value, or ``self._CACHE_MISS`` when not cached.
        """
        key = self._cache_key(name, *args, **kwargs)
        if key not in self._cache:
            return self._CACHE_MISS
        return self._copy_cache_result(self._cache[key], copy_result=copy_result)

    def _cache_set(self, value, name, *args, copy_result="deep", **kwargs):
        """
        Store and return a cached value.

        Parameters
        ----------
        value : object
            Value to cache.
        name : str
            Logical cache namespace.
        *args
            Positional cache-key values.
        copy_result : {"deep", "list", "none"}, default "deep"
            Copy mode used when returning cached values.
        **kwargs
            Keyword cache-key values.

        Returns
        -------
        object
            Cached value copied according to ``copy_result``.
        """
        key = self._cache_key(name, *args, **kwargs)
        if copy_result == "list":
            self._cache[key] = tuple(value)
        elif copy_result == "none":
            self._cache[key] = value
        elif copy_result == "deep":
            self._cache[key] = deepcopy(value)
        else:
            raise ValueError("copy_result must be one of 'deep', 'list', or 'none'")
        return self._copy_cache_result(self._cache[key], copy_result=copy_result)

    def _cache_get_shared(self, name, *args, **kwargs):
        """
        Return a private shared cache value without copying it.

        This is used only for internal intermediate stores and SQL row lists
        that the public methods treat as read-only. Public methods should use
        ``_cache_get`` so callers cannot mutate cached state.
        """
        return self._cache_get(name, *args, copy_result="none", **kwargs)

    def _cache_set_shared(self, value, name, *args, **kwargs):
        """
        Store and return a private shared cache value without copying it.

        Keeping this as a named helper makes call sites explicit about why a
        large intermediate result is not deep-copied.
        """
        return self._cache_set(
            value,
            name,
            *args,
            copy_result="none",
            **kwargs,
        )

    def _cached_query(self, name, query, **kwargs):
        """
        Execute and cache a SQL query.

        Parameters
        ----------
        name : str
            Logical cache namespace for the query.
        query : str
            SQL query string.
        **kwargs
            Semantic query parameters that form the cache key.

        Returns
        -------
        list
            Shared cached SQLite rows. Private query callers must treat these
            rows as read-only.
        """
        cached = self._cache_get_shared(name, **kwargs)
        if cached is not self._CACHE_MISS:
            return cached
        rows = self.sql_query(query)
        return self._cache_set_shared(rows, name, **kwargs)

    # --------------- Private SQL query functions ---------------

    def _query_facility_agents(self, spec_keywords=None):
        """
        Query facility agents, optionally filtering by specification keyword.

        Parameters
        ----------
        spec_keywords : str, optional
            Specification keyword used to filter facility agents.

        Returns
        -------
        list
            SQLite rows with ``agentid`` and ``prototype`` columns.
        """
        if not spec_keywords:
            query = """SELECT distinct(agentid), prototype
                   FROM agententry
                   WHERE kind='Facility'"""
        else:
            query = f"""SELECT distinct(agentid), prototype
                    FROM agententry
                    WHERE kind='Facility' and spec
                    LIKE '%{spec_keywords}%' --case-insensitive"""
        return self._cached_query(
            "_query_facility_agents",
            query,
            spec_keywords=spec_keywords,
        )

    def _query_proto_ids(self, prototypes):
        """
        Query agent IDs for one or more prototypes.

        Parameters
        ----------
        prototypes : sequence[str]
            Prototype names.

        Returns
        -------
        list
            SQLite rows with ``prototype`` and ``agentid`` columns.
        """
        if not prototypes:
            return []
        proto_csv = ", ".join(f'"{prototype}"' for prototype in prototypes)
        query = f"""
            SELECT prototype, agentid
            FROM agententry
            WHERE prototype IN ({proto_csv})
        """
        return self._cached_query("_query_proto_ids", query, prototypes=tuple(prototypes))

    def _query_commodities(self):
        """
        Query all unique commodities in the simulation.

        Returns
        -------
        list
            SQLite rows with a ``commodity`` column.
        """
        query = """SELECT distinct(commodity)
            FROM transactions"""
        return self._cached_query("_query_commodities", query)

    def _query_commodities_received_by_agent_ids(self, agentids):
        """
        Query commodities received by one or more agent IDs.

        Parameters
        ----------
        agentids : sequence[int]
            Receiver agent IDs.

        Returns
        -------
        list
            SQLite rows with a ``commodity`` column.
        """
        if not agentids:
            return []
        csv = ",".join(str(agentid) for agentid in agentids)
        query = f"""SELECT distinct(commodity)
            FROM transactions
            WHERE receiverid
            IN ({csv})"""
        return self._cached_query(
            "_query_commodities_received_by_agent_ids",
            query,
            agentids=tuple(agentids),
        )

    def _query_commodities_sent_by_agent_ids(self, agentids):
        """
        Query commodities sent by one or more agent IDs.

        Parameters
        ----------
        agentids : sequence[int]
            Sender agent IDs.

        Returns
        -------
        list
            SQLite rows with a ``commodity`` column.
        """
        if not agentids:
            return []
        csv = ",".join(str(agentid) for agentid in agentids)
        query = f"""SELECT distinct(commodity)
            FROM transactions
            WHERE senderid IN ({csv})"""
        return self._cached_query(
            "_query_commodities_sent_by_agent_ids",
            query,
            agentids=tuple(agentids),
        )

    def _query_mass_flow_by_commodity(self, commodity_name):
        """
        Query total mass flow for one commodity by time step.

        Parameters
        ----------
        commodity_name : str
            Commodity name.

        Returns
        -------
        list
            SQLite rows with ``sum(quantity)`` and ``time`` columns.
        """
        query = f"""SELECT sum(quantity), time
                FROM transactions
                INNER JOIN resources
                ON transactions.resourceid = resources.resourceid
                WHERE Commodity="{commodity_name}"
                GROUP BY time"""
        return self._cached_query(
            "_query_mass_flow_by_commodity",
            query,
            commodity_name=commodity_name,
        )

    def _query_received_fuel_by_prototype_year(self, prototypes):
        """
        Query received fuel mass, uranium mass, and U-235 mass by prototype/year.

        The public fuel-demand and enrichment helpers return yearly arrays, so
        this query groups directly by prototype and aligned calendar year.
        Fetching one row per agent and month would create unnecessary SQLite
        output and Python-side aggregation work for large simulations.

        Calendar-year alignment is performed in SQL using the same convention
        as ``get_yearly_sum``: yearly index 0 is a zero placeholder; index ``i``
        for ``i > 0`` stores the aggregate for ``self.years_int[i - 1]``; the
        final represented calendar year is dropped.

        Parameters
        ----------
        prototypes : sequence[str]
            Reactor prototype names.

        Returns
        -------
        list
            SQLite rows with ``prototype``, ``year_index``, ``q``, ``u_mass``,
            and ``u235`` columns.
        """
        if len(prototypes) == 0:
            return []

        proto_csv = ", ".join(f'"{prototype}"' for prototype in prototypes)
        month_offset = self.init_month - 1
        max_year_index = self.n_yearly_points

        query = f"""
            WITH requested_agents AS (
                SELECT DISTINCT
                    agentid,
                    prototype
                FROM agententry
                WHERE prototype IN ({proto_csv})
            ),
            uranium_fractions AS (
                SELECT
                    qualid,
                    SUM(
                        CASE
                            WHEN nucid BETWEEN 922000000 AND 922999999
                            THEN massfrac
                            ELSE 0
                        END
                    ) AS u_frac,
                    SUM(
                        CASE
                            WHEN nucid = 922350000
                            THEN massfrac
                            ELSE 0
                        END
                    ) AS u235_frac
                FROM compositions
                GROUP BY qualid
            ),
            received AS (
                SELECT
                    requested_agents.prototype AS prototype,
                    CAST(
                        ({month_offset} + transactions.time) / 12
                        AS INTEGER
                    ) + 1 AS year_index,
                    resources.quantity AS quantity,
                    COALESCE(uranium_fractions.u_frac, 0) AS u_frac,
                    COALESCE(uranium_fractions.u235_frac, 0) AS u235_frac
                FROM transactions
                JOIN requested_agents
                    ON transactions.receiverid = requested_agents.agentid
                JOIN resources
                    ON transactions.resourceid = resources.resourceid
                LEFT JOIN uranium_fractions
                    ON resources.qualid = uranium_fractions.qualid
                WHERE transactions.commodity IS NOT NULL
                AND transactions.time < {self.duration}
            )
            SELECT
                prototype,
                year_index,
                SUM(quantity) AS q,
                SUM(quantity * u_frac) AS u_mass,
                SUM(quantity * u235_frac) AS u235
            FROM received
            WHERE year_index > 0
            AND year_index < {max_year_index}
            GROUP BY prototype, year_index
        """
        return self._cached_query(
            "_query_received_fuel_by_prototype_year",
            query,
            prototypes=tuple(prototypes),
        )

    def _query_sent_fuel_by_prototype_year(self, prototypes):
        """
        Query discharged fuel mass by prototype/year.

        The public discharged-fuel helper returns yearly arrays, so this query
        groups directly by prototype and aligned calendar year. Fetching one row
        per agent and month would create unnecessary SQLite output and
        Python-side aggregation work for large simulations.

        Calendar-year alignment is performed in SQL using the same convention
        as ``get_yearly_sum``: yearly index 0 is a zero placeholder; index ``i``
        for ``i > 0`` stores the aggregate for ``self.years_int[i - 1]``; the
        final represented calendar year is dropped.

        Parameters
        ----------
        prototypes : sequence[str]
            Reactor prototype names.

        Returns
        -------
        list
            SQLite rows with ``prototype``, ``year_index``, and ``q`` columns.
        """
        if len(prototypes) == 0:
            return []

        proto_csv = ", ".join(f'"{prototype}"' for prototype in prototypes)
        month_offset = self.init_month - 1
        max_year_index = self.n_yearly_points

        query = f"""
            WITH requested_agents AS (
                SELECT DISTINCT
                    agentid,
                    prototype
                FROM agententry
                WHERE prototype IN ({proto_csv})
            ),
            sent AS (
                SELECT
                    requested_agents.prototype AS prototype,
                    CAST(
                        ({month_offset} + transactions.time) / 12
                        AS INTEGER
                    ) + 1 AS year_index,
                    resources.quantity AS quantity
                FROM transactions
                JOIN requested_agents
                    ON transactions.senderid = requested_agents.agentid
                JOIN resources
                    ON transactions.resourceid = resources.resourceid
                WHERE transactions.commodity IS NOT NULL
                AND transactions.time < {self.duration}
            )
            SELECT
                prototype,
                year_index,
                SUM(quantity) AS q
            FROM sent
            WHERE year_index > 0
            AND year_index < {max_year_index}
            GROUP BY prototype, year_index
        """
        return self._cached_query(
            "_query_sent_fuel_by_prototype_year",
            query,
            prototypes=tuple(prototypes),
        )

    def _query_power_agents(self):
        """
        Query one summary row per power-producing reactor agent.

        Returns
        -------
        list
            SQLite rows with ``agentid``, ``prototype``, ``entertime``,
            ``lifetime``, ``parentid``, ``first_power_time``,
            ``last_power_time``, and ``power_cap`` columns.
        """
        query = f"""
            WITH power_history AS (
                {self._reactor_power_query()}
            )
            SELECT
                agentid,
                prototype,
                entertime,
                lifetime,
                parentid,
                MIN(CASE WHEN power > 0 THEN time END) AS first_power_time,
                MAX(CASE WHEN power > 0 THEN time END) AS last_power_time,
                MAX(CASE WHEN power > 0 THEN power END) AS power_cap
            FROM power_history
            GROUP BY
                agentid,
                prototype,
                entertime,
                lifetime,
                parentid
            HAVING MAX(CASE WHEN power > 0 THEN 1 ELSE 0 END) = 1
            ORDER BY agentid
        """
        return self._cached_query("_query_power_agents", query)

    def _query_capacity_factors_from_cycle_times(self, prototypes):
        """
        Query design capacity factors from reactor cycle/refuel times.

        Parameters
        ----------
        prototypes : sequence[str]
            Reactor prototype names.

        Returns
        -------
        list
            SQLite rows with ``prototype`` and ``capacity_factor`` columns.
        """
        if len(prototypes) == 0:
            return []
        proto_csv = ", ".join(f'"{prototype}"' for prototype in prototypes)
        query = f"""
            SELECT
                p.Prototype AS prototype,
                SUM(r.cycle_time) * 1.0
                    / NULLIF(
                        SUM(r.cycle_time + r.refuel_time),
                        0
                    ) AS capacity_factor
            FROM AgentState_cycamore_ReactorInfo r
            JOIN Prototypes p
                ON p.AgentId = r.AgentId
            WHERE p.Prototype IN ({proto_csv})
            AND r.cycle_time IS NOT NULL
            AND r.refuel_time IS NOT NULL
            GROUP BY p.Prototype;
        """
        return self._cached_query(
            "_query_capacity_factors_from_cycle_times",
            query,
            prototypes=tuple(prototypes),
        )

    def _query_avg_capacity_factor(self, prototypes):
        """
        Query one fleet-averaged realized capacity factor.

        Parameters
        ----------
        prototypes : sequence[str]
            Reactor prototype names.

        Returns
        -------
        list
            SQLite rows with one ``capacity_factor`` column.
        """
        if len(prototypes) == 0:
            return []
        proto_csv = ", ".join(f"'{prototype}'" for prototype in prototypes)
        query = f"""
            WITH cap AS (
                SELECT
                    a.agentid AS agentid,
                    a.prototype AS prototype,
                    MAX(
                        CASE
                            WHEN ts.value > 0
                            THEN ts.value
                            ELSE NULL
                        END
                    ) AS power_cap_mwe
                FROM timeseriespower ts
                JOIN agententry a
                    ON a.agentid = ts.agentid
                WHERE a.spec LIKE "%Reactor"
                AND a.prototype IN ({proto_csv})
                GROUP BY a.agentid, a.prototype
            ),
            win AS (
                SELECT
                    a.agentid AS agentid,
                    SUM(ts.value) * 1.0 AS sum_power_mwe,
                    COUNT(ts.time) AS n_steps
                FROM timeseriespower ts
                JOIN agententry a
                    ON a.agentid = ts.agentid
                WHERE a.spec LIKE "%Reactor"
                AND a.prototype IN ({proto_csv})
                GROUP BY a.agentid
            ),
            per_agent AS (
                SELECT
                    cap.agentid AS agentid,
                    win.sum_power_mwe AS sum_power_mwe,
                    win.n_steps AS n_steps,
                    cap.power_cap_mwe AS power_cap_mwe
                FROM cap
                JOIN win
                    ON win.agentid = cap.agentid
                WHERE cap.power_cap_mwe IS NOT NULL
            )
            SELECT
                SUM(sum_power_mwe)
                    / NULLIF(
                        SUM(power_cap_mwe * n_steps),
                        0
                    ) AS capacity_factor
            FROM per_agent;
        """
        return self._cached_query(
            "_query_avg_capacity_factor",
            query,
            prototypes=tuple(prototypes),
        )

    def _query_avg_capacity_factors_by_prototype(self, prototypes):
        """
        Query realized capacity factors by reactor prototype.

        Parameters
        ----------
        prototypes : sequence[str]
            Reactor prototype names.

        Returns
        -------
        list
            SQLite rows with ``prototype`` and ``capacity_factor`` columns.
        """
        if len(prototypes) == 0:
            return []
        proto_csv = ", ".join(f"'{prototype}'" for prototype in prototypes)
        query = f"""
            WITH cap AS (
                SELECT
                    a.agentid AS agentid,
                    a.prototype AS prototype,
                    MAX(
                        CASE
                            WHEN ts.value > 0
                            THEN ts.value
                            ELSE NULL
                        END
                    ) AS power_cap_mwe
                FROM timeseriespower ts
                JOIN agententry a
                    ON a.agentid = ts.agentid
                WHERE a.spec LIKE "%Reactor"
                  AND a.prototype IN ({proto_csv})
                GROUP BY a.agentid, a.prototype
            ),
            win AS (
                SELECT
                    a.agentid AS agentid,
                    a.prototype AS prototype,
                    SUM(ts.value) * 1.0 AS sum_power_mwe,
                    COUNT(ts.time) AS n_steps
                FROM timeseriespower ts
                JOIN agententry a
                    ON a.agentid = ts.agentid
                WHERE a.spec LIKE "%Reactor"
                  AND a.prototype IN ({proto_csv})
                GROUP BY a.agentid, a.prototype
            ),
            per_agent AS (
                SELECT
                    win.agentid AS agentid,
                    win.prototype AS prototype,
                    win.sum_power_mwe AS sum_power_mwe,
                    win.n_steps AS n_steps,
                    cap.power_cap_mwe AS power_cap_mwe
                FROM win
                JOIN cap
                    ON cap.agentid = win.agentid
                WHERE cap.power_cap_mwe IS NOT NULL
            )
            SELECT
                prototype,
                SUM(sum_power_mwe)
                    / NULLIF(
                        SUM(power_cap_mwe * n_steps),
                        0
                    ) AS capacity_factor
            FROM per_agent
            GROUP BY prototype;
        """
        return self._cached_query(
            "_query_avg_capacity_factors_by_prototype",
            query,
            prototypes=tuple(prototypes),
        )

    def _query_generated_power_by_prototype_time(self, prototypes):
        """
        Query generated reactor power by prototype and time step.

        Parameters
        ----------
        prototypes : sequence[str]
            Reactor prototype names.

        Returns
        -------
        list
            SQLite rows with ``prototype``, ``time``, and ``sum_mwe`` columns.
        """
        if len(prototypes) == 0:
            return []
        query = f"""
            WITH power_history AS (
                {self._reactor_power_query(prototypes=prototypes)}
            )
            SELECT
                prototype,
                time,
                SUM(power) * 1.0 AS sum_mwe
            FROM power_history
            GROUP BY prototype, time
            ORDER BY prototype, time
        """
        return self._cached_query(
            "_query_generated_power_by_prototype_time",
            query,
            prototypes=tuple(prototypes),
        )
