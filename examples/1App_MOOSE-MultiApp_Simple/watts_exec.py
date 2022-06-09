# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example provides a demonstration on how to use WATTS to perform a simple simulation leveraging MOOSE's MultiApps system.
"""

from math import cos, pi
import os
import watts

params = watts.Parameters()

# Cladding Parameters
params['Initial_Temp'] = 1400.0 # K
params['Swelling_Coefficient'] = 3000.0 # K.

params.show_summary(show_metadata=False, sort_by='key')

# MOOSE Workflow
# set your BISON directorate as BISON_DIR

moose_app_type = "bison"
app_dir = os.environ[moose_app_type.upper() + "_DIR"]
moose_plugin = watts.PluginMOOSE('main.tmpl', extra_inputs=['main_in.e', 'sub.i'])
moose_plugin.executable = app_dir + "/" + moose_app_type.lower() + "-opt"
moose_result = moose_plugin(params)
for key in moose_result.csv_data:
    print(key, moose_result.csv_data[key])
print(moose_result.inputs)
print(moose_result.outputs)
