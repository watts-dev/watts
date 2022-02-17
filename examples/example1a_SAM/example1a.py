# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from math import cos, pi
import os
import watts
from astropy import units as u

# Uses Astropy for unit conversion
u.imperial.enable()    # Enable imperial units
Quantity = u.Quantity

params = watts.Parameters()

# TH params

params['He_inlet_temp'] = Quantity(600, "Celsius")  # 873.15 K
params['He_outlet_temp'] = Quantity(850, "Celsius") # 1123.15 K
params['He_cp'] = Quantity(4.9184126, "BTU/(kg*K)") # 5189.2 J/kg-K
params['He_K'] =  0.32802   # W/m-K
params['He_density'] = 3.8815   # kg/m3
params['He_viscosity'] = 4.16e-5 # Pa.s
params['He_Pressure'] = Quantity(1015.264164, "psi") # 7e6 Pa
params['Tot_assembly_power'] = 250000 # W

for i in range(1, 6):
    params[f'Init_P_{i}'] = 1 # Fraction

# Core design params - some are not used in SAM model
params['ax_ref'] = 20 # cm
params['num_cool_pins'] = 1*6+2*6+6*2/2
params['num_fuel_pins'] = 6+6+6+3*6+2*6/2+6/3
params['Height_FC'] = Quantity(2000, "mm") # Automatically converts to 'm' for MOOSE and 'cm' for openmc 
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
params['control_pin_rad'] = Quantity(9.9, "mm") # Automatically converts to 'm' for MOOSE and 'cm' for openmc

params.show_summary(show_metadata=False, sort_by='key')

# MOOSE Workflow
# set your SAM directorate as SAM_DIR

moose_app_type = "SAM"
app_dir = os.environ[moose_app_type.upper() + "_DIR"]
moose_plugin = watts.PluginMOOSE(moose_app_type.lower() + '_template') # show all the output
moose_plugin.moose_exec = app_dir + "/" + moose_app_type.lower() + "-opt"
moose_result = moose_plugin.workflow(params)
for key in moose_result.csv_data:
    print(key, moose_result.csv_data[key])
print(moose_result.inputs)
print(moose_result.outputs)