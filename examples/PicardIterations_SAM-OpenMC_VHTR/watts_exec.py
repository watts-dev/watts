# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to perform several
iterations where SAM calculations are followed by OpenMC 
calculation and temperature/power information are exchanged
until convergence. This example uses a simple VHTR unit-cell
model with 1 coolant channel surrounded by graphite and fuel.
"""

from math import cos, pi
import os
import watts
from statistics import mean
from openmc_template import build_openmc_model


params = watts.Parameters()

# TH params

params['He_inlet_temp'] = 600 + 273.15  # K
params['He_outlet_temp'] = 850 + 273.15 # K
params['He_cp'] = 5189.2 # J/kg-K
params['He_K'] =  0.32802   # W/m-K
params['He_density'] = 3.8815   # kg/m3
params['He_viscosity'] = 4.16e-5 # Pa.s
params['He_Pressure'] = 7e6    # Pa
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
params['control_pin_rad'] = 0.99 # cm

# Control use of S(a,b) tables
params['use_sab'] = True
params['use_sab_BeO'] = True
params['use_sab_YH2'] = False

# OpenMC params
params['cl'] = params['Height_FC']*100 - 2 * params['ax_ref'] # cm
params['pf'] = 40 # percent

# printout params
params.show_summary(show_metadata=True, sort_by='time')
conv_it = True
nmax_it = 5
conv_criteria = 1e-4

list_keff = []
while conv_it:
    # MOOSE Workflow
    moose_app_type = "SAM"
    app_dir = os.environ[moose_app_type.upper() + "_DIR"]
    sam_plugin = watts.PluginMOOSE('../example1a_SAM/sam_template', show_stderr=True) # show only error
    sam_plugin.moose_exec = app_dir + "/" + moose_app_type.lower() + "-opt"
    sam_result = sam_plugin(params)

    # get temperature from SAM results
    params['temp'] = mean([sam_result.csv_data[f'avg_Tgraphite_{i}'][-1] for i in range(1, 6)])
    for i in range(1, 6):
        params[f'temp_F{i}'] = sam_result.csv_data[f'avg_Tf_{i}'][-1]

    params.show_summary(show_metadata=False, sort_by='time')

    # Run OpenMC plugin
    openmc_plugin = watts.PluginOpenMC(build_openmc_model, show_stderr=True) # show only error
    openmc_result = openmc_plugin(params)
    print("KEFF = ", openmc_result.keff)
    list_keff.append(openmc_result.keff)

    power_fractions = openmc_result.tallies[0].get_values(scores=['nu-fission']).ravel()
    for i, power_frac in enumerate(power_fractions):
        params[f'Init_P_{i+1}'] = power_frac

    if len(list_keff) > 1 and (list_keff[-1]-list_keff[-2])/list_keff[-1] < conv_criteria:
        conv_it = False
        if len(list_keff) > nmax_it:
            conv_it = False
params.show_summary(show_metadata=True, sort_by='time')
print (list_keff)
