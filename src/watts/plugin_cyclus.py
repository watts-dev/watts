# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from functools import lru_cache
from pathlib import Path
from typing import Callable, Mapping, List, Optional

from uncertainties import ufloat

import sqlite3 as lite
import numpy as np
import os

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import Plugin, PluginGeneric, _find_executable
from .results import Results, ExecInfo

class ResultsCyclus(Results):
    """Cyclus simulation restuls

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
    """

    def __init__(self, params: Parameters, exec_info: ExecInfo,
                 inputs: List[Path], outputs: List[Path]):
        super().__init__(params, exec_info, inputs, outputs)
        self.obj = self.get_object()
        #! can't do this because sqlite cursors can't be pickled
        # self.obj = CyclusOutput(self.sqlite_file)

    def get_object(self):
        return CyclusOutput(self.sqlite_file)

    @property
    def sqlite_file(self) -> Path:
        l = [p for p in self.outputs if p.name.endswith('sqlite')]
        assert(len(l) == 1)
        return l[0]

    @property
    def prototypes(self):
        return list(set(self.obj.agent_dict.values()))

    @property
    def reactors(self):
        return self.obj.get_facility_agents('reactor')

    @property
    def commodities(self) -> List[str]:
        # obj = CyclusOutput(self.sqlite_file)
        q = self.obj.cur.execute('SELECT distinct(commodity) FROM transactions')
        return [x['commodity'] for x in q]

    @property
    def time_dict(self) -> dict:
        # obj = CyclusOutput(self.sqlite_file)
        return self.obj.get_times()

    @property
    def mass_flow_dict(self) -> dict:
        # obj = CyclusOutput(self.sqlite_file)
        arr = self.obj.get_fuel_demands(self.commodities)
        d = {}
        for indx in range(len(arr)):
            d[self.commodities[indx]] = arr[indx,:]
        return d



class PluginCyclus(PluginGeneric):
    """Plugin for running Cyclus

    #! In addition to the basic capability to use placeholders in MCNP input files,
    this class also provides a custom Jinja filter called `expand_element
    that allows you to specify natural elements in MCNP material definitions and
    have them automatically expanded based on what isotopes appear in the xsdir
    file.

    Parameters
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
        executable: PathLike = 'cyclus',
        show_stdout: bool = False,
        show_stderr: bool = False
    ):
        executable = _find_executable(executable, 'PATH')
        output_name = template_file.replace('.xml', '.sqlite')
        super().__init__(
            executable, ['{self.executable}', '{self.input_name}', '-o', output_name],
            # executable, [self.executable, template_file, '-o', output_name],
            template_file, plugin_name="Cyclus",
            show_stdout=show_stdout,
            show_stderr=show_stderr,
            unit_system='si')
        self.input_name = "cyclus_input"


class CyclusOutput:
    def __init__(self, path, by_proto=True):
        '''
        Class to access and browse an output file from Cyclus.
        Output file MUST be an SQLite database (.sqlite)
        Parameters:
        -----------
        path: str
            path to output file, including file name
        '''
        assert(os.path.exists(path)), 'File does not exist.'
        ext = os.path.splitext(path)
        assert(ext[-1] == '.sqlite'), 'File extension has to be .sqlite'
        con = lite.connect(path)
        con.row_factory = lite.Row
        self.cur = con.cursor()
        # get times
        td = self.get_times()
        for k,v in td.items():
            setattr(self, k, v)
        self.nucids = self.get_nucids()
        self.agent_dict = self.get_facility_agents()

        # self.flows, self.stocks = self.get_agent_flow_and_stock_dict(by_proto)
        # self.products = self.get_products()


    def get_facility_agents(self, spec_keywords=None):
        """Returns all facility agents in the simulation

        Returns:
            dict: key: int(id), value: str(prototype)
        """
        if not spec_keywords:
            query = self.sql_query('''SELECT distinct(agentid), prototype
                                   FROM agententry
                                   WHERE kind=="Facility"''')
        else:
            query = self.sql_query(f'''SELECT distinct(agentid), prototype
                                   FROM agententry
                                   WHERE kind=="Facility" and spec
                                   LIKE "%{spec_keywords}%" --case-insensitive''')
        agents = {q['agentid']:q['prototype'] for q in query}
        return agents


    def get_products(self):
        # get product tables
        product_dict = {}
        query = self.sql_query('''SELECT name
                               FROM sqlite_master
                               WHERE type="table";''')
        tables = [q['name'] for q in query if 'TimeSeries' in q['name']]
        # kill ones with timeseriessupply or timeseriesdemand
        tables = [q for q in tables if 'TimeSeriessupply' not in q]
        tables = [q for q in tables if 'TimeSeriesdemand' not in q]
        for table in tables:
            key = table.replace('TimeSeries', '')
            product_dict[key] = {}
            # get unique agentids
            query = self.sql_query(f'''SELECT distinct(agentid)
                                   FROM {table}''')
            agentids = [q['agentid'] for q in query]
            # get production timeseries
            for agentid in agentids:
                query = self.sql_query(f'''SELECT sum(value), time
                                       FROM {table}
                                       WHERE agentid=={agentid}
                                       GROUP BY time''')
                product_dict[key][agentid] = self.get_yearly_sum(self.query_to_array(query, self.duration, nucids=[], time_label='time', value_label='sum(value)'))
        return product_dict


    def process_prototype(self, proto, get_isotopics):
        print(f'\tProcessing prototype: {proto}')
        flow_dict = {}
        for c in ['receiverid', 'senderid']:
            key = c.replace('erid', 'ing')
            flow_dict[key] = {}
            # get ids
            if isinstance(proto, list):
                ps = ', '.join([f'"{str(q)}"' for q in proto])
                query = self.sql_query(f'''SELECT agentid
                                       FROM agententry
                                       WHERE prototype
                                       IN ({ps})''')
            else:
                query = self.sql_query(f'''SELECT agentid
                                       FROM agententry
                                       WHERE prototype == "{proto}"''')
            ids = [q['agentid'] for q in query]
            id_str = ', '.join([str(q) for q in ids])
            query = self.sql_query(f'''SELECT distinct(commodity)
                                   FROM transactions
                                   WHERE {c}
                                   IN ({id_str})''')
            trade_commods = [q['commodity'] for q in query]

            for commod in trade_commods:
                if not get_isotopics:
                    query = self.sql_query(f'''SELECT sum(quantity), time
                                           FROM transactions
                                           INNER JOIN resources
                                           ON transactions.resourceid = resources.resourceid
                                           WHERE {c} in ({id_str})
                                           AND commodity=="{commod}"
                                           GROUP BY time''')
                    flow_dict[key][commod] = self.get_yearly_sum(self.query_to_array(
                        query, self.duration, nucids=[], time_label='time', value_label='sum(quantity)'))
                else:
                    # isotopics
                    query = self.sql_query(f'''SELECT time, nucid, sum(quantity * massfrac)
                                           AS nucmass
                                           FROM transactions
                                           JOIN resources
                                           ON transactions.resourceid = resources.resourceid
                                           JOIN compositions on resources.qualid = compositions.qualid
                                           WHERE {c} in ({id_str})
                                           AND commodity=="{commod}"
                                           GROUP BY time, nucid''')
                    flow_dict[key][commod] = self.get_yearly_sum(self.query_to_array(
                        query, self.duration, nucids=self.nucids, time_label='time', value_label='nucmass'))

        # Calculate the stock for this prototype
        agent_stock = np.cumsum(sum(flow_dict['receiving'].values()) - sum(flow_dict['sending'].values()))

        return proto, flow_dict, agent_stock


    def process_agent(self, id, get_isotopics):

        flow_dict = {}
        for c in ['receiverid', 'senderid']:
            key = c.replace('erid', 'ing')
            flow_dict[key] = {}
            query = self.sql_query(f'''SELECT distinct(commodity)
                                   FROM transactions
                                   WHERE {c}=={id}''')
            trade_commods = [q['commodity'] for q in query]

            for commod in trade_commods:
                if not get_isotopics:
                    query = self.sql_query(f'''SELECT sum(quantity), time
                                           FROM transactions
                                           INNER JOIN resources
                                           ON transactions.resourceid = resources.resourceid
                                           WHERE {c}=={id}
                                           AND commodity=="{commod}"
                                           GROUP BY time''')
                    flow_dict[key][commod] = self.get_yearly_sum(self.query_to_array(
                        query, self.duration, nucids=[], time_label='time', value_label='sum(quantity)'))
                else:
                    # isotopics
                    query = self.sql_query(f'''SELECT time, nucid, sum(quantity * massfrac)
                                           AS nucmass
                                           FROM transactions
                                           JOIN resources
                                           ON transactions.resourceid = resources.resourceid
                                           JOIN compositions on resources.qualid = compositions.qualid
                                           WHERE {c}=={id}
                                           AND commodity=="{commod}"
                                           GROUP BY time, nucid''')
                    flow_dict[key][commod] = self.get_yearly_sum(self.query_to_array(
                        query, self.duration, nucids=self.nucids, time_label='time', value_label='nucmass'))

        # Calculate the stock for this agent
        agent_stock = np.cumsum(sum(flow_dict['receiving'].values()) - sum(flow_dict['sending'].values()))

        return id, flow_dict, agent_stock

    def get_agent_flow_and_stock_dict(self, by_proto, get_isotopics=False):
        agent_flow_dict = {}
        agent_stock_dict = {}

        cnt = 1
        uniq_protos = set(self.agent_dict.values())

        if by_proto:
            print(f'Going through {len(uniq_protos)} prototypes.')
            for proto in uniq_protos:
                proto, flow_dict, agent_stock = self.process_prototype(proto, get_isotopics)
                agent_flow_dict[proto] = flow_dict
                agent_stock_dict[proto] = flow_dict
                print(f"\tCompleted prototype {cnt}/{len(uniq_protos)}")
                cnt += 1
        else:
            print(f'Going through {len(self.agent_dict)} agents.')
            for id, proto in self.agent_dict.items():
                id, flow_dict, agent_stock = self.process_agent(id, proto, get_isotopics)
                agent_flow_dict[id] = flow_dict
                agent_stock_dict[id] = flow_dict
                print(f"\tCompleted agent {cnt}/{len(self.agent_dict)}")
                cnt += 1

        return agent_flow_dict, agent_stock_dict

    # ----------------------------- Global Utility Functions -----------------------------

    def sql_query(self, query_str: str):
        '''
        Execute a SQL query linked to the current database and return the result

        Parameters:
        -----------
        query_str: str
            SQL query to be executed
        '''
        query = self.cur.execute(query_str).fetchall()
        return query


    @staticmethod
    def query_to_array(query_result, duration, nucids=[], time_label='entertime', value_label=''):
        '''
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
        '''
        if len(nucids) != 0:
            # isotopic mass
            nucids = list(nucids)
            val = np.zeros((duration, len(nucids)))
            assert('NucId' in query_result[0].keys()), print(query_result[0].keys())
            assert(value_label != '')
            for row in query_result:
                val[row[time_label], nucids.index(row['NucId'])] += row[value_label]
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
        Convert monthly time series data into yearly sums, with initial alignment.

        This function:
        - Sums values over consecutive 12-month periods
        - Prepends an initial 0.0 as a placeholder for the year before data begins
        - Returns one value per year, excluding the final year of data

        Parameters
        ----------
        arr : array-like
            1D array of monthly values

        Returns
        -------
        np.ndarray
            1D array of yearly sums, length = floor(len(arr) / 12), plus one initial 0
        """
        arr = np.asarray(arr)
        n = (len(arr) // 12) * 12             # truncate to full years
        yearly = arr[:n].reshape(-1, 12).sum(axis=1)
        return np.insert(yearly[:-1], 0, 0.0) # remove last year, prepend 0




    # ----------------------------- Basic data extraction functions -----------------------------

    def get_times(self):
        '''
        Gets different time-related data from a simulation

        Parameters:
        -----------

        Returns:
        --------
        dict
            {'init_year':int, 'init_month':int,
             'duration':int, 'time': int, 'years':int}
        '''
        q = self.sql_query('''SELECT prototype, entertime, lifetime, Spec, value
                           FROM agententry
                           INNER JOIN timeseriespower
                           ON agententry.agentid = timeseriespower.agentid
                           WHERE agententry.spec
                           LIKE "%Reactor"
                           AND value != 0
                           GROUP BY agententry.agentid''')
        duration = self.sql_query('''SELECT InitialYear, InitialMonth, Duration
                                  FROM Info''')[0]
        init_year = duration['InitialYear']
        init_month = duration['InitialMonth']
        duration = duration['Duration']
        time = init_year + (np.arange(duration)+init_month-1)/12
        years = time
        return {'init_year': init_year, 'init_month': init_month,
                'duration': duration, 'years': years}

    def get_nucids(self):
        query = self.sql_query('''SELECT distinct(nucid)
                                FROM compositions''')
        nucids = np.array(sorted([q['nucid'] for q in query]))
        return nucids


    def get_fuel_demands(self, fuel_forms=[]):
        '''

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
        '''
        l_ = len(self.get_yearly_sum(np.zeros(self.duration)))
        fuel_flow_array = np.zeros((len(fuel_forms), l_))
        for indx, ff in enumerate(fuel_forms):
            query = self.sql_query('''SELECT sum(quantity), time
                                      FROM transactions
                                      INNER JOIN resources
                                      ON transactions.resourceid = resources.resourceid
                                      WHERE Commodity="%s"
                                      GROUP BY time''' %ff)
            fuel_flow_array[indx, :] = np.array(self.get_yearly_sum(self.query_to_array(query, self.duration, time_label='time', value_label='sum(quantity)')))
        return fuel_flow_array

    def get_commodity_into(self, proto_name=None, agentid=None):
        # there can only be one
        assert((proto_name is not None) != (agentid is not None))
        if proto_name:
            # get the agentids
            agentid = self.get_proto_ids(proto_name)
        else:
            if not isinstance(agentid, list):
                agentid = [agentid]
        assert(len(agentid) > 0), 'No agentid found'
        commods = []
        csv = ','.join([str(q) for q in agentid])
        query = self.sql_query(f'''SELECT distinct(commodity)
                               FROM transactions
                               WHERE receiverid
                               IN ({csv})''')
        return [q['commodity'] for q in query]


    def get_commodity_out_of(self, proto_name=None, agentid=None):
        # there can only be one
        assert((proto_name is not None) != (agentid is not None))
        if proto_name:
            # get the agentids
            agentid = self.get_proto_ids(proto_name)
        else:
            if not isinstance(agentid, list):
                agentid = [agentid]
        assert(len(agentid) > 0), 'No agentid found'
        commods = []
        csv = ','.join([str(q) for q in agentid])
        query = self.sql_query(f'''SELECT distinct(commodity)
                               FROM transactions
                               WHERE senderid IN ({csv})''')
        return [q['commodity'] for q in query]


    def get_proto_ids(
        self,
        proto_name):
        """If **proto_name** is a str, return a flat list of agent IDs.
        If it is a sequence, return a dict {prototype: [agent IDs]}. """

        want_flat = isinstance(proto_name, str)
        prototypes = [proto_name] if want_flat else list(proto_name)

        if not prototypes:                       # handles None, "", empty list
            return [] if want_flat else {}

        # Build a CSV of quoted prototype names:  "rx1", "rx2", …
        proto_csv = ", ".join(f'"{p}"' for p in prototypes)

        # Query the database for agent IDs associated with the prototypes
        rows = self.sql_query(f'''
            SELECT prototype, agentid
            FROM agententry
            WHERE prototype IN ({proto_csv})
        ''')

        # If we want a flat list, return it directly
        if want_flat:
            return [r["agentid"] for r in rows]

        # Otherwise, return a dict mapping prototypes to lists of agent IDs
        out = {p: [] for p in prototypes}
        for r in rows:
            out[r["prototype"]].append(r["agentid"])
        return out


    def get_commodities(self):
        query = self.sql_query('''SELECT distinct(commodity)
                               FROM transactions''')
        return [x['commodity'] for x in query]

    def get_mass_flow(self, commodity_name):
        '''
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
        '''
        query = self.sql_query(f'''SELECT sum(quantity), time
                               FROM transactions
                               INNER JOIN resources
                               ON transactions.resourceid = resources.resourceid
                               WHERE Commodity="{commodity_name}"
                               GROUP BY time''')
        return np.array(self.get_yearly_sum(self.query_to_array(query, self.duration, 'time', 'sum(quantity)')))

    # ----------------------------- Direct fuel-related functions -----------------------------

    def get_deployment_dict(self, reactors, misc_key='legacy'):
        '''
        Determines the amount of deployed power for each time step for
        each reactor prototype

        Parameters:
        -----------
        reactors: list of str
            names of reactor prototypes in the simulation
        misc_key: str
            prototype name to skip over in database

        Returns:
        --------
        power_dict: dictionary
            keys are strings, the reactor names and 'legacy',
            the values are a numpy array with one element for
            each time step in the scenario, indicating how
            much power is deployed for each key during the
            smulation.
        '''
        q = self.sql_query('''SELECT prototype, entertime, lifetime, Spec, value
                           FROM agententry
                           INNER JOIN timeseriespower
                           ON agententry.agentid = timeseriespower.agentid
                           WHERE agententry.spec
                           LIKE "%Reactor"
                           AND value != 0
                           GROUP BY agententry.agentid''')

        power = np.zeros(self.duration)

        power_dict = {k:np.zeros(self.duration) for k in reactors}
        power_dict['legacy'] = np.zeros(self.duration)
        pow_cap_dict = {k:0 for k in reactors if k != misc_key}

        for row in q:
            proto = row['prototype']
            t0 = row['entertime']
            t1 = row['lifetime']

            found = False
            for react_ in reactors:
                if react_ in proto:
                    key = react_
                    found = True
                    if react_ == proto:
                        pow_cap_dict[react_] = row['value'] * 1e-3
            if not found:
                key = misc_key

            power_dict[key][t0-1:t0+t1-1] += row['value'] * 1e-3
        return power_dict

    def get_fuel_mass_and_enrichment(self, prototype: str | list[str], return_sum: bool = True) -> tuple[np.ndarray, np.ndarray] | dict[str, tuple[np.ndarray, np.ndarray]]:
        fuel_mass = self.stock_fuel_demand(prototype, return_sum=return_sum)
        enrichment = self.get_enrichments(prototype)
        return fuel_mass, enrichment

    def stock_fuel_demand(self, prototype: str | list[str], return_sum: bool = True) -> np.ndarray | dict[str, np.ndarray]:
        """
        Annual fuel mass demand from one or more prototypes.

        Parameters
        ----------
        prototype : str or list of str
            Reactor prototype(s).
        return_sum : bool
            If True, returns a single array summed over all prototypes.

        Returns
        -------
        fuel_mass : np.ndarray or dict[str, np.ndarray]
            Yearly fuel mass per prototype, or total if return_sum=True.
        """
        # Convert prototype to a numpy array
        prototype = np.atleast_1d(prototype)

        # Get agent IDs for the specified prototypes (flat list)
        ids_by_proto = self.get_proto_ids(prototype)
        all_ids = [aid for ids in ids_by_proto.values() for aid in ids] # flatten
        id_csv = ",".join(map(str, all_ids))

        # If no IDs found, return empty arrays of the appropriate size
        if not all_ids:
            return np.zeros(self.duration // 12) if return_sum else {p: np.zeros(self.duration // 12) for p in prototype}

        # Get relevant commodities (fuel=into) for each prototype
        commods = self.get_commodity_into(agentid=all_ids)
        commod_csv = ",".join(f'"{c}"' for c in commods)

        # Get total received fuel mass per agent per time step
        # Filters transactions by receiver IDs and fuel-related commodities,
        # and groups results by receiver ID and time to get the total quantity
        rows = self.sql_query(f"""
            SELECT receiverid, time, SUM(quantity) AS q
            FROM transactions
            JOIN resources USING (resourceid)
            WHERE receiverid IN ({id_csv})
            AND commodity IN ({commod_csv})
            GROUP BY receiverid, time
        """)

        # Accumulate monthly quantities
        out = {p: np.zeros(self.duration) for p in prototype}
        for row in rows:
            rid, t, q = row["receiverid"], row["time"], row["q"]
            if t >= self.duration:
                continue
            for p, ids in ids_by_proto.items():
                if rid in ids:
                    out[p][t] += q
                    break

        # Convert to yearly totals
        fuel_mass = {p: self.get_yearly_sum(arr) for p, arr in out.items()}

        # Sum over all prototypes if requested
        if return_sum:
            fuel_mass = np.sum(list(fuel_mass.values()), axis=0)
        return fuel_mass

    def stock_fuel_discharged(self, prototype: str | list[str], return_sum: bool = True) -> np.ndarray | dict[str, np.ndarray]:
        """
        Annual discharged fuel mass from one or more prototypes.

        Parameters
        ----------
        prototype : str or list of str
            Reactor prototype(s).
        return_sum : bool
            If True, returns a single array summed over all prototypes.

        Returns
        -------
        discharged_mass : np.ndarray or dict[str, np.ndarray]
            Yearly discharged fuel mass per prototype, or total if return_sum=True.
        """
        # Convert prototype to a numpy array
        prototype = np.atleast_1d(prototype)

        # Get agent IDs for the specified prototypes (flat list)
        ids_by_proto = self.get_proto_ids(prototype)
        all_ids = [aid for ids in ids_by_proto.values() for aid in ids] # flatten
        id_csv = ",".join(map(str, all_ids))

        # If no IDs found, return empty arrays of the appropriate size
        if not all_ids:
            return np.zeros(self.duration // 12) if return_sum else {p: np.zeros(self.duration // 12) for p in prototype}

        # Get relevant commodities (discharged=out of) for each prototype
        commods = self.get_commodity_out_of(agentid=all_ids)
        commod_csv = ",".join(f'"{c}"' for c in commods)

        # Get total discharged fuel mass per agent per time step
        # Filters transactions by sender IDs and fuel-related commodities,
        # and groups results by sender ID and time to get the total quantity
        rows = self.sql_query(f"""
            SELECT senderid, time, SUM(quantity) AS q
            FROM transactions
            JOIN resources USING (resourceid)
            WHERE senderid IN ({id_csv})
            AND commodity IN ({commod_csv})
            GROUP BY senderid, time
        """)

        # Accumulate monthly quantities
        out = {p: np.zeros(self.duration) for p in prototype}
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

    def get_enrichments(self, prototype: str | list[str]) -> np.ndarray | dict[str, np.ndarray]:
        """
        Annual enrichment (U-235 mass fraction) for fuel delivered to one or more prototypes.
        Always returns one array per prototype.

        Parameters
        ----------
        prototype : str or list of str
            Name(s) of the prototypes to analyze.

        Returns
        -------
        enrichment : dict[str, np.ndarray]
            Annual enrichment time series for each prototype, or a total array.
        """
        # Convert prototype to a numpy array
        prototype = np.atleast_1d(prototype)

        # Get agent IDs for the specified prototypes (flat list)
        ids_by_proto = self.get_proto_ids(prototype)
        all_ids = [aid for ids in ids_by_proto.values() for aid in ids] # flatten
        id_csv = ",".join(map(str, all_ids))

        # If no IDs found, return empty arrays of the appropriate size
        if not all_ids:
            return {p: np.zeros(self.duration // 12) for p in prototype}

        # Get relevant commodities (fuel=into) for each prototype
        commods = self.get_commodity_into(agentid=all_ids)
        commod_csv = ",".join(f'"{c}"' for c in commods)

        # SQL: sum total quantity and U-235 mass per receiver and time
        rows = self.sql_query(f'''
            SELECT receiverid,
                time,
                SUM(CASE WHEN nucid BETWEEN 922000000 AND 922999999
                            THEN quantity * massfrac ELSE 0 END) AS u_mass,
                SUM(CASE WHEN nucid = 922350000
                            THEN quantity * massfrac ELSE 0 END) AS u235
            FROM transactions
            JOIN resources    USING (resourceid)
            JOIN compositions ON resources.qualid = compositions.qualid
            WHERE receiverid IN ({id_csv})
            AND commodity  IN ({commod_csv})
            GROUP BY receiverid, time
        ''')


        # Accumulate monthly quantities
        u235_by_proto = {p: np.zeros(self.duration) for p in prototype}
        mass_by_proto = {p: np.zeros(self.duration) for p in prototype}
        for row in rows:
            rid, t, u_mass, u235 = row["receiverid"], row["time"], row["u_mass"], row["u235"]
            if t >= self.duration:
                continue
            for p, ids in ids_by_proto.items():
                if rid in ids:
                    mass_by_proto[p][t] += u_mass
                    u235_by_proto[p][t] += u235
                    break

        # Convert to yearly total
        for p in prototype:
            mass_by_proto[p] = self.get_yearly_sum(mass_by_proto[p])
            u235_by_proto[p] = self.get_yearly_sum(u235_by_proto[p])

        enrich = {}
        # Calculate enrichment (U-235 mass fraction)
        for p in prototype:
            with np.errstate(divide='ignore', invalid='ignore'): # to remove warnings when dividing by zero
                ratio = np.zeros_like(u235_by_proto[p])
                nonzero = mass_by_proto[p] > 0
                ratio[nonzero] = u235_by_proto[p][nonzero] / mass_by_proto[p][nonzero]
                enrich[p] = ratio

        return enrich

    # ----------------------------- Enrichment process helpers -----------------------------

    @staticmethod
    def feed_to_product_ratio(feed_enr: float | list[float],
                               prod_enr: float | list[float],
                               tailing_enr: float | list[float]) -> float:
        """
        Calculate the feed-to-product ratio for a given enrichment process.

        Parameters
        ----------
        feed_enr : float or list of float
            Enrichment of the feed material.
        prod_enr : float or list of float
            Enrichment of the product material.
        tailing_enr : float or list of float
            Enrichment of the tails material.

        Returns
        -------
        float or list of float
            Feed-to-product ratio for the given enrichment process.
        """
        # Convert inputs to numpy arrays
        feed_enr = np.atleast_1d(feed_enr)
        prod_enr = np.atleast_1d(prod_enr)
        tailing_enr = np.atleast_1d(tailing_enr)

        # Calculate the feed-to-product ratio, based on product, feed, and tails enrichments
        ratio = (prod_enr - tailing_enr) / (feed_enr - tailing_enr)
        ratio[prod_enr == 0] = 0  # Set ratio to 0 if product enrichment is 0
        assert np.all(ratio >= 0), f"Feed-to-product ratio cannot be negative.\nRatio: {ratio}.\nInput was:\n\tFeed: {feed_enr}\n\tProduct: {prod_enr}\n\tTails: {tailing_enr}"
        return ratio

    @staticmethod
    def tails_to_product_ratio(feed_enr: float | list[float],
                               prod_enr: float | list[float],
                               tailing_enr: float | list[float]) -> float:
        """
        Calculate the tails-to-product ratio for a given enrichment process.

        Parameters
        ----------
        feed_enr : float or list of float
            Enrichment of the feed material.
        prod_enr : float or list of float
            Enrichment of the product material.
        tailing_enr : float or list of float
            Enrichment of the tails material.

        Returns
        -------
        float or list of float
            Tails-to-product ratio for the given enrichment process.
        """
        # Convert inputs to numpy arrays
        feed_enr = np.atleast_1d(feed_enr)
        prod_enr = np.atleast_1d(prod_enr)
        tailing_enr = np.atleast_1d(tailing_enr)

        # Calculate the tails-to-product ratio based on product, feed, and tails enrichments
        ratio = (prod_enr - feed_enr) / (feed_enr - tailing_enr)
        ratio[prod_enr == 0] = 0  # Set ratio to 0 if product enrichment is 0
        assert np.all(ratio >= 0), f"Tails-to-product ratio cannot be negative.\nRatio: {ratio}.\nInput was:\n\tFeed: {feed_enr}\n\tProduct: {prod_enr}\n\tTails: {tailing_enr}"
        return ratio

    @staticmethod
    def _swu_function(enr: float | list[float]):
        """
        Helper function to calculate the separative work unit (SWU) for a given enrichment level.
        This function is used internally by the calculate_swu method.

        Parameters
        ----------
        enr : float or list of float
            Enrichment level of the material, expressed as a decimal (0 to 1).

        Returns
        -------
        float or list of float
            SWU value for the given enrichment level.
        """
        # Convert inputs to numpy arrays
        enr = np.atleast_1d(enr)
        result = np.zeros_like(enr)

        # Mask for valid enrichment values (0 < enr < 1). The rest will be 0.
        mask = (enr > 0) & (enr < 1)

        # Formula is: f(x) = (2x - 1) * log(x / (1 - x)) where x is the enrichment
        result[mask] = (2 * enr[mask] - 1) * np.log(enr[mask] / (1 - enr[mask]))
        return result if result.shape else result.item()

    @staticmethod
    def SWU_to_product_ratio(feed_enr: float | list[float],
                            prod_enr: float | list[float],
                            tailing_enr: float | list[float]) -> float | np.ndarray:
        """
        Calculate the separative work unit (SWU) to product ratio for a given enrichment process.

        Parameters
        ----------
        feed_enr : float or list of float
            Enrichment of the feed material.
        prod_enr : float or list of float
            Enrichment of the product material.
        tailing_enr : float or list of float
            Enrichment of the tails material.

        Returns
        -------
        float or np.ndarray
            SWU-to-product ratio for the given enrichment process.
        """

        # Convert to arrays
        feed_enr = np.atleast_1d(feed_enr)
        prod_enr = np.atleast_1d(prod_enr)
        tailing_enr = np.atleast_1d(tailing_enr)

        # Compute intermediate ratios
        tails_ratio = CyclusOutput.tails_to_product_ratio(feed_enr, prod_enr, tailing_enr)
        feed_ratio = CyclusOutput.feed_to_product_ratio(feed_enr, prod_enr, tailing_enr)

        # Compute value terms
        Vp = CyclusOutput._swu_function(prod_enr)
        Vf = CyclusOutput._swu_function(feed_enr)
        Vt = CyclusOutput._swu_function(tailing_enr)

        # Final SWU per product formula
        swu_per_product = Vp + tails_ratio * Vt - feed_ratio * Vf
        swu_per_product[prod_enr == 0] = 0  # Set SWU to 0 if product enrichment is 0
        assert np.all(swu_per_product >= 0), f"SWU-to-product ratio cannot be negative.\nRatio: {swu_per_product}.\nInput was:\n\tFeed: {feed_enr}\n\tProduct: {prod_enr}\n\tTails: {tailing_enr}"
        return swu_per_product

    # ----------------------------- Advanced data extraction functions -----------------------------

    def stock_fuel_natu(self, prototype:str | list[str],
                        natu_assay:float,
                        tails_assay:float,
                        return_sum: bool = True):
        """
        Calculate the natural uranium mass flow for a given prototype or list of prototypes.
        This function computes the natural uranium mass flow based on the feed-to-product ratio
        and the enrichment levels of the specified prototypes.

        Parameters
        ----------
        prototype : str or list of str
            Name(s) of the prototype(s) to analyze.
        natu_assay : float
            Enrichment level of the natural uranium, expressed as a decimal.
        tails_assay : float
            Enrichment level of the tails material, expressed as a decimal.
        return_sum : bool, optional
            If True, returns a single array summed over all prototypes. Default is True.

        Returns
        -------
        nat : dict[str, np.ndarray] or np.ndarray
            Natural uranium mass flow for each prototype, or total if return_sum=True.
        """
        # Convert prototype to a numpy array
        prototype = np.atleast_1d(prototype)

        # Get fuel demand and enrichment for the specified prototypes, separately for each
        fuel_mass_flow, enrichment = self.get_fuel_mass_and_enrichment(prototype, return_sum=False)

        # Construct a dictionary per prototype
        nat = {}
        for p in prototype:
            # Calculate the feed-to-product ratio for the current prototype
            feed_to_product_ratio = self.feed_to_product_ratio(natu_assay, enrichment[p], tails_assay)
            # Multiply the ratio by the product (fuel demand)
            nat[p] = fuel_mass_flow[p] * feed_to_product_ratio

        # Sum over all prototypes if requested
        if return_sum:
            nat = np.sum(list(nat.values()), axis=0)
        return nat

    def stock_fuel_tails(self, prototype:str | list[str],
                        natu_assay:float,
                        tails_assay:float,
                        return_sum: bool = True):
        """
        Calculate the tails mass flow for a given prototype or list of prototypes.
        This function computes the tails mass flow based on the tails-to-product ratio
        and the enrichment levels of the specified prototypes.

        Parameters
        ----------
        prototype : str or list of str
            Name(s) of the prototype(s) to analyze.
        natu_assay : float
            Enrichment level of the natural uranium, expressed as a decimal.
        tails_assay : float
            Enrichment level of the tails material, expressed as a decimal.
        return_sum : bool, optional
            If True, returns a single array summed over all prototypes. Default is True.

        Returns
        -------
        nat : dict[str, np.ndarray] or np.ndarray
            Tails mass flow for each prototype, or total if return_sum=True.
        """
        # Convert prototype to a numpy array
        prototype = np.atleast_1d(prototype)

        # Get fuel demand and enrichment for the specified prototypes, separately for each
        fuel_mass_flow, enrichment = self.get_fuel_mass_and_enrichment(prototype, return_sum=False)

        # Construct a dictionary per prototype
        nat = {}
        for p in prototype:
            # Calculate the tails-to-product ratio for the current prototype
            tails_to_product_ratio = self.tails_to_product_ratio(natu_assay, enrichment[p], tails_assay)
            # Multiply the ratio by the product (fuel demand)
            nat[p] = fuel_mass_flow[p] * tails_to_product_ratio

        # Sum over all prototypes if requested
        if return_sum:
            nat = np.sum(list(nat.values()), axis=0)
        return nat

    def stock_fuel_swu(self, prototype:str | list[str],
                       natu_assay:float,
                       tails_assay:float,
                       return_sum: bool = True,
                       split_cat:bool=False,
                       cascade_splits:list[float]=[0.1, 0.2],):
        """
        Calculate the separative work unit (SWU) for a given prototype or list of prototypes.
        This function computes the SWU based on the enrichment levels of the specified prototypes.

        Parameters
        ----------
        prototype : str or list of str
            Name(s) of the prototype(s) to analyze.
        natu_assay : float
            Enrichment level of the natural uranium, expressed as a decimal.
        tails_assay : float
            Enrichment level of the tails material, expressed as a decimal.
        return_sum : bool, optional
            If True, returns a single array summed over all prototypes. Default is True.

        Returns
        -------
        swu : dict[str, np.ndarray] or np.ndarray
            SWU for each prototype, or total if return_sum=True.
        """
        # Convert prototype to a numpy array
        prototype = np.atleast_1d(prototype)

        # Get fuel mass and enrichment for the specified prototypes, separately for each
        fuel_mass, enr = self.get_fuel_mass_and_enrichment(prototype, return_sum=False)
        uniq_enr = {round(float(e), 8) for p in prototype for e in enr[p] if e > 0} # unique enrichments, rounded to avoid truncation errors

        # Calculate the SWU split for each category for unique enrichments if needed
        if split_cat:
            from .enr_utils import calculate_swu_split
            SWU_splits = {}
            for e in uniq_enr:
                SWU_splits[e] = np.asarray(
                    calculate_swu_split(
                        e,
                        tailing_enr=tails_assay,
                        feed_enr=natu_assay,
                        cascade_splits=cascade_splits,
                    ),
                    dtype=float,
                )
        swu = {}
        zeros = np.zeros(len(cascade_splits) + 1)

        for p in prototype:
            if not split_cat:
                ratio = self.SWU_to_product_ratio(natu_assay, enr[p], tails_assay)
                swu[p] = fuel_mass[p] * ratio
            else:
                # map each enrichment to its cached split
                multistage_swu = np.array(
                    [
                        SWU_splits.get(round(float(e), 8), zeros) # Return zeros if enrichment not found
                        if e > 0 else zeros
                        for e in enr[p]
                    ],
                    dtype=float,
                )
                swu[p] = fuel_mass[p] * multistage_swu.T

        return sum(swu.values()) if return_sum else swu
    
