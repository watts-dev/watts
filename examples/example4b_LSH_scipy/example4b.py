# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from scipy.stats import qmc
from example4 import *

sampler = qmc.LatinHypercube(d=2)
sample = sampler.random(n=10)
l_bounds = [0.5, 0.5]
u_bounds = [1.0, 1.0]
qmc.scale(sample, l_bounds, u_bounds)

print (sample)
results = {}
results["keff"] = []
results["max_Tf"] = []
results["avg_Tf"] = []

for X in sample:
    res = append(calc_workflow(X))
    results["keff"].append(res[0])
    results["max_Tf"].append(res[1])
    results["avg_Tf"].append(res[2])

print (results, mean(results["keff"]), mean(results["max_Tf"]), mean(results["avg_Tf"]))
