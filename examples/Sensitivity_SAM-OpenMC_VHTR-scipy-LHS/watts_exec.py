# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to perform
sensitivity study by running SAM followed by OpenMC workflow.
This example uses the same simple VHTR unit-cell as 1App examples
model with 1 coolant channel surrounded by graphite and fuel.
The SciPy library is used to drive the sensitivity with a
Latin Hypercube Sampling (LHS). The fuel pin and coolant radius
are being varied by the sensitivity analysis and resulting
keff, max and average fuel temperatures are being analyzed.
"""

from scipy.stats import qmc
from watts_main import *

sampler = qmc.LatinHypercube(d=2) # create a sampler for 2-dimension variable
sample = sampler.random(n=10) # create 10 randomely distributed samples
l_bounds = [0.5, 0.5]
u_bounds = [1.0, 1.0]
sample_scaled = qmc.scale(sample, l_bounds, u_bounds) # scale the samples within the bounds of the problem

print(sample_scaled)
results = {"keff": [], "max_Tf": [], "avg_Tf": []} # initialization of the results

for X in sample_scaled:
    keff, max_Tf, avg_Tf = calc_workflow(X) # simulations of the samples
    results["keff"].append(keff)
    results["max_Tf"].append(max_Tf)
    results["avg_Tf"].append(avg_Tf)

print(results)
print("keff: {} +/- {}".format(mean(results["keff"]), stdev(results["keff"])))
print("max_Tf: {} +/- {}".format(mean(results["max_Tf"]), stdev(results["max_Tf"])))
print("avg_Tf: {} +/- {}".format(mean(results["avg_Tf"]), stdev(results["avg_Tf"])))
