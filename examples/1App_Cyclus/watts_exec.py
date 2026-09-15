# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to perform a criticality search on an
MCNP model. This example is based on Jezebel, a critical sphere of plutonium
metal. In the MCNP input file, the radius is specified as a variable. To perform
the search on the critical radius, we use root-finding capabilites from SciPy.
"""

from multiprocessing import cpu_count
from scipy.optimize import root_scalar
import watts
import numpy as np

# Create paramaters object
params = watts.Parameters()


# Create MCNP plugin
cyclus_plugin = watts.PluginCyclus('cyclus_template.xml', show_stdout=True, show_stderr=True)


for cl in [24, 36, 100]:
    params['duration'] = cl
    result = cyclus_plugin(params, name='test.xml')
    print(result.commodities)
    print(result.mass_flow_dict)
    # check if it's working properly
    assert(result.commodities == ['enriched_u'])
    assert(len(result.mass_flow_dict['enriched_u']) == np.ceil(cl/12))