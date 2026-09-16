# SPDX-FileCopyrightText: 2022-2025 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to estimate the capital
cost of an AP1000 two-unit plant with ACCERT. The overnight capital
cost is escalated to a target dollar year and reported per unit of
electric capacity, which is the form used to compare designs.
"""

import watts

# Set required parameters
params = watts.Parameters()
params['thermal_power'] = 6800
params['electric_power'] = 2234
params['piping_mass'] = 77001
params['dollar_year'] = 2025

accert_plugin = watts.PluginACCERT("ACCERT_input.tmpl")
accert_result = accert_plugin(params)

print("Reference model: ", accert_result.ref_model)
print("Total direct cost [B$]: {:.2f}".format(
    accert_result.total_direct_cost / 1e9))
print("Total indirect cost [B$]: {:.2f}".format(
    accert_result.total_indirect_costs / 1e9))
print("Total owner's cost [B$]: {:.2f}".format(accert_result.owner_cost / 1e9))
print("Total OCC [B$]: {:.2f}".format(accert_result.total_OCC / 1e9))
print("Total OCC in {} dollars [B$]: {:.2f}".format(
    accert_result.escalated_dollar_year,
    accert_result.total_OCC_escalated / 1e9))
print("Total OCC in {} dollars [$/kW]: {:.0f}".format(
    accert_result.escalated_dollar_year, accert_result.total_OCC_per_kW))

# The accounts that ACCERT recalculated because of the input above
accounts = accert_result.account_table
print(accounts[accounts['review_status'] != 'Unchanged'].to_string(index=False))

params.show_summary(show_metadata=True, sort_by='key')
