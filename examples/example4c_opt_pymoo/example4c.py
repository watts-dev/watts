# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from example4 import *
import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize
from pymoo.core.problem import Problem

# initial X values

# Problem definition
class fitness_calc(Problem):
    def __init__(self):
        super().__init__(n_var=2, n_obj=2, xl=np.array([0.5, 0.5]), xu=np.array([1.0, 1.0]))

    def _evaluate(self, x, out, *args, **kwargs):
        print(x)
        out["F"] = [] 
        for X in x:
            (keff, max_Tf, avg_Tf) = calc_workflow(X)
            print(keff, max_Tf, avg_Tf) 
            out["F"].append([keff, max_Tf/avg_Tf])

algorithm = NSGA2(pop_size=5)

res = minimize(fitness_calc(),
               algorithm,
               ('n_gen', 3),
               seed=1,
               verbose=False)
