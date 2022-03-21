# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to perform 
multi-criteria optimization study by running SAM followed by 
OpenMC workflow. This example uses the same simple VHTR unit-cell 
as 1App examples model with 1 coolant channel surrounded by graphite 
and fuel. The pymoo library is used to drive the optimization using
a Genetic Algorithm, which goal is to minimize both excess reactivity 
and peak fuel temperature. The fuel pin and coolant radius are being 
varied by the optimization algorithm. The best solutions are being 
returned.
"""

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize
from pymoo.core.problem import ElementwiseProblem

# Problem definition
class fitness_calc(ElementwiseProblem):
    """simple definition of the optimization problem with initialization and evaluation methods"""
    def __init__(self):
        super().__init__(n_var=2, n_obj=2, xl=np.array([0.5, 0.5]), xu=np.array([1.0, 1.0])) # initialization of the problem

    def _evaluate(self, x, out, *args, **kwargs):
        print(x) # this is the matrix of the size of the population
        (keff, max_Tf, avg_Tf) = calc_workflow(x) # the workflow is called here and we are saving the results in out['F']
        print(keff, max_Tf, avg_Tf) 
        out["F"] = [keff, max_Tf]

algorithm = NSGA2(pop_size=5) # multicriteria algorithm applied

res = minimize(fitness_calc(),
               algorithm,
               ('n_gen', 4),
               seed=1,
               verbose=False) # this runs the optimization algorithm

print("all variables", res.X)
print("all results", res.F)
