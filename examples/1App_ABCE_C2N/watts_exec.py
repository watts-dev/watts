# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to run an
ABCE calculation. This example uses a coal-to-nuclear transition
scenario.
"""

import watts
from pathlib import Path
import numpy as np
import time


n_steps = 2

params = watts.Parameters()
params['NFOM_VALUE'] = "ATB"
params['N_STEPS'] = n_steps
params['run_ALEAF'] = "False"

template_name = "abce_template.txt"
results_path = Path.cwd() / 'results' / f"{n_steps}_periods_ALEAF_{params['run_ALEAF']}_99"
results_path.mkdir(exist_ok=True)

watts.Database.set_default_path(results_path)

average_ngp = 5  # $/mmbtu
variance_ngp = 2
n_samples = 12

start = time.perf_counter()

np.random.seed(12345)
ngp_list = np.array([2.0, 3.5, 5.5, 8.5]) # $/mmbtu
# nfom_list = np.linspace(start=40, stop=500, num=n_samples) # $/MWh
ptc_list = np.linspace(start=0, stop=30, num=n_samples) # $/MWh

for i, n in enumerate(ngp_list): # loop through all of the natural gas prices
    params['NATURAL_GAS_PRICE'] = n
    for j, p in enumerate(ptc_list):
        params['PTC_VALUE'] = p
        params['DATABASE_NAME'] = f'NG_PTC_run_4{i}{j}_pd{n_steps}.db'
        params.show_summary(show_metadata=True, sort_by='key')
        abce_plugin = watts.PluginABCE(f'{template_name}', show_stdout=True, show_stderr=True)
        abce_result = abce_plugin(params, extra_args=['-f'])

end = time.perf_counter()

print(f'TOTAL SIMULATION TIME: {np.round(end-start)/60} minutes')