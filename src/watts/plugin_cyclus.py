# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
from typing import List

import sqlite3 as lite
import xml.etree.ElementTree as ET
import numpy as np
import os

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import PluginGeneric, _find_executable
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
    def __init__(self, path):
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

        # Store input text and input dict
        self.input_text = self.get_input_text()
        self.input_dict = self.get_input_dict()

        # Store times
        td = self.get_times()
        for k, v in td.items():
            setattr(self, k, v)

        # Store nuclides, agents, reactors
        self.nucids = self.get_nucids()
        self.agent_dict = self.get_facility_agents()
        self.reactors = np.unique(
            list(self.get_facility_agents("reactor").values()))

    def get_input_text(self) -> str:
        """
        Returns the Cyclus input file text stored in the SQLite database.

        Returns:
        -------
        str
            Cyclus input file content as a string.
        """

        # Get table content
        rows = self.sql_query("SELECT * FROM InputFiles")

        # Ensure there is a single row
        assert len(rows) == 1, f"Expected 1 row in InputFiles, found {len(rows)}"
        row = rows[0]

        # Ensure the key "Data" exists
        keys = list(row.keys())
        assert "Data" in keys, f"'Data' key not found in InputFiles. Keys: {keys}"
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
                    if all(
                        isinstance(v, dict) and "name" in v
                        for v in values
                    ):
                        result[tag] = {
                            v["name"]: {
                                k: val for k, val in v.items()
                                if k != "name"
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
        Execute a SQL query linked to the current database and return the
        result

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
             'duration':int, 'years':float, 'years_int':int}
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
            "years_int": np.unique(np.floor(years).astype(int)),
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
                                    time_label="time",
                                    value_label="sum(quantity)")
            )
        )

    # --------------- Direct fuel-related functions ---------------

    def get_deployed_capacity(
        self,
        prototypes: str | list[str] | None = None,
        return_sum: bool = False,
        yearly: bool = True,
        reactors: str | list[str] | None = None,
        rest_key: str = 'legacy'
    ) -> np.ndarray | dict[str, np.ndarray]:
        """
        Determines the amount of deployed power (GW) for each time step
        for each reactor prototype

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
        rest_key: str
            key used to accumulate any prototypes not in the `prototypes` list

        Returns:
        --------
        power_dict: dictionary
            keys are strings, the reactor names and 'legacy',
            the values are a numpy array with one element for
            each time step in the scenario, indicating how
            much power is deployed for each key during the
            simulation (GW).
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
        assert(rest_key not in power_dict), f"Key '{rest_key}' already exists in power_dict"
        power_dict[rest_key] = np.zeros(self.duration)
        pow_cap_dict = {}

        # ensure nonzero power output is the same
        pow_query = self.sql_query(
            """SELECT prototype, value
               FROM agententry
               INNER JOIN timeseriespower
               ON agententry.agentid = timeseriespower.agentid
               WHERE agententry.spec
               LIKE "%Reactor"
               AND value != 0 """
        )
        pow_query_dict = [dict(q) for q in pow_query]
        for reactor in prototypes:
            l = [q for q in pow_query_dict if q['Prototype'] == reactor]
            vals = [q['Value'] for q in l]
            assert(len(list(set(vals))) == 1)
            pow_cap_dict[reactor] = vals[0]

        for row in query:
            proto = row["prototype"]
            t0 = row["entertime"]
            t1 = row["lifetime"]
            pow = row['value']
            if proto in power_dict.keys():
                assert(pow == pow_cap_dict[proto]), f"Power output for {proto} is not consistent: {pow} != {pow_cap_dict[proto]}"
                power_dict[proto][t0 - 1: t0 + t1 - 1] += pow * 1e-3
            else:
                power_dict[rest_key][t0 - 1: t0 + t1 - 1] += pow * 1e-3

        if sum(power_dict[rest_key]) == 0:
            # if it's zero no need to keep it
            power_dict.pop(rest_key)

        # If yearly is True, convert monthly data to yearly data
        if yearly:
            for key in power_dict.keys():
                power_dict[key] = self.get_yearly_sum(power_dict[key]) / 12.0

        # If return_sum is True, sum the power across all reactors
        if return_sum:
            # Sum all power arrays in the dictionary
            power_dict = np.sum(list(power_dict.values()), axis=0)
        return power_dict

    def get_capacity_factors(
        self,
        prototypes: str | list[str] | None = None,
        reactors: str | list[str] | None = None,
    ) -> dict[str, float]:
        """
        Capacity factor per reactor prototype from cycle time c
        and refueling time r steps: CF = c/(r+c)
        """

        assert (
            prototypes is None or reactors is None
        ), f"Either 'prototypes' or 'reactors' must be specified, but not both: " \
        f"prototypes={prototypes}, reactors={reactors}"

        if prototypes is None and reactors is None:
            prototypes = self.reactors
        elif reactors is not None:
            prototypes = reactors

        prototypes = np.atleast_1d(prototypes)

        if len(prototypes) == 0:
            return {}

        proto_csv = ", ".join(f'"{p}"' for p in prototypes)

        rows = self.sql_query(f"""
            SELECT
                p.Prototype AS prototype,
                SUM(r.cycle_time) * 1.0
                / NULLIF(SUM(r.cycle_time + r.refuel_time), 0) AS capacity_factor
            FROM AgentState_cycamore_ReactorInfo r
            JOIN Prototypes p
            ON p.AgentId = r.AgentId
            WHERE p.Prototype IN ({proto_csv})
            AND r.cycle_time IS NOT NULL
            AND r.refuel_time IS NOT NULL
            GROUP BY p.Prototype;
        """)

        return {row["prototype"]: row["capacity_factor"] for row in rows}

    def get_avg_capacity_factors(
        self,
        prototypes: str | list[str] | None = None,
        reactors: str | list[str] | None = None,
        return_avg: bool = False,
    ) -> dict[str, float] | float:
        """
        Realized capacity factor per reactor prototype computed from time series:
            CF = sum_over_agents( sum_over_time P(agent,time) )
                 / sum_over_agents( power_cap(agent) * n_steps_agent )

        Parameters:
        -----------
        prototypes: str | list[str] | None
            names of reactor prototypes in the simulation
        reactors: str | list[str] | None
            alias for prototypes, used for compatibility with DYMOND plugin.
            reactors and prototypes cannot both be specified.
        time: None | True | float | list/tuple/array of floats
            If None or True, compute over the whole timeline.
            If float/int, compute over the single year closest to this value.
            If list/tuple/array, compute over the union of all years between
            min(time) and max(time), inclusive.
        return_avg: bool
            If True, return a single fleet-averaged capacity factor (float)
            over the selected timeline.
            If False, return a dict of floats keyed by prototype.

        Returns:
        --------
        dict[str, float] | float
            Either a dict of floats (one per prototype) or a single float
            (fleet average over the selected timeline).

        Notes:
        ------
        Prototypes with no reactors present during the selected time window
        are not returned (they do not participate in the CF).
        """
        # Match the house style: prototypes/reactors aliasing
        assert (
            prototypes is None or reactors is None
        ), f"Either 'prototypes' or 'reactors' must be specified, but not both: " \
        f"prototypes={prototypes}, reactors={reactors}"

        if prototypes is None and reactors is None:
            prototypes = self.reactors
        elif reactors is not None:
            prototypes = reactors

        prototypes = np.atleast_1d(prototypes)

        if len(prototypes) == 0:
            return 0.0 if return_avg else {}

        # Use SQL string literals (single quotes) for robustness
        proto_csv = ", ".join(f"'{p}'" for p in prototypes)

        # Realized CF from timeseriespower, aggregated robustly across agents.
        # We infer nameplate per agent from its time series:
        # power_cap_mwe = MAX(value) over the full agent history where value > 0.
        if return_avg:
            rows = self.sql_query(f"""
                WITH cap AS (
                  SELECT
                    a.agentid AS agentid,
                    a.prototype AS prototype,
                    MAX(CASE WHEN ts.value > 0 THEN ts.value ELSE NULL END) AS power_cap_mwe
                  FROM timeseriespower ts
                  JOIN agententry a ON a.agentid = ts.agentid
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
                  JOIN agententry a ON a.agentid = ts.agentid
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
                  SUM(sum_power_mwe) / NULLIF(SUM(power_cap_mwe * n_steps), 0) AS capacity_factor
                FROM per_agent;
            """)
            cf = rows[0][0] if rows and rows[0][0] is not None else 0.0
            cf = float(cf)
            cf = max(0.0, min(1.0, cf))
            return cf

        rows = self.sql_query(f"""
            WITH cap AS (
              SELECT
                a.agentid AS agentid,
                a.prototype AS prototype,
                MAX(CASE WHEN ts.value > 0 THEN ts.value ELSE NULL END) AS power_cap_mwe
              FROM timeseriespower ts
              JOIN agententry a ON a.agentid = ts.agentid
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
              JOIN agententry a ON a.agentid = ts.agentid
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
              SUM(sum_power_mwe) / NULLIF(SUM(power_cap_mwe * n_steps), 0) AS capacity_factor
            FROM per_agent
            GROUP BY prototype;
        """)

        cf_dict = {}
        for row in rows:
            proto = row["prototype"]
            cf = row["capacity_factor"]
            if cf is None:
                cf = 0.0
            cf = float(cf)
            cf_dict[proto] = cf

        # Prototypes with no agents present in the selected window are omitted
        return cf_dict

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
            If True, return yearly sums instead of monthly data.
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
            Arrays represent generated power in GW for each time step (monthly),
            or yearly means if yearly=True.
        """
        # aliasing for prototypes/reactors
        assert (
            prototypes is None or reactors is None
        ), "Either 'prototypes' or 'reactors' must be specified, but not both."
        if prototypes is None and reactors is None:
            prototypes = self.reactors
        elif reactors is not None:
            prototypes = reactors
        prototypes = np.atleast_1d(prototypes)

        if len(prototypes) == 0:
            return {} if not return_sum else np.zeros(0)

        # If capacity_factors are provided,
        # compute generation from deployed capacity
        if capacity_factors is not None:
            deployed_power = self.get_deployed_capacity(
                prototypes,
                return_sum=False,
                yearly=yearly,
                reactors=reactors,
            )
            gen_dict = {}
            for proto in deployed_power.keys():
                gen_dict[proto] = deployed_power[proto] * \
                    float(capacity_factors.get(proto, default_capacity_factor))

            if return_sum:
                return np.sum(list(gen_dict.values()), axis=0)
            return gen_dict

        # Otherwise, compute generated power directly from time series
        proto_csv = ", ".join(f'"{p}"' for p in prototypes)

        # Direct aggregation in SQL: sum p.value (MWe) per prototype/time
        rows = self.sql_query(f"""
            SELECT
              a.prototype AS prototype,
              p.time AS time,
              SUM(p.value) * 1.0 AS sum_mwe
            FROM timeseriespower p
            JOIN agententry a ON a.agentid = p.agentid
            WHERE a.prototype IN ({proto_csv})
            GROUP BY a.prototype, p.time
            ORDER BY a.prototype, p.time;
        """)

        # Initialize arrays (monthly) and fill with zeros
        gen_dict = {prototype: np.zeros(self.duration) for prototype in prototypes}

        # Fill arrays (convert MWe -> GW)
        for row in rows:
            proto = row["prototype"]
            t = int(row["time"])
            sum_mwe = float(row["sum_mwe"])
            gen_gw = sum_mwe * 1e-3
            idx = t - 1
            if idx >= 0:
                gen_dict[proto][idx] += gen_gw

        # If yearly requested, convert monthly to yearly mean GW
        if yearly:
            for proto in gen_dict.keys():
                yearly_sum = self.get_yearly_sum(gen_dict[proto])
                gen_dict[proto] = yearly_sum / 12.0

        # If return_sum True, sum across prototypes
        if return_sum:
            return np.sum(list(gen_dict.values()), axis=0)
        return gen_dict


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
            If provided, compute generated power from deployed capacity multiplied
            by capacity factors, then convert to electricity.

        Returns:
        -------
        np.ndarray or dict
            If return_sum=True, returns summed array.
            If return_sum=False, returns dict of arrays per prototype.
            Arrays represent generated electricity in GW-yr for each period.
        """
        power_dict = self.get_generated_power(
            prototypes,
            return_sum=False,
            yearly=yearly,
            reactors=reactors,
            capacity_factors=capacity_factors,
        )
        electricity_dict = {}
        for reactor, power in power_dict.items():
            # Convert power (GW) to electricity (GW-yr)
            # If monthly data, multiply by 1/12
            elec = power * (1.0 if yearly else 1.0 / 12.0)
            electricity_dict[reactor] = elec

        if return_sum:
            return np.sum(list(electricity_dict.values()), axis=0)
        return electricity_dict

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
            for proto, ids in ids_by_proto.items():
                if rec_id in ids:
                    out[proto][time] += quantity
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
            rid, time, quantity = row["senderid"], row["time"], row["q"]
            if time >= self.duration:
                continue
            for p, ids in ids_by_proto.items():
                if rid in ids:
                    out[p][time] += quantity
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
            Enrichments are expressed as decimals.
        """
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
            rid, time, u_mass, u235 = (
                row["receiverid"],
                row["time"],
                row["u_mass"],
                row["u235"],
            )
            if time >= self.duration:
                continue
            for proto, ids in ids_by_proto.items():
                if rid in ids:
                    mass_by_proto[proto][time] += u_mass
                    u235_by_proto[proto][time] += u235
                    break

        # Convert to yearly total
        for prototype in prototypes:
            mass_by_proto[prototype] = self.get_yearly_sum(
                mass_by_proto[prototype])
            u235_by_proto[prototype] = self.get_yearly_sum(
                u235_by_proto[prototype])

        enrich = {}
        # Calculate enrichment (U-235 mass fraction)
        for prototype in prototypes:
            # to remove warnings when dividing by zero
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = np.zeros_like(u235_by_proto[prototype])
                nonzero = mass_by_proto[prototype] > 0
                ratio[nonzero] = u235_by_proto[prototype][nonzero] / \
                    mass_by_proto[prototype][nonzero]
                enrich[prototype] = ratio

        return enrich

    # --------------- Advanced data extraction functions ---------------

    def stock_fuel_resources(
        self,
        prototypes: str | list[str] | None = None,
        natu_assay: float = None,
        tails_assay: float = None,
        return_sum: bool = True,
        split_cat: bool = False,
        cascade_splits=[0.1, 0.2],
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
            Enrichment of the feed (typically natural uranium) as a decimal.
        tails_assay : float
            Enrichment of the tails material as a decimal.
        return_sum : bool, optional
            If True, returns the sum across reactors (default True).
        split_cat : bool, optional
            If True, return tails and SWU split by cascade stage;
            otherwise return totals (default False).
        cascade_splits : list of float
            Intermediate enrichments that define cascade stages, expressed as
            decimals.
            Defaults to [0.1, 0.2].
        reactors : str or list[str], optional
            Alias for prototypes, used for compatibility with DYMOND plugin.

        Returns:
        -------
        results: dict[str, dict[str, np.ndarray] | np.ndarray]
            Dictionary with keys 'natu', 'tails', and 'swu'.
            For each entry the structure matches the corresponding
            stock_fuel_* helper that it replaces.
        """

        if not cascade_splits:
            cascade_splits = [np.inf]

        # Reactor list
        assert (
            prototypes is None or reactors is None
        ), f"Either 'prototypes' or 'reactors' must be specified, \
            but not both: prototypes={prototypes}, reactors={reactors}"
        if prototypes is None and reactors is None:
            prototypes = self.reactors
        elif reactors is not None:
            prototypes = reactors
        prototypes = np.atleast_1d(prototypes)

        # Mass and enrichment arrays
        fuel_mass, enr = self.get_fuel_mass_and_enrichment(
            prototypes, return_sum=False
        )

        # Cache cascade splits by unique enrichment
        cache = {}
        for prototype in prototypes:
            for enrichment in enr[prototype]:
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

        results = {"natu": {}, "tails": {}, "swu": {}}

        for prototype in prototypes:
            # Natural-uranium feed
            res_natu = np.array(
                [
                    cache.get(round(float(e), 8), {"natu": 0})[
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
                        cache.get(round(float(e), 8), {
                                  "tails": zeros})["tails"]
                        if e > 0
                        else zeros
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
                        cache.get(round(float(e), 8), {"swu": zeros})["swu"]
                        if e > 0
                        else zeros
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
            return {k: sum(v.values()) for k, v in results.items()}
        return results

    def stock_fuel_natu(
        self,
        prototypes: str | list[str] | None = None,
        natu_assay: float = None,
        tails_assay: float = None,
        return_sum: bool = True,
        cascade_splits=[0.1, 0.2],
        reactors: str | list[str] | None = None,
    ):
        """
        Compute natural uranium requirements for one or more reactors.

        Parameters:
        ----------
        prototypes : str or list[str]
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
        cascade_splits=[0.1, 0.2],
        reactors: str | list[str] | None = None,
    ):
        """
        Compute enrichment tails for one or more reactors.

        Parameters:
        ----------
        prototypes : str or list[str]
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
        reactors : str or list[str], optional
            Alias for prototypes, used for compatibility with DYMOND plugin.

        Returns:
        -------
        dict[str, np.ndarray] or np.ndarray
            Tails per reactor (or summed), split or total.
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
        cascade_splits=[0.1, 0.2],
        reactors: str | list[str] | None = None,
    ):
        """
        Compute SWU requirements for one or more reactors.

        Parameters:
        ----------
        prototypes : str or list[str]
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
        reactors : str or list[str], optional
            Alias for prototypes, used for compatibility with DYMOND plugin.

        Returns:
        -------
        dict[str, np.ndarray] or np.ndarray
            SWU per reactor (or summed), split or total.
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
