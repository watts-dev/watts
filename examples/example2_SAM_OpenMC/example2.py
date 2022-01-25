# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from math import cos, pi
import os
import watts
from statistics import mean
from openmc_template import build_openmc_model


params = watts.Parameters()

# TH params

params['He_inlet_temp'] = {"value":600, "current_unit": "Celsius", "new_unit": "Kelvin"}  #873.15 K
params['He_outlet_temp'] = 850 + 273.15 # K
params['He_cp'] = {"value": 4.9184126, "current_unit": "BTU/(kg*K)", "new_unit": "J/(kg*K)"} #5189.2 J/kg-K
params['He_K'] =  0.32802   # W/m-K
params['He_density'] = 3.8815   # kg/m3
params['He_viscosity'] = 4.16e-5 # Pa.s
params['He_Pressure'] = {"value":1015.264164, "current_unit": "psi", "new_unit": "pascal"}  #7e6 Pa
params['Tot_assembly_power'] = 250000 # W

for i in range(1, 6):
    params[f'Init_P_{i}'] = 1 # Fraction

# Core design params
params['ax_ref'] = 20 # cm
params['num_cool_pins'] = 1*6+2*6+6*2/2
params['num_fuel_pins'] = 6+6+6+3*6+2*6/2+6/3
params['Height_FC'] = 2.0 # m
params['Lattice_pitch'] = 2.0
params['FuelPin_rad'] = 0.90 # cm
params['cool_hole_rad'] = 0.60 # cm
params['Coolant_channel_diam'] = (params['cool_hole_rad'] * 2)/100 # in m
params['Graphite_thickness'] = (params['Lattice_pitch'] - params['FuelPin_rad'] - params['cool_hole_rad']) # cm
params['Assembly_pitch'] = 7.5 * 2 * params['Lattice_pitch'] / (cos(pi/6) * 2)
params['lbp_rad'] = 0.25 # cm
params['mod_ext_rad'] = 0.90 # cm
params['shell_thick'] = 0.05   # FeCrAl
params['liner_thick'] = 0.007  # Cr
params['control_pin_rad'] = {"value": 0.3897638, "current_unit": "inch"} # Automatically converts to 'm' for MOOSE and 'cm' for openmc

# Control use of S(a,b) tables
params['use_sab'] = True
params['use_sab_BeO'] = True
params['use_sab_YH2'] = False

# OpenMC params
params['cl'] = params['Height_FC']*100 - 2 * params['ax_ref'] # cm
params['pf'] = 40 # percent

# printout params
params.show_summary(show_metadata=True, sort_by='time')


# MOOSE Workflow
# set your SAM directorate as SAM_DIR

moose_app_type = "SAM"
app_dir = os.environ[moose_app_type.upper() + "_DIR"]
moose_plugin = watts.PluginMOOSE('../example1a_SAM/sam_template', show_stderr=True) # show only error
moose_plugin.moose_exec = app_dir + "/" + moose_app_type.lower() + "-opt"
moose_result = moose_plugin.workflow(params)
for key in moose_result.csv_data:
    print(key, moose_result.csv_data[key])
print(moose_result.inputs)
print(moose_result.outputs)

# get temperature from SAM results
params['temp'] = mean([moose_result.csv_data[f'avg_Tgraphite_{i}'][-1] for i in range(1, 6)])
for i in range(1, 6):
    params[f'temp_F{i}'] = moose_result.csv_data[f'avg_Tf_{i}'][-1]

params.show_summary(show_metadata=False, sort_by='time')

# Run OpenMC plugin
openmc_plugin = watts.PluginOpenMC(build_openmc_model, show_stderr=True) # show only error
openmc_result = openmc_plugin.workflow(params)
print("KEFF = ", openmc_result.keff)
print(openmc_result.inputs)
print(openmc_result.outputs)
print(openmc_result.tallies[0].get_pandas_dataframe())

power_fractions = openmc_result.tallies[0].get_values(scores=['nu-fission']).ravel()
for i, power_frac in enumerate(power_fractions):
    params[f'Init_P_{i+1}'] = power_frac

params.show_summary(show_metadata=True, sort_by='time')
