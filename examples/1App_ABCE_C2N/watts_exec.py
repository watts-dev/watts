# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to run an
ABCE calculation. This example uses a coal-to-nuclear transition
scenario.
"""

import watts
import os
import pathlib
import pandas as pd
import numpy as np

params = watts.Parameters()

params['DATABASE_NAME'] = 'test.db'

params.show_summary(show_metadata=True, sort_by='key')


average_ngp = 5  # $/mmbtu
variance_ngp = 2
n_samples = 10

np.random.seed(12345)
ngp_list = np.random.normal(loc=average_ngp, scale=variance_ngp, size=n_samples) # $/mmbtu
ptc_list = np.linspace(start=0, stop=30, num=n_samples) # $/MWh

results_dict = {}

for i,n in enumerate(ngp_list): # loop through all of the natural gas prices
    params['NATURAL_GAS_PRICE'] = n
    for j,p in enumerate(ptc_list):
        params['PTC_VALUE'] = p

        params.show_summary(show_metadata=True, sort_by='key')

        abce_plugin = watts.PluginABCE('abce_template.txt')
        abce_result = abce_plugin(params)
