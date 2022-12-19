# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
Example problem of runing SAS4A/SASSY-1 with WATTS using the 
SAS 'INCLUDE' directive that allows for multiple input files. 
This example uses the same sodium loop model as in 
example '1App_SAS_SodiumLoop'. For details on the loop,
please refer to the input file of '1App_SAS_SodiumLoop'.
In this example, the SAS input file is broken into several
input files, namely 'Channel', 'DecayPower', 'FuelCladding',
'PointKinetics', 'PRIMAR4', and 'Primary', and the main 
input file is known as 'sas_template'. The values of any
parameters in the extra input files can be input/changed
using the same approach as the parameters in the main input 
file. To include the input files to the simulation, users 
need to add 'INCLUDE "Extra_file_name"' in the main input file. 
"""

from math import cos, pi
import os
import watts
from astropy.units import Quantity


params = watts.Parameters()

# Channel params
params['sas_version'] = 5.5
params['tmax'] = 1000.0 # maximum problem time in s
params['flow_per_pin'] = 0.15 # kg/s
params['total_reactor_power'] = Quantity(20, "kW")
params['betai_1'] = 2.0E-04 # Effective delayed neutron fraction
params['betai_2'] = 1.0E-03
params['betai_3'] = 1.2E-03
params['betai_4'] = 2.5E-03
params['betai_5'] = 1.5E-03
params['betai_6'] = 5.0E-04
params['fuel_axial_exp_coeff'] = 2.0E-05 # Fuel axial expansion coefficient
params['clad_axial_exp_coeff'] = 1.4E-05 # Clad axial expansion coefficient
params['outlet_pressure'] = 200000.0 # Outlet plenum pressure

params.show_summary(show_metadata=False, sort_by='key')

# SAS Workflow
# template_file: Main input file
# extra_template_inputs: Additional templated input files
sas_plugin = watts.PluginSAS(
    template_file='sas_template',
    extra_template_inputs=['Primary', 'FuelCladding', 'Channel', 'DecayPower', 'PointKinetics', 'PRIMAR4']
    )

sas_result = sas_plugin(params)
for key in sas_result.csv_data:
    print(key, sas_result.csv_data[key])
print(sas_result.inputs)
print(sas_result.outputs)
