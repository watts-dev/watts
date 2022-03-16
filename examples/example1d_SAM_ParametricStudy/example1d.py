# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to perform 
multiple runs and extract selected results from the runs. 
The demonstration includes an approach to save selected 
results from different runs into a single CSV file for 
ease of comparison, visualization, post-processing.
This demonstration uses SAM with a single PbCoreChannel
with a inlet and outlet boundary conditions. The input 
power of the channel is varied. The simulation is run 
as transient where the end time is varied to artificially
create results of different lengths to show that the 
output CSV file can accept columns of different lengths.
"""

from math import cos, pi
import os
import watts
import pandas as pd
from astropy.units import Quantity


params = watts.Parameters()

# Input parameters to template file

params['He_inlet_temp'] = Quantity(600, "Celsius")  # 873.15 K
params['He_outlet_temp'] = Quantity(850, "Celsius") # 1123.15 K
params['He_cp'] = Quantity(4.9184126, "BTU/(kg*K)") # 5189.2 J/kg-K
params['He_K'] =  0.32802   # W/m-K
params['He_density'] = 3.8815   # kg/m3
params['He_viscosity'] = 4.16e-5 # Pa.s
params['He_Pressure'] = Quantity(1015.264164, "psi") # 7e6 Pa
params['num_cool_pins'] = 1*6+2*6+6*2/2
params['num_fuel_pins'] = 6+6+6+3*6+2*6/2+6/3
params['Height_FC'] = Quantity(2000, "mm") # Automatically converts to 'm' for MOOSE and 'cm' for openmc
params['Lattice_pitch'] = 2.0
params['FuelPin_rad'] = 0.90 # cm
params['cool_hole_rad'] = 0.60 # cm
params['Coolant_channel_diam'] = (params['cool_hole_rad'] * 2)/100 # in m
params['Graphite_thickness'] = (params['Lattice_pitch'] - params['FuelPin_rad'] - params['cool_hole_rad']) # cm

params.show_summary(show_metadata=False, sort_by='key')

# MOOSE Workflow
moose_app_type = "SAM"
app_dir = os.environ[moose_app_type.upper() + "_DIR"]

power = [100000, 250000, 300000, 400000, 500000] # Watts
endtime = [50, 100, 100, 50, 50] # End time is varied to artificially create results of different lengths.
results_dict = {} # Create empty dictionary
for i in range(len(power)):
    params['Tot_assembly_power'] = power[i]
    params['endtime'] = endtime[i]

    # Execute WATTS
    moose_plugin = watts.PluginMOOSE(moose_app_type.lower() + '_template') # show all the output
    moose_plugin.moose_exec = app_dir + "/" + moose_app_type.lower() + "-opt"
    moose_result = moose_plugin(params)

    # Add items to dictionary.
    results_dict['time_'+str(i+1)] = moose_result.csv_data['time']
    results_dict['max_Tcoolant_'+str(i+1)] = moose_result.csv_data['max_Tcoolant']
    results_dict['max_Tw_'+str(i+1)] = moose_result.csv_data['max_Tw']

df = pd.DataFrame(dict([(k, pd.Series(v)) for k, v in results_dict.items()])) # Store dictionary items as dataframe. Columns of unequal lengths are padded with NaN.
df.reindex(sorted(df.columns), axis=1).to_csv('results.csv') # Sort column names alphabetically and save as CSV file.