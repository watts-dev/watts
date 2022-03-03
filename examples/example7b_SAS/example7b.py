# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

#########################################################
# Example problem of runing SAS4A/SASSY-1 with WATTS.
# This is a simple sodium loop that uses the channel (core)
# and PRIMAR-4 module. Sodium is heated in the core, then
# flows upwward through a series of pipes to a heat
# exchanger (IHX), then downward to a pump, and lastly
# back to the outlet of the core. A tank with cover gas is 
# used to provide compressible space. The design of
# loop is a simplified version of the loop by Zhang et al.
# (https://doi.org/10.1016/j.nucengdes.2021.111149). The
# dimensions of this simplified loop are arbitrarily selected.
#                         ___
#     -------------------[   ]
#    |                   [   ]
#    |                   [ I ]
#    |  P                [ H ]
#    |  I                [ X ]
#    |  P                [   ]
#    |  E                [___]
#    |                     |
#    |                     |
#    *                     |
#    *                     |
#    *                     |
#    *                     |
#    *                     |
#    *  C                  |                
#    *  O                  |              ____________
#    *  R                  |             |            |
#    *  R                  |             |            |
#    *                     |             |------------|
#    *                     |             |            |
#    *                     |             |            |
#    *                     |             |            |
#    *                    ____           |            |
#    *                   [    ]          |            |
#     -------------------[    ]----------|____________|
#                        [____]               TANK
#                         PUMP 
#
##########################################################

from math import cos, pi
import os
import watts
from astropy.units import Quantity


params = watts.Parameters()

# Channel params
params['sas_version'] = 5.5
params['tmax'] = 1000.0 # maximum problem time in s
params['flow_per_pin'] = 0.15 # kg/s
params['total_reactor_power'] = Quantity(20, "kW") # 200000.0 W
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
