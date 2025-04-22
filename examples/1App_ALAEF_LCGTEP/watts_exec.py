# SPDX-FileCopyrightText: 2022-2025 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to run an A-LEAF calculation.
"""

import watts
from pathlib import Path
import numpy as np
import time

params = watts.Parameters()


reference_prices = {
    2022: 0.62, 2023: 0.62, 2024: 0.62, 2025: 0.62, 2026: 0.62, 2027: 0.62,
    2028: 0.63, 2029: 0.63, 2030: 0.63, 2031: 0.76, 2032: 0.76, 2033: 0.76,
    2034: 0.76, 2035: 0.76, 2036: 0.77, 2037: 0.77, 2038: 0.77, 2039: 0.77,
    2040: 0.77, 2041: 0.78, 2042: 0.78, 2043: 0.78, 2044: 0.78, 2045: 0.78,
    2046: 0.79, 2047: 0.79, 2048: 0.79, 2049: 0.79, 2050: 0.79, 2051: 0.80,
    2052: 0.80, 2053: 0.80, 2054: 0.80, 2055: 0.80, 2056: 0.81, 2057: 0.81,
    2058: 0.81, 2059: 0.81, 2060: 0.81
}


# Set nuclear prices from reference and calculated growth
starting_year = 2031
starting_price = 0.76
# Set nuclear prices from reference up to 2030
for year in range(2022, starting_year):
    params[f'fuel_{year}'] = reference_prices[year]

# Assign the starting price for 2031
params[f'fuel_{starting_year}'] = starting_price

# Compute prices from 2031 onwards using the growth rates
for year in range(starting_year + 1, 2061):
    prev_year_price = params[f'fuel_{year - 1}']
    growth_factor = 1.0028 if year <= 2050 else 1.057
    params[f'fuel_{year}'] = round(prev_year_price * growth_factor, 3)

params.show_summary(show_metadata=True, sort_by='key')

# Set default path for results
results_path = Path.cwd() / 'results'
results_path.mkdir(exist_ok=True, parents=True)
watts.Database.set_default_path(results_path)

# Create ALEAF plugin
# aleaf_plugin = watts.PluginALEAF('Fuel.txt', extra_templates={'Simulation Configuration': 'Simulation Configuration.txt'})
aleaf_plugin = watts.PluginALEAF('Fuel.txt')
# Run ALEAF
aleaf_result = aleaf_plugin(params)
print('ALEAF simulation completed.')

# Collect and display results
print(aleaf_result.csv_data)
