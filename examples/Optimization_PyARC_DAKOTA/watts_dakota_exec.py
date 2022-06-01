# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use DAKOTA to perform 
optimization of a WATTS workflow. 
"""

import watts
from astropy.units import Quantity

watts.Database.set_default_path('/home/zooi/watts-dakota-results')

params = watts.Parameters()

# Dakota parameters
params['real'] = 2

params.show_summary(show_metadata=False, sort_by='key')

# Dakota Workflow
dakota_plugin = watts.PluginDakota(
    template_file='dakota_watts_opt.in', show_stdout=True) # show all the output

dakota_result = dakota_plugin(params)

for key in dakota_result.output_data:
    print(key, dakota_result.output_data[key])