# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

#########################################################
# Example problem of runing SAS4A/SASSY-1 with WATTS.
# This is a steady-state, single pin problem with uniform 
# dimensions and constant properties. The fuel pin has a
# constant linear heat generation and the boundaries of 
# the problem are the top and bottom of the fuel pin. 
# Sodium coolant enters from the bottom. The fuel pin is
# separated into a bottom unheated section, fuel section,
# gas plenum, and top unheated section. This problem DOES
# NOT use the PRIMAR4 module.
#########################################################

from math import cos, pi
import os
import watts
from astropy.units import Quantity


params = watts.Parameters()

# Channel params
params['sas_version'] = 5.5
params['tmax'] = 400.0 # maximum problem time in s
params['flow_per_pin'] = 0.15 # kg/s
params['total_reactor_power'] = Quantity(182, "MW") # 182000000.0 W
params['betai_1'] = 2.0E-04 # Effective delayed neutron fraction
params['betai_2'] = 1.0E-03
params['betai_3'] = 1.2E-03
params['betai_4'] = 2.5E-03
params['betai_5'] = 1.5E-03
params['betai_6'] = 5.0E-04

params.show_summary(show_metadata=False, sort_by='key')

# SAS Workflow
# Set SAS directory as sas_dir (SAS_DIR is environment variable)
# Linux and macOS have different executables but both are ".x".
# The Windows executable is ".exe". 
# SAS executable and post-processing utilities are assumed to be
# in the same directory in this example.
sas_dir = os.environ["SAS_DIR"] 
sas_plugin = watts.PluginSAS('sas_template') # Show all the output
sas_plugin.sas_exec = sas_dir + "/sas.x" # SAS executable
sas_plugin.conv_channel = sas_dir + "/CHANNELtoCSV.x" # SAS utility to convert "CHANNEL.dat" files to ".csv"
sas_plugin.conv_primar4 = sas_dir + "/PRIMAR4toCSV.x" # SAS utility to convert "PRIMAR4.dat" files to ".csv"
sas_result = sas_plugin.workflow(params)
for key in sas_result.csv_data:
    print(key, sas_result.csv_data[key])
print(sas_result.inputs)
print(sas_result.outputs)
