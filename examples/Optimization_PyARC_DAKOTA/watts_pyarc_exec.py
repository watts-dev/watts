# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use DAKOTA to perform
optimization of a WATTS workflow.
"""
import shutil
import watts
import json
from astropy.units import Quantity

# TH params
params = watts.Parameters()

# Load Dakota's output and read Dakota's output from 'params.json' and directly
# input them to WATTS' params()
f = open("params.json")
dakota_output = json.load(f)

# Set PyARC variables ('assembly_pitch' and 'assembly_length') to the
# values generated by Dakota. Make sure that keys ('AP' and 'AL' in this example) match the
# variable descriptors in the Dakota input file.
params['assembly_pitch'] = Quantity(dakota_output['AP'], "cm")
params['assembly_length'] = Quantity(dakota_output['AL'], "cm")
params['temp'] = Quantity({{ temp }}, "Celsius")  # 300 K

# Store the Dakota response descriptors as dictionary.
# Make sure that the ORDER of the descriptors matches the order in the Dakota input file
# because WATTS uses the order to identify the descriptors.
# MUST use the 'dakota_descriptors' key word here.
params['dakota_descriptors'] = {
    '{{ dakota_descriptor_1 }}': 'keff-dif3d',
    '{{ dakota_descriptor_2 }}': 'core_weight',
    '{{ dakota_descriptor_3 }}': 'keff-dif3d'
}

# PyARC Workflow
pyarc_plugin = watts.PluginPyARC(
    template_file='pyarc_template', show_stdout=True,
    extra_inputs=['lumped.son', 'pyarc_input.isotxs']) # show all the output
pyarc_result = pyarc_plugin(params)

# Store results to params.
# Make sure the keys for params match the keys for 'dakota_descriptors' above.
params['keff-dif3d'] = pyarc_result.results_data["keff_dif3d"][0.0]
params['core_weight'] = pyarc_result.results_data["rebus_inventory"][0][('CORE', 'TOTAL')]

# Generate output file for the next iteration.
for p in pyarc_result.inputs:
    if "pyarc_input.son" in str(p):
        shutil.copyfile(str(p), "pyarc_input.son")
for p in pyarc_result.outputs:
    if "pyarc_input.summary" in str(p):
        shutil.copyfile(str(p), "pyarc_input.summary")
    if "pyarc_input.out" in str(p):
        shutil.copyfile(str(p), "pyarc_input.out")

# Save params() as a pickle file for data transfer between WATTS and Dakota.
# The file MUST be named as 'opt_res.out'.
# If this file is missing, an error will be generated.
params.save("opt_res.out")

print(f"results: KeffOpt = {params['keff-dif3d']} - HNinventory = {params['core_weight']} ")
