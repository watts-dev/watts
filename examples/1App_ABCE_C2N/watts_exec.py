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

results_path = Path.cwd() / 'results'
results_path.mkdir(exist_ok=True)
params['PTC_VALUE'] = 25.0

watts.Database.set_default_path(results_path)



average_ngp = 5  # $/mmbtu
variance_ngp = 2
n_samples = 2

np.random.seed(12345)
# ngp_list = np.random.normal(loc=average_ngp, scale=variance_ngp, size=n_samples) # $/mmbtu
ngp_list = np.linspace(start = 2.0, stop=30, num=n_samples) # $/mmbtu
nfom_list = np.linspace(start=40, stop=500, num=n_samples) # $/MWh

results_dict = {}

for i,n in enumerate(ngp_list): # loop through all of the natural gas prices
    params['NATURAL_GAS_PRICE'] = n
    for j,p in enumerate(nfom_list):
        params['NFOM_VALUE'] = p
        params['DATABASE_NAME'] = f'NG_NFOM_run_0{i}{j}.db'
        params.show_summary(show_metadata=True, sort_by='key')
        # breakpoint()
        abce_plugin = watts.PluginABCE('abce_template.txt', show_stdout=True, show_stderr=True)
        abce_result = abce_plugin(params, extra_args=['-f'])
