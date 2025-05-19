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
        q = self.obj.cur.execute('SELECT distinct(commodity) FROM transactions').fetchall()
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
    this class also provides a custom Jinja filter called ``expand_element``
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
        q = self.cur.execute('SELECT prototype, entertime, lifetime, Spec, value FROM agententry INNER JOIN timeseriespower ON agententry.agentid = timeseriespower.agentid WHERE agententry.spec LIKE "%Reactor" AND value != 0 GROUP BY agententry.agentid').fetchall()
        duration = self.cur.execute('SELECT InitialYear, InitialMonth, Duration FROM Info').fetchone()
        init_year = duration['InitialYear']
        init_month = duration['InitialMonth']
        duration = duration['Duration']
        time = init_year + (np.arange(duration)+init_month-1)/12
        years = time
        return {'init_year': init_year, 'init_month': init_month,
                'duration': duration, 'years': years}


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
        q = self.cur.execute('SELECT prototype, entertime, lifetime, Spec, value FROM agententry INNER JOIN timeseriespower ON agententry.agentid = timeseriespower.agentid WHERE agententry.spec LIKE "%Reactor" AND value != 0 GROUP BY agententry.agentid').fetchall()

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
    
    def get_proto_ids(self, proto_name):
        if isinstance(proto_name, list):
            ps = ', '.join([f'"{str(q)}"' for q in proto_name])
            query = self.cur.execute(f'SELECT agentid FROM agententry WHERE prototype IN ({ps})').fetchall()
        else:
            query = self.cur.execute(f'SELECT agentid FROM agententry WHERE prototype=="{proto_name}"').fetchall()
        return [x['agentid'] for x in query]


    def get_commodities(self):
        query = self.cur.execute('SELECT distinct(commodity) FROM transactions').fetchall()
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
        query = self.cur.execute(f'''SELECT sum(quantity), time FROM transactions INNER JOIN resources
                        ON transactions.resourceid = resources.resourceid WHERE Commodity="{commodity_name}"
                        GROUP BY time''').fetchall()
        return np.array(self.get_yearly_sum(self.query_to_array(query, self.duration, 'time', 'sum(quantity)')))


    def get_nucids(self):
        query = self.cur.execute('SELECT distinct(nucid) FROM compositions').fetchall()
        nucids = np.array(sorted([q['nucid'] for q in query]))
        return nucids


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
        query = self.cur.execute(f'SELECT distinct(commodity) FROM transactions WHERE receiverid IN ({csv})').fetchall()
        return [q['commodity'] for q in query]


    def get_facility_agents(self, spec_keywords=None):
        """Returns all facility agents in the simulation

        Returns:
            dict: key: int(id), value: str(prototype)
        """
        if not spec_keywords:
            query = self.cur.execute('SELECT distinct(agentid), prototype FROM agententry WHERE kind=="Facility"').fetchall()
        else:
            query = self.cur.execute(f'SELECT distinct(agentid), prototype FROM agententry WHERE kind=="Facility" and spec LIKE "%{spec_keywords}%" --case-insensitive').fetchall()
        agents = {q['agentid']:q['prototype'] for q in query}
        return agents


    def get_products(self):
        # get product tables
        product_dict = {}
        query = self.cur.execute('select name from sqlite_master where type="table";').fetchall()
        tables = [q['name'] for q in query if 'TimeSeries' in q['name']]
        # kill ones with timeseriessupply or timeseriesdemand
        tables = [q for q in tables if 'TimeSeriessupply' not in q]
        tables = [q for q in tables if 'TimeSeriesdemand' not in q]
        for table in tables:
            key = table.replace('TimeSeries', '')
            product_dict[key] = {}
            # get unique agentids
            query = self.cur.execute(f'SELECT distinct(agentid) FROM {table}').fetchall()
            agentids = [q['agentid'] for q in query]
            # get production timeseries
            for agentid in agentids:
                query = self.cur.execute(f'SELECT sum(value), time FROM {table} WHERE agentid=={agentid} GROUP BY time').fetchall()
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
                query = self.cur.execute(f'SELECT agentid FROM agententry WHERE prototype IN ({ps})').fetchall()
            else:
                query = self.cur.execute(f'SELECT agentid FROM agententry WHERE prototype == "{proto}"').fetchall()
            ids = [q['agentid'] for q in query]
            id_str = ', '.join([str(q) for q in ids])
            query = self.cur.execute(f'SELECT distinct(commodity) FROM transactions WHERE {c} IN ({id_str})').fetchall()
            trade_commods = [q['commodity'] for q in query]

            for commod in trade_commods:
                if not get_isotopics:
                    query = self.cur.execute(f'''SELECT sum(quantity), time FROM transactions INNER JOIN resources
                                              ON transactions.resourceid = resources.resourceid WHERE {c} in ({id_str})
                                             AND commodity=="{commod}" GROUP BY time''').fetchall()
                    flow_dict[key][commod] = self.get_yearly_sum(self.query_to_array(
                        query, self.duration, nucids=[], time_label='time', value_label='sum(quantity)'))
                else:
                    # isotopics
                    query = self.cur.execute(f'''SELECT time, nucid, sum(quantity * massfrac) AS nucmass FROM transactions
                                         JOIN resources ON transactions.resourceid = resources.resourceid
                                         JOIN compositions on resources.qualid = compositions.qualid
                                         WHERE {c} in ({id_str}) AND commodity=="{commod}"
                                         GROUP BY time, nucid''').fetchall()
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
            query = self.cur.execute(f'SELECT distinct(commodity) FROM transactions WHERE {c}=={id}').fetchall()
            trade_commods = [q['commodity'] for q in query]
            
            for commod in trade_commods:
                if not get_isotopics:
                    query = self.cur.execute(f'''SELECT sum(quantity), time FROM transactions INNER JOIN resources
                                              ON transactions.resourceid = resources.resourceid WHERE {c}=={id}
                                             AND commodity=="{commod}" GROUP BY time''').fetchall()
                    flow_dict[key][commod] = self.get_yearly_sum(self.query_to_array(
                        query, self.duration, nucids=[], time_label='time', value_label='sum(quantity)'))
                else:
                    # isotopics
                    query = self.cur.execute(f'''SELECT time, nucid, sum(quantity * massfrac) AS nucmass FROM transactions
                                         JOIN resources ON transactions.resourceid = resources.resourceid
                                         JOIN compositions on resources.qualid = compositions.qualid
                                         WHERE {c}=={id} AND commodity=="{commod}"
                                         GROUP BY time, nucid''').fetchall()
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

    def get_fuel_mass_and_enrichment(self, prototype:str):
        flow_into = self.process_prototype(prototype, False)[1]['receiving']
        tot_u235 = self.get_yearly_sum(np.zeros(self.duration))
        for commod, fuel_mass_flow in flow_into.items():
            # commod = list(flow_into.keys())[0]
            agentids = self.get_proto_ids(prototype)
            # fuel_mass_flow = list(flow_into.values())[0]
            enr = self.get_enrichments(commod, receiver_agentids=agentids)
            tot_u235 += enr * fuel_mass_flow

        return sum(flow_into.values()), np.nan_to_num(tot_u235 / sum(flow_into.values()), nan=0)


    def stock_fuel_natu(self, prototype:str,
                        natu_assay:float,
                        tails_assay:float):
        fuel_mass_flow, enr = self.get_fuel_mass_and_enrichment(prototype)
        return fuel_mass_flow*(enr-tails_assay)/(natu_assay-tails_assay)


    def stock_fuel_swu(self, prototype:str,
                       natu_assay:float,
                       tails_assay:float,
                       split_cat:bool=False):
        fuel_mass_flow, enr = self.get_fuel_mass_and_enrichment(prototype)
        if split_cat:
            from .enr_utils import calculate_swu_split_cats
            swu = calculate_swu_split_cats(natu_assay, tails_assay, enr)
            swu = fuel_mass_flow * swu[:,None]
            print('Returning 2D array of shape ', swu.shape)
            return swu
        else:
            from .enr_utils import calculate_swu
            swu = calculate_swu(natu_assay, tails_assay, enr)
            return fuel_mass_flow * swu
    




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
            query = self.cur.execute('''SELECT sum(quantity), time FROM transactions INNER JOIN resources
                        ON transactions.resourceid = resources.resourceid WHERE Commodity="%s"
                        GROUP BY time''' %ff).fetchall()
            fuel_flow_array[indx, :] = np.array(self.get_yearly_sum(self.query_to_array(query, self.duration, time_label='time', value_label='sum(quantity)')))
        return fuel_flow_array


    def get_enrichments(self, commod, receiver_agentids=None):
        # get u235 flow
        if receiver_agentids:
            csv = ','.join([str(q) for q in receiver_agentids])
            query = self.cur.execute(f'''SELECT time, nucid, sum(quantity), sum(quantity * massfrac) AS nucmass FROM transactions
                                            JOIN resources ON transactions.resourceid = resources.resourceid
                                            JOIN compositions on resources.qualid = compositions.qualid
                                            WHERE commodity=="{commod}" AND nucid==922350000 AND receiverid IN ({csv})
                                            GROUP BY time, nucid''').fetchall()
        else:
            query = self.cur.execute(f'''SELECT time, nucid, sum(quantity), sum(quantity * massfrac) AS nucmass FROM transactions
                                            JOIN resources ON transactions.resourceid = resources.resourceid
                                            JOIN compositions on resources.qualid = compositions.qualid
                                            WHERE commodity=="{commod}" AND nucid==922350000
                                            GROUP BY time, nucid''').fetchall()
        u235_mass = self.query_to_array(query, self.duration, time_label='time', value_label='nucmass')
        u235_mass_annual = np.array(self.get_yearly_sum(u235_mass))
        all_mass = self.query_to_array(query, self.duration, time_label='time', value_label='sum(quantity)')
        all_mass_annual = np.array(self.get_yearly_sum(all_mass))
        return np.nan_to_num(u235_mass_annual / all_mass_annual, nan=0)


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
        '''
        Parameters:
        -----------
        arr: numpy array
            1D array of length that typically corresponds to the number 
            of time steps in a simulation, with data for each time step.

        Returns:
        --------
        newarr: numpy array
            length is the number of years in a simulations (i.e., 
            length of arr/12) with the data from arr summed up for each 
            year 
        '''
        newarr = []
        c = 0
        for indx, val in enumerate(arr):
            if indx%12 == 0:
                newarr.append(c)
                c = 0
            c += val
        return np.array(newarr[:])
