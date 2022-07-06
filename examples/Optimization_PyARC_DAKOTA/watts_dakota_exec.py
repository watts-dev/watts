# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use DAKOTA to perform 
optimization with WATTS. This example uses PyArc as the
'input' code for Dakota. This Python script runs Dakota,
which in turn runs the Dakota driver that facilitates the
communication and data-transfer between Dakota and PyArc.
Note that a watts_exec.py script (in this case, watts_pyarc_exec.py)
is needed for PyArc. Parameters in the Dakota input file and
the watts_pyarc_exec.py script can be provided using WATTS'
'extra_template_inputs' option.
"""

import os
import sys
import watts
import time
from astropy.units import Quantity

watts.Database.set_default_path('/home/zooi/watts-dakota-results')
# watts.Database.set_default_path('/default/directory') # Set default save directory if necessary

params = watts.Parameters()

# Provide parameters to generate the dakota_driver.py file
params['dakota_path'] = '/software/Workbench/dakota/share/dakota/Python/dakota'
params['dakota_driver_name'] = 'dakota_driver.py' # Specify the file name of Dakota driver
params['coupled_code_exec'] = 'watts_pyarc_exec.py' # Specify the script of the coupled code

# Dakota parameters
params['real'] = 2
params['temp'] = 26.85

# Descriptors for Dakota
# Make sure the descriptors match those in the coupled code's WATTS script
params['dakota_descriptor_1'] = 'KO'
params['dakota_descriptor_2'] = 'CW'
params['dakota_descriptor_3'] = 'KC'

params.show_summary(show_metadata=False, sort_by='key')

# Dakota Workflow
# Use 'extra_template_inputs' to template optional extra files.
# USe 'extra_inputs' to copy files to the temporary directory for WATTS operation.
dakota_plugin = watts.PluginDakota(
    template_file='dakota_watts_opt.in',
    extra_template_inputs=['watts_pyarc_exec.py', 'dakota_driver.py'],
    extra_inputs=['pyarc_input.isotxs', 'pyarc_template', 'lumped.son', 'watts_dakota_exec.py'],
    show_stdout=True) # show all the output

dakota_result = dakota_plugin(params)

for key in dakota_result.output_data:
    print(key, dakota_result.output_data[key])