# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
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

# Create paramaters object
params = watts.Parameters()

# Create MCNP plugin
mcnp_plugin = watts.PluginMCNP('mcnp_template')

# The root-finding function from scipy.optimize needs to take as argument a
# function that you want to find the zero of. In this case, we want k - 1 to be
# zero, so we define a function that runs MCNP with the specified radius and
# then returns k - 1. As an added convenience, the function optionally takes a
# 'target' argument that could specify a different target k-effective value.
def f(radius, target=1.0):
    """Return difference between actual and target k-effective as a function of radius"""
    # Set radius in parameters
    params['radius'] = radius

    # Run MCNP in parallel
    threads = str(cpu_count())
    result = mcnp_plugin(params, name=f'r={radius}', extra_args=['TASKS', str(threads)])

    # Display the resulting k-effective value
    print(f'k={result.keff}')

    # Return the difference between the observed k-effective and the target
    return result.keff.n - target

# Run the root-finding algorithm using a bracketed search. It's assumed that the
# critical radius will lie between 1 and 20 cm
sol = root_scalar(f, bracket=[1.0, 20.0], rtol=1e-3)
print(f'After {sol.iterations} iterations, found critical radius = {sol.root} cm')
