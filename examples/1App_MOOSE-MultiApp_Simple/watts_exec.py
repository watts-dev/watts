# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example provides a demonstration on how to use WATTS to perform a simple
simulation leveraging MOOSE's MultiApps system.
"""

from pathlib import Path
import os

import watts

params = watts.Parameters()

# Cladding Parameters
params['Initial_Temp'] = 1400.0 # K
params['Swelling_Coefficient'] = 3000.0 # K.

params.show_summary(show_metadata=False, sort_by='key')

# MOOSE Workflow
# set your BISON directory as BISON_DIR

app_dir = Path(os.environ["BISON_DIR"])
moose_plugin = watts.PluginMOOSE(
    'main.tmpl',
    executable=app_dir / 'bison-opt',
    extra_inputs=['main_in.e', 'sub.i']
)
moose_result = moose_plugin(params)
for key in moose_result.csv_data:
    print(key, moose_result.csv_data[key])
print(moose_result.inputs)
print(moose_result.outputs)
