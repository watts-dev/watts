# SPDX-FileCopyrightText: 2022-2025 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to perform
ACCERT simulations. The ACCERT model quotes the overnight
capital cost and the cost of each account for a given set
of parameters. Results from ACCERT are extracted and stored
in params.
"""

import watts

# Set required parameters
params = watts.Parameters()
params['thermal_power'] = 3200
params['electric_power'] = 1300
params['cost_217'] = 29_000_000
input_name = "ACCERT_input.tmpl"


accert_plugin = watts.PluginACCERT(input_name)
accert_result = accert_plugin(params)

print(accert_result.inputs)
print(accert_result.outputs)
print("Reference model: ", accert_result.ref_model)
print("Total calculated direct cost [B$]: {:.2f}".format(
    accert_result.total_calculated_direct_cost / 1e9))
print("Total direct cost [B$]: {:.2f}".format(
    accert_result.total_direct_cost / 1e9))
print("Total indirect cost [B$]: {:.2f}".format(
    accert_result.total_indirect_costs / 1e9))
print("Total cost without owner [B$]: {:.2f}".format(
    accert_result.total_cost_without_owner / 1e9))
print("Total owner's cost [B$]: {:.2f}".format(
    accert_result.owner_cost / 1e9))
print("Total OCC [B$]: {:.2f}".format(accert_result.total_OCC / 1e9))

# ### The escalated results below require ACCERT 2.0 or later
print("Total OCC in {} dollars [B$]: {:.2f}".format(
    accert_result.escalated_dollar_year,
    accert_result.total_OCC_escalated / 1e9))
print("Total OCC in {} dollars [$/kW]: {:.2f}".format(
    accert_result.escalated_dollar_year, accert_result.total_OCC_per_kW))

# ### uncomment below to see the ACCERT account table in markdown format
# ### run `pip install -U pandas-profiling` to install pandas-profiling
# print(accert_result.account_table.to_markdown())

params.show_summary(show_metadata=True, sort_by='key')
