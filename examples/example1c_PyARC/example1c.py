# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import os
import watts

params = watts.Parameters()

# TH params

params['assembly_pitch'] = 20e-2  # m
params['assembly_length'] = 0.13   # m

params.show_summary(show_metadata=False, sort_by='key')

# PyARC Workflow

pyarc_plugin = watts.PluginPyARC('pyarc_template', show_stdout=True, supp_inputs=['lumped_test5.son']) # show all the output
#pyarc_plugin.pyarc_exec  = os.environ["PyARC_DIR"] # requires to have export PyARC_DIR='/path-to-/PyARC'
pyarc_result = pyarc_plugin.workflow(params)
for key in pyarc_result.results_data:
    print(key, pyarc_result.results_data[key])
print(pyarc_result.inputs)
print(pyarc_result.outputs)
params['keff-dif3d'] = pyarc_result.results_data["dif3d"][0.0]
params['keff-mcc3'] = pyarc_result.results_data["mcc3"][('R', 0, 1, 'A', 1)]

params.show_summary(show_metadata=True, sort_by='key')
