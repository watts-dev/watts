# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to run an
ABCE calculation. This example uses a coal-to-nuclear transition
scenario.
"""

import watts
import os
from pathlib import Path
import pandas as pd
import numpy as np


params = watts.Parameters()

n_steps = 2
results_path = Path.cwd() / 'results'
results_path.mkdir(exist_ok=True)
params['NFOM_VALUE'] = 'ATB'
params['N_STEPS'] = n_steps

watts.Database.set_default_path(results_path)



average_ngp = 5  # $/mmbtu
variance_ngp = 2
n_samples = 4

np.random.seed(12345)
# ngp_list = np.random.normal(loc=average_ngp, scale=variance_ngp, size=n_samples) # $/mmbtu
ngp_list = np.linspace(start = 0.5, stop=30, num=n_samples) # $/mmbtu
# nfom_list = np.linspace(start=40, stop=500, num=n_samples) # $/MWh
ptc_list = np.linspace(start=0, stop=60, num=n_samples) # $/MWh
results_dict = {}

for i,n in enumerate(ngp_list): # loop through all of the natural gas prices
    params['NATURAL_GAS_PRICE'] = n
    for j,p in enumerate(ptc_list):
        params['PTC_VALUE'] = p
        params['DATABASE_NAME'] = f'NG_PTC_run_1{i}{j}_pd{n_steps}.db'
        params.show_summary(show_metadata=True, sort_by='key')
        abce_plugin = watts.PluginABCE('abce_template.txt', show_stdout=True, show_stderr=True)
        abce_result = abce_plugin(params, extra_args=['-f'])
