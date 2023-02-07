# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This is an example problem of running RELAP5-3D with WATTS.
The problem is a single annulus channel where the inner cylinder
is heated. The inner heater and the outer pipe wall are modeled
as heat structures. Inlet and outlet boundary conditions are
specified at the inlet and outlet of the channel. The example
also shows how to add extra input options to the execution of
RELAP5-3D.
"""

import os
import watts
from astropy.units import Quantity

from pathlib import Path

params = watts.Parameters()

# Channel params
params['inlet_pressure'] = 3.0e5
params['outlet_pressure'] = 1.013e5
params['heater_power'] = Quantity(20, "kW")


params.show_summary(show_metadata=False, sort_by='key')

# RELAP5-3D Workflow
relap5_plugin = watts.PluginRELAP5('relap5_template')

# Example of input with extra options, including explicitly specifying the
# locations of fluid files.
# relap5_plugin = watts.PluginRELAP5('relap5_template')
# relap5_plugin(params, extra_args=['-w', 'tpfh2o', '-e', 'tpfn2', '-tpfdir', 'location\of\fluid\property\files'])

# If RELAP5_DIR is not added to the environment, the directory where the
# executable and license key are stored can be specified explicitly.
# relap5_plugin.relap5_dir = "location\of\executable\and\license\key"

relap5_result = relap5_plugin(params)
for key in relap5_result.csv_data:
    print(key, relap5_result.csv_data[key])
print(relap5_result.inputs)
print(relap5_result.outputs)
