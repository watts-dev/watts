# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from math import cos, pi
import os
import watts

params = watts.Parameters()

# Cladding Parameters
params['Cladding_Thickness'] = 0.38e-03 # m
params['Cladding_Top_Gap'] = 479.5e-3 # m
params['Cladding_Side_Gap'] = 0.382e-03 # m
params['Cladding_End_Cap_Thickness'] = 2.24e-3 # m
params['Cladding_Bottom_Gap'] = 0.31e-3 # m

# Fuel Slug Parameters
params['Fuel_Outer_Radius'] = 2.158e-03 # m
params['Fuel_Length'] = 342.5e-3 # m
params['Fuel_Density'] = 16000.0 # m

# Cladding Meshing Parameters
params['Cladding_Radial_Intervals'] = 1
params['Cladding_Axial_Intervals'] = 20
params['Cladding_Upper_End_Cap_Axial_Intervals'] = 1
params['Cladding_Lower_End_Cap_Axial_Intervals'] = 1

# Fuel Meshing Parameters
params['Fuel_Radial_Intervals'] = 1
params['Fuel_Axial_Intervals'] = 1

# Coolant Channel Parameters
params['Inlet_Coolant_Temperature'] = 648.0 # K
params['Inlet_Coolant_Mass_Flux'] = 2300.0 # kg/m2/s
params['Cladding_Outer_Radius'] = params['Fuel_Outer_Radius'] + params['Cladding_Side_Gap'] + params['Cladding_Thickness'] # m
params['Wrapping_Wire_Thickness'] = 1.067e-03 # m

params.show_summary(show_metadata=False, sort_by='key')

# MOOSE Workflow
# set your BISON directorate as BISON_DIR

moose_app_type = "bison"
app_dir = os.environ[moose_app_type.upper() + "_DIR"]
moose_plugin = watts.PluginMOOSE('bison_template', show_stdout=True, n_cpu=2) # show all the output
moose_plugin.executable = app_dir + "/" + moose_app_type.lower() + "-opt"
moose_result = moose_plugin(params)
for key in moose_result.csv_data:
    print(key, moose_result.csv_data[key])
print(moose_result.inputs)
print(moose_result.outputs)
