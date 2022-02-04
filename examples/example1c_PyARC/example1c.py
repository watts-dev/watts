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
# TODO: set your PyARC directorate as PyARC_DIR

pyarc_plugin = watts.PluginPyARC('pyarc_template', show_stdout=True, supp_inputs = ['lumped_test5.son']) # show all the output
pyarc_plugin.pyarc_exec  = '/Users/nstauff/PyARC'
pyarc_result = pyarc_plugin.workflow(params)
for key in pyarc_result.results_data:
    print(key, pyarc_result.results_data[key])
print(pyarc_result.inputs)
print(pyarc_result.outputs)
