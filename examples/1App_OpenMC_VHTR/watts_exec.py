# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to perform
OpenMC calculation. This example uses a simple VHTR unit-cell
model with 1 coolant channel surrounded by graphite and fuel.
The demonstration includes the application of unit-conversion
approach in WATTS. OpenMC is executed and the main results are
printed out and stored in the params database.
"""

from math import cos, pi
import os
import watts
from statistics import mean
from openmc_template import build_openmc_model
import openmc
from astropy.units import Quantity


params = watts.Parameters()

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
params['control_pin_rad'] = Quantity(9.9, "mm") # Automatically converts to 'm' for MOOSE and 'cm' for openmc

# Control use of S(a,b) tables
params['use_sab'] = True
params['use_sab_BeO'] = True
params['use_sab_YH2'] = False

# OpenMC params
params['cl'] = params['Height_FC']*100 - 2 * params['ax_ref'] # cm
params['pf'] = 40 # percent

# get temperature from SAM results
params['temp'] = Quantity(725, "Celsius")
for i in range(1, 6):
    params[f'temp_F{i}'] = Quantity(725, "Celsius")

params.show_summary(show_metadata=False, sort_by='time')

# Create OpenMC plugin
openmc_plugin = watts.PluginOpenMC(build_openmc_model, show_stderr=True) # show only error

# Run OpenMC plugin, instructing it to plot the geometry and run a simulation
def run_func():
    openmc.plot_geometry()
    openmc.run()
openmc_result = openmc_plugin(params, function=run_func)
print("KEFF = ", openmc_result.keff)
print(openmc_result.inputs)
print(openmc_result.outputs)
print(openmc_result.tallies[0].get_pandas_dataframe())

power_fractions = openmc_result.tallies[0].get_values(scores=['nu-fission']).ravel()
for i, power_frac in enumerate(power_fractions):
    params[f'Init_P_{i+1}'] = power_frac

params.show_summary(show_metadata=True, sort_by='time')
