# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from scipy.stats import qmc
from example4 import *

sampler = qmc.LatinHypercube(d=2)
sample = sampler.random(n=10)
l_bounds = [0.5, 0.5]
u_bounds = [1.0, 1.0]
sample_scaled = qmc.scale(sample, l_bounds, u_bounds)

print(sample_scaled)
results = {"keff": [], "max_Tf": [], "avg_Tf": []}

for X in sample_scaled:
    keff, max_Tf, avg_Tf = calc_workflow(X)
    results["keff"].append(keff)
    results["max_Tf"].append(max_Tf)
    results["avg_Tf"].append(avg_Tf)

print (results)
print ("keff: mean = %f , stdev = %f"%(mean(results["keff"]), stdev(results["keff"])))
print ("max_Tf: mean = %f , stdev = %f"%(mean(results["max_Tf"]), stdev(results["max_Tf"])))
print ("avg_Tf: mean = %f , stdev = %f"%(mean(results["avg_Tf"]), stdev(results["avg_Tf"])))
