# SPDX-FileCopyrightText: 2024 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
from typing import List, Optional
import math
import pandas as pd
import numpy as np
import h5py as h5 
import json

from .plugin import Plugin, PluginGeneric, _find_executable
from .results import Results, ExecInfo
from .fileutils import PathLike
from .parameters import Parameters
from .template import TemplateRenderer


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
        Dictionary of cumulative material stored in the model at each time point by agent type and material type
    flows
        Dictionary of material that has entered an agent between each time point by agent type and material type
    operations
        Dictionary of facility operational data (e.g., power produced or material throughput)
    output_data
        Dictionary with information on structure of other dictionaries (model times and nuclides)

    stdout
        standard output from a DYMOND run
    """

    def __init__(self, params: Parameters, exec_info: ExecInfo,
                 inputs: List[Path], outputs: List[Path]):
        super().__init__(params, exec_info, inputs, outputs)
        self.stocks, self.flows, self.operations, self.output_data = self._get_dymond_json_data()

    def _get_dymond_json_data(self) -> dict:
        """Read abbreviated DYMOND output JSON files and return it as dictionaries"""
        for oup in self.outputs:
            if "stocks" in str(oup):
                stocks_dict = json.loads(oup.read_text())
            elif "flows" in str(oup):
                flows_dict = json.loads(oup.read_text())
            elif "operations" in str(oup):
                operations_dict = json.loads(oup.read_text())
            elif "output" in str(oup):
                output_data_dict = json.loads(oup.read_text())
        
        return(stocks_dict, flows_dict, operations_dict, output_data_dict)

    def stock_fuel_natu(self, reactor: str,
                              natu_assay: float,
                              tails_assay: float):
        """
        calculate the amount of natural uranium to fabricate the loaded fuel based on the input 
        definition and the mass flow in the json flows output. This function is only to be used
        when the fuel is fabricated from some initial stock.

        Parameters:
        -----------
        reactor: str
            the name of the reactor type to calculate the natural uranium for
        natu_assay: float
            the fraction of u235 in natural uranium
        tails_assay: float
            the fraction of u235 in the enrichment tails
        
        Returns:
        ----------
        natu: numpy array<float>
            array of annual natural uranium equivalent inputs
        """

        for inp in self.inputs:
            if ".input" in str(inp):
                input_dict = json.loads(inp.read_text())

        flows_dict = self.flows

        for r in input_dict["types"]["reactor"]:
            if(r["name"] == reactor):
                fuel_material_recipe = r["fuel"]

        fuel_composition = {}
        for fuel_mat in fuel_material_recipe:
            for event in input_dict["events"]:
                if fuel_mat in event["parameters"].keys():
                    for nuclide, mass in event["parameters"][fuel_mat].items():
                        comp_mass = fuel_material_recipe[fuel_mat]*mass
                        if nuclide in fuel_composition:
                            fuel_composition[nuclide] += comp_mass
                        else:
                            fuel_composition[nuclide] = comp_mass
                        
        u235_mass = fuel_composition["u235"]
        u_mass = 0.0
        for nuclide in fuel_composition:
            if nuclide.startswith("u"):
                u_mass += fuel_composition[nuclide]

        enrichment = u235_mass/u_mass

        fuel_mass_flow = np.array(flows_dict["TOTAL"][reactor])
        natu = fuel_mass_flow*(enrichment-tails_assay)/(natu_assay-tails_assay)
        
        return(natu)

    def stock_fuel_swu(self, reactor: str,
                             feed_assay:float,
                             tails_assay:float):
        """
        calculate the amount of total swu to fabricate the loaded fuel based on the input 
        definition and the mass flow in the json flows output. This function is only to be used
        when the fuel is fabricated from some initial stock.

        Parameters:
        -----------
        reactor: str
            the name of the reactor type to calculate the natural uranium for
        natu_assay: float
            the fraction of u235 in natural uranium
        tails_assay: float
            the fraction of u235 in the enrichment tails

        Returns:
        ----------
        natu: numpy array<float>
            array of annual total swu for equivalent fuel
        """

        for inp in self.inputs:
            if ".input" in str(inp):
                input_dict = json.loads(inp.read_text())

        flows_dict = self.flows


        for r in input_dict["types"]["reactor"]:
            if(r["name"] == reactor):
                fuel_material_recipe = r["fuel"]

        fuel_composition = {}
        for fuel_mat in fuel_material_recipe:
            for event in input_dict["events"]:
                if fuel_mat in event["parameters"].keys():
                    for nuclide, mass in event["parameters"][fuel_mat].items():
                        comp_mass = fuel_material_recipe[fuel_mat]*mass
                        if nuclide in fuel_composition:
                            fuel_composition[nuclide] += comp_mass
                        else:
                            fuel_composition[nuclide] = comp_mass
                        
        u235_mass = fuel_composition["u235"]
        u_mass = 0.0
        for nuclide in fuel_composition:
            if nuclide.startswith("u"):
                u_mass += fuel_composition[nuclide]

        enrichment = u235_mass/u_mass

        fuel_mass_flow = np.array(flows_dict["TOTAL"][reactor])
        swu = np.array([swu_calc(fuel_mass_flow[i], enrichment, tails_assay, feed_assay)[2] for i in range(len(fuel_mass_flow))])

        return(swu)    



    def stock_fuel_swu_2stage(self, reactor: str,
                                    feed_assays:np.array, 
                                    tails_assays:np.array):
        """
        calculate the amount of total swu to fabricate the loaded fuel based on the input 
        definition and the mass flow in the json flows output. This function is only to be used
        when the fuel is fabricated from some initial stock.

        Parameters:
        -----------
        reactor: str
            the name of the reactor type to calculate the natural uranium for
        natu_assays: np.array<float>
            the fraction of u235 in natural uranium
        tails_assays: np.array<float>
            the fraction of u235 in the enrichment tails

        Returns:
        ----------
        natu: np.array<np.array<float>>
            array of annual swu required for each stage
        """

        for inp in self.inputs:
            if ".input" in str(inp):
                input_dict = json.loads(inp.read_text())

        flows_dict = self.flows


        for r in input_dict["types"]["reactor"]:
            if(r["name"] == reactor):
                fuel_material_recipe = r["fuel"]

        fuel_composition = {}
        for fuel_mat in fuel_material_recipe:
            for event in input_dict["events"]:
                if fuel_mat in event["parameters"].keys():
                    for nuclide, mass in event["parameters"][fuel_mat].items():
                        comp_mass = fuel_material_recipe[fuel_mat]*mass
                        if nuclide in fuel_composition:
                            fuel_composition[nuclide] += comp_mass
                        else:
                            fuel_composition[nuclide] = comp_mass
                        
        u235_mass = fuel_composition["u235"]
        u_mass = 0.0
        for nuclide in fuel_composition:
            if nuclide.startswith("u"):
                u_mass += fuel_composition[nuclide]

        enrichment = u235_mass/u_mass

        fuel_mass_flow = np.array(flows_dict["TOTAL"][reactor])
        swu = multistage_swu_calc(fuel_mass_flow, enrichment, feed_assays, tails_assays) 

        return(swu[0])



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

        return(np.array(operations_dict["reactors"][reactor]))

    
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

        return(np.array(flows_dict["TOTAL"][reactor]))


    def reprocessed_mass(self, reprocess_plant: str):
        """
             retrieves the total reprocessing utilization data from the flows json output

            Parameters:
            -----------
            reprocess_plant: str
                the name of the reprocessing plant type to get the mass flow data for

            Returns:
            -----------
            numpy.array<float>
                the annual reprocessing info for the reprocessing plant type           
        
        """

        flows_dict = self.flows

        return(np.array(flows_dict["TOTAL"][reprocess_plant]))


    def cumulative_waste_mass(self, material: str, storage: str):
        """
             retrieves the cumulative waste data from the stocks json output

            Parameters:
            -----------
            material: str
                the name of the waste material to get data for
            storage: str
                the name of the storage type where the material is stored

            Returns:
            -----------
            numpy.array<float>
                the total mass of waste being stored each year          
        
        """

        stocks_dict = self.stocks

        return(np.array(stocks_dict[storage][material]))
        



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


    def __init__(self, 
                 template_file: PathLike,
                 executable: PathLike = 'dymond.sh',
                 extra_inputs: Optional[List[str]] = None,
                 extra_template_inputs: Optional[List[PathLike]] = None,
                 show_stdout: bool = False,
                 show_stderr: bool = False):
        
        executable = _find_executable(executable, 'DYMOND_DIR')
        execute_command = ['{self.executable}', '-i', '{self.input_name}']

        super().__init__(executable, execute_command, template_file, extra_inputs,
                         extra_template_inputs, "DYMOND", show_stdout, show_stderr)     
        
        self.input_name = "DYMOND_input"

    @PluginGeneric.executable.setter
    def executable(self, exe: PathLike):
        if not exe.is_file():
            raise RuntimeError(
                f"{self.plugin_name} module '{exe}' does not exist. The "
                "DYMOND_DIR environment variable needs to be set to a directory "
                "containing the DYMOND scripts and model modules."
            )
        self._executable = Path(exe)    



def swu_calc(product, Xproduct, Xtails, Xfeed):
#product is the mass or rate of enriched uranium (np.array)
#The X variables are the mass fraction of U235 of the respective masses (floats)
    Vp = (2*Xproduct-1)*math.log(Xproduct/(1-Xproduct))
    Vt = (2*Xtails-1)*math.log(Xtails/(1-Xtails))
    Vf = (2*Xfeed-1)*math.log(Xfeed/(1-Xfeed)) 
    F = 0
    T = 0
    

    P = product
    T = (Xproduct-Xfeed)/(Xfeed-Xtails)*P
    F = T + P
    swu = P*Vp + Vt*T - Vf*F
    
    return(T, F, swu)

def swuStages(product, p_assay, feed_assays, tails_assays):
    #This function calculates the SWU, products masses, feed masses, and tails masses by stage
    #for a multi-stage enrichment scheme in an ideal configuration (i.e. t(n) = f(n-1), p(n) = f(n+1))
    #product: the mass of the final enriched product in kg
    #p_assay: the enrichment fraction of the final product
    #feed_assays: the enrichment of the feed for each stage of enrichment
    #tails_assays: the enrichment of the tails coming out of each stage of enrichment
    
    swu_demand = np.zeros(len(feed_assays))
    feeds = np.zeros(len(feed_assays))
    products = np.zeros(len(feed_assays))
    tails = np.zeros(len(feed_assays))
    xp = p_assay
    T1 = 0
    for n in range(len(feeds), 0, -1):
        #Stage is only needed if the enrichment is higher than the input feed
        if p_assay > feed_assays[n-1]:
            if products[n-1] == 0.0:
                products[n-1] = product
            tails[n-1], feeds[n-1], swu_demand[n-1] = swu_calc(products[n-1], xp, tails_assays[n-1], feed_assays[n-1])
            feeds[n-1] -= T1
            xp = feed_assays[n-1]
            if n > 1:
                products[n-2] = feeds[n-1]
                
            T1 = tails[n-1]
    
    return(swu_demand, products, feeds, tails)

def multistage_swu_calc(product, p_assay, feed_assays, tails_assays):
    swu_demand = np.zeros([len(product), len(feed_assays)])
    product_streams = np.zeros([len(product), len(feed_assays)])
    feed_streams = np.zeros([len(product), len(feed_assays)])
    tails_streams = np.zeros([len(product), len(feed_assays)])

    for y in range(len(product)):
        swu, p, f, t = swuStages(product[y], p_assay, feed_assays, tails_assays)
        for s in range(len(feed_assays)):
            swu_demand[y][s] = swu[s]
            product_streams[y][s] = p[s]
            feed_streams[y][s] = f[s]
            tails_streams[y][s] = t[s]


    return(swu_demand, product_streams, feed_streams, tails_streams)