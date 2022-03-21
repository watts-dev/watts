# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import watts
from astropy.units import Quantity

# TH params
params = watts.Parameters()
params['assembly_pitch'] = Quantity(20, "cm")  # 20e-2  m
params['assembly_length'] = Quantity(13, "cm")  # 0.13 m
params['temp'] = Quantity(26.85, "Celsius")  # 300 K

params.show_summary(show_metadata=False, sort_by='key')

# PyARC Workflow

pyarc_plugin = watts.PluginPyARC('pyarc_template', show_stdout=True, extra_inputs=['lumped_test5.son']) # show all the output
pyarc_result = pyarc_plugin(params)
for key in pyarc_result.results_data:
    print(key, pyarc_result.results_data[key])
print(pyarc_result.inputs)
print(pyarc_result.outputs)
params['keff-dif3d'] = pyarc_result.results_data["keff_dif3d"][0.0]
params['keff-mcc3'] = pyarc_result.results_data["keff_mcc3"][('R', 0, 1, 'A', 1)]

params.show_summary(show_metadata=True, sort_by='key')
