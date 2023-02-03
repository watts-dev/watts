# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to perform
optimization study by running SAM followed by OpenMC workflow.
This example uses the same simple VHTR unit-cell as 1App examples
model with 1 coolant channel surrounded by graphite and fuel.
The SciPy library is used to drive the optimization. A single
criteria (fitness function) for this optimization study
to minimize both excess reactivity and peak fuel temperature.
The fuel pin and coolant radius are being varied by the optimization
algorithm. The best solution is being returned.
"""

from scipy.optimize import minimize
from watts_main import *

# initial X values required for scipy optimization
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
