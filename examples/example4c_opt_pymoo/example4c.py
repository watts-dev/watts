# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from example4 import *
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize

# initial X values
X = [0.9, 0.6]

def fitness_calc(X): # simple fitness function to get 1 "objective function" to scipy
    (keff, max_Tf, avg_Tf) = calc_workflow(X)
    fitness = (abs(keff - 1), (max_Tf/avg_Tf))
    return fitness

algorithm = NSGA2(pop_size=5)

res = minimize(fitness_calc,
               algorithm,
               ('n_gen', 3),
               seed=1,
               verbose=False)
