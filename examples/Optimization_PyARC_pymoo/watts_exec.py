# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use XXX to perform 
optimization of a WATTS workflow. 
"""

import watts
db = watts.Database()
import numpy as np
from astropy.units import Quantity
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize
from pymoo.core.problem import ElementwiseProblem

X = (20, 20, 2e-2)

def calc_workflow(X):
    params = watts.Parameters()

    params['assembly_pitch'] = Quantity(X[0], "cm")  
    params['assembly_length'] = Quantity(X[1], "cm")
    params['enrich'] = X[2]

    params['temp'] = Quantity(26.85, "Celsius")  # 300 K

    # PyARC Workflow
    pyarc_plugin = watts.PluginPyARC('pyarc_template', show_stdout=True, extra_inputs=['lumped.son', 'pyarc_input.isotxs']) # show all the output
    pyarc_result = pyarc_plugin(params)
    params['keff-dif3d'] = pyarc_result.results_data["keff_dif3d"][0.0]
    params['core_weight'] = pyarc_result.results_data["rebus_inventory"][0][('CORE', 'TOTAL')]
#    print(pyarc_result.outputs)
    return (params['keff-dif3d'], params['core_weight'])

# Problem definition
class fitness_calc(ElementwiseProblem):
    """simple definition of the optimization problem with initialization and evaluation methods"""
    def __init__(self):
        super().__init__(n_var=3, n_obj=2, xl=np.array([10, 10, 1e-3]), xu=np.array([25, 50, 2e-2])) # initialization of the problem

    def _evaluate(self, x, out, *args, **kwargs):
        (keff, core_weight) = calc_workflow(x) # the workflow is called here and we are saving the results in out['F']
        print(x) # this is the matrix of the size of the population
        print(keff, core_weight) 
        out["F"] = [abs(1-1/keff), core_weight]

algorithm = NSGA2(pop_size=5) # multicriteria algorithm applied

res = minimize(fitness_calc(),
               algorithm,
               ('n_gen', 4),
               seed=1,
               verbose=False) # this runs the optimization algorithm

print("all variables", res.X)
print("all results", res.F)
db.clear()