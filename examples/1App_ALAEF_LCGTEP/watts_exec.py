# SPDX-FileCopyrightText: 2022-2025 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to run an A-LEAF calculation.
"""

import watts
from pathlib import Path
import pandas as pd

params = watts.Parameters()


fuel_price = {
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

# Compute prices dynamically for years after the starting year
growth_rates = {year: 1.0028 if year <= 2050 else 1.057 for year in range(starting_year + 1, 2061)}
computed_prices = {starting_year: starting_price}
for year in range(starting_year + 1, 2061):
    prev_price = computed_prices[year - 1]
    computed_prices[year] = round(prev_price * growth_rates[year], 3)

fuel_price.update(computed_prices)

# Initialize parameters and pass the fuel price dictionary
params = watts.Parameters()
params['fuel_price'] = fuel_price
# Display parameter summary
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

# Get the technology summary
techsummary = aleaf_result.csv_data
# keep only the capacity columns 
techsummary = techsummary[['Year', 'UnitGroup', 'Unit_Type', 'Fuel', 'ICAP', 'ICap_New', 'ICap_Ret']]

# group the technology summary by year and fuel
grouped_df = techsummary.groupby(['Year','Fuel']).sum()
# print out the grouped dataframe
print(grouped_df)


