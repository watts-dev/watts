# SPDX-FileCopyrightText: 2022-2025 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to estimate the cost of a
large tokamak with ACCERT. On top of the capital cost, ACCERT computes
the levelized cost of electricity (LCOE) for its fusion reference
models, so the example also sweeps the discount rate to show how the
LCOE responds to the financing assumptions.
"""

import watts

params = watts.Parameters()
params['discount_rate'] = 0.0435
params['capacity_factor'] = 0.8
params['plant_life'] = 30
params['net_electric_power'] = 401
params['site_cost'] = 16

accert_plugin = watts.PluginACCERT("ACCERT_input.tmpl")
accert_result = accert_plugin(params)

print("Reference model: ", accert_result.ref_model)
print("Total direct cost [B$]: {:.2f}".format(
    accert_result.total_direct_cost / 1e9))
print("Total OCC [B$]: {:.2f}".format(accert_result.total_OCC / 1e9))
print("LCOE [$/MWh]: {:.2f}".format(accert_result.lcoe))

# Contribution of each component to the levelized cost of electricity
print(accert_result.lcoe_table.to_string())

# Sweep the discount rate to see how sensitive the LCOE is to financing
for discount_rate in (0.03, 0.05, 0.07, 0.09):
    params['discount_rate'] = discount_rate
    result = accert_plugin(params, name=f'discount_rate={discount_rate}')
    print("Discount rate {:.0%} -> LCOE {:.2f} $/MWh".format(
        discount_rate, result.lcoe))

params.show_summary(show_metadata=True, sort_by='key')
