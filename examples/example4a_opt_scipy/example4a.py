# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from scipy.optimize import minimize
from example4 import *

# initial X values
X = [0.9, 0.6]

def fitness_calc(X):
    """simple fitness function to get 1 "objective function" to scipy"""
    (keff, max_Tf, avg_Tf) = calc_workflow(X)
    fitness = abs(keff - 1) + (max_Tf/avg_Tf)
    return fitness

# optimization function - only 10 maximum iterations to make it run quick!
res = minimize(fitness_calc, X, method ='SLSQP', bounds=((0.5, 1.0), (0.5, 0.99)), options={'maxiter': 10, 'iprint': 1, 'disp': False, 'eps': 0.01})
params.show_summary(show_metadata=True, sort_by='time')


X = res.x
print("optimum X(FuelPin_rad, cool_hole_rad) = ", X)
