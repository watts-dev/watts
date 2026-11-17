# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to run a series of GCMAT calculations for a nuclear scenario. 

In this example, a set of GCMAT simulations are performed, each with a different `end_year` parameter. 
The `end_year` parameter specifies the final year of the simulation, allowing us to explore how 
extending the simulation period impacts the output. Additionally, we specify different `output_folder` 
names for each simulation to organize the results separately.

By running multiple simulations with varying `end_year` values, this example demonstrates the sensitivity 
of the GCMAT model to changes in the simulation period and the resulting effects on key output metrics.

Note that the `end_year` parameter's unit is in week, and starting from the year is 2010, so the end_year
2028 is equivalent to YEAR 2049, and 2080 is equivalent to YEAR 2050.
"""

import watts
from pathlib import Path
import numpy as np
import time

params = watts.Parameters()
template_name = 'gcmat_template.txt'

###############################################################################
# Example of Uranium demand from 2025 to 2035 the original values are from the GCMAT example
# The final demand is the sum of the demand from China, US, Europe, and the rest of the world
# unit in tonnes

final_demand_org = {'2025': 129942.80467537, '2026': 131242.232722123, '2027': 132554.655049345, '2028': 133880.201599838, '2029': 135219.003615836, '2030': 136571.193651995, '2031': 137936.905588515, '2032': 139316.2746444, '2033': 140709.437390844, '2034': 142116.531764752, '2035': 143537.6970824}
# Below are the shares of the demand from China, US, Europe, and the rest of the world
china_shares = {'2025': 0.1488, '2026': 0.1509, '2027': 0.153, '2028': 0.1551, '2029': 0.1572, '2030': 0.1593, '2031': 0.1614, '2032': 0.1635, '2033': 0.1656, '2034': 0.1677, '2035': 0.1698}
us_shares = {'2025': 0.167705168506287, '2026': 0.16583640931287, '2027': 0.164092357127913, '2028': 0.162454545105463, '2029': 0.160909323261296, '2030': 0.159448692009461, '2031': 0.158069206226392, '2032': 0.156774330726817, '2033': 0.155566621066295, '2034': 0.154449705570859, '2035': 0.153426207060785}
europe_shares = {'2025': 0.121418171095092, '2026': 0.119622503016436, '2027': 0.117931399291808, '2028': 0.116333503569193, '2029': 0.11482130552861, '2030': 0.113390051603732, '2031': 0.112036657179276, '2032': 0.110761596604602, '2033': 0.109563494760443, '2034': 0.108442445566371, '2035': 0.107398402556524}
row_shares = {'2025': 0.562076660398621, '2026': 0.563641087670695, '2027': 0.56497624358028, '2028': 0.566111951325344, '2029': 0.567069371210094, '2030': 0.567861256386808, '2031': 0.622751279451474, '2032': 0.625765072971703, '2033': 0.622194919609123, '2034': 0.622673325674434, '2035': 0.622981308570158}

###############################################################################
# Example of the new US Uranium demand from 2025 to 2035, these values can be calculated from DYMOND or other sources

us_new_demands = {'2025': 293500, '2026': 292100, '2027': 312300, '2028': 313400, '2029': 377000, '2030': 399100, '2031': 314900, '2032': 361100, '2033': 340200, '2034': 337200, '2035': 336800}

# As we are changing the US demand, we need to recalculate the shares for all the regions
for i in range(2025, 2036):
    china_demand = final_demand_org[str(i)] * china_shares[str(i)]
    europe_demand = final_demand_org[str(i)] * europe_shares[str(i)]
    row_demand = final_demand_org[str(i)] * row_shares[str(i)]
    # Original US demand, the demand is calculated based on the shares
    # Not used in the calculation, here for reference
    us_demand = final_demand_org[str(i)] * us_shares[str(i)]
    # New US demand
    us_new_demand = us_new_demands[str(i)]
    # New final demand
    new_final_demand = china_demand  + europe_demand + row_demand + us_new_demand
    params[f'final_demand_{i}'] = new_final_demand
    params[f'china_{i}'] = china_demand/new_final_demand
    params[f'us_{i}'] = us_new_demand/new_final_demand
    params[f'eu_{i}'] = europe_demand/new_final_demand
    params[f'row_{i}'] = row_demand/new_final_demand

# Create a directory for storing results
results_path = Path.cwd() / 'results' 
results_path.mkdir(exist_ok=True, parents=True)

# Set the default path for the database
watts.Database.set_default_path(results_path)
print('results_path',results_path)
# Define simulation parameters for multiple runs
# The parameter `end_year` is specified in weeks since the start of the simulation in 2010.
# For example:
# - 1040 weeks corresponds to the year 2030
# - 1274 weeks corresponds to the year 2040
# - 2080 weeks corresponds to the year 2050

output_years = [2030, 2040, 2050]  # Target years for the end of each simulation
# Convert each target year to the corresponding number of weeks since 2010
end_years = [int((year - 2010) * 52) for year in output_years]
# Generate output folder names based on target years
output_folders = [f"output_{year}" for year in output_years]

# Start timing the simulation for performance measurement
start = time.perf_counter()

# Loop through the defined variations in end_years and output_folders to run simulations
for output_year, end_year, output_folder in zip(output_years, end_years, output_folders):
    # Update parameters for the current simulation run
    params['end_year'] = end_year
    params['output_folder'] = output_folder
    params['DATABASE_NAME'] = f'GCMAT_{end_year}.db'
    
    # Display the current parameter settings for transparency and debugging
    params.show_summary(show_metadata=True, sort_by='key')
    
    # Create the GCMAT plugin instance with the specified template file
    gcmat_plugin = watts.PluginGCMAT('gcmat_template.txt', show_stdout=True, show_stderr=True)
    
    # Run the GCMAT simulation with the current set of parameters
    gcmat_result = gcmat_plugin(params, end_year=params['end_year'], output_folder=params['output_folder'])
    
    # Print the U buyer price in the US for the specified output year from the end of the simulation results
    print(f'Output year {output_year} price: {gcmat_result.csv_data["U buyer price US"].iloc[-1]}')

# End timing the simulation
end = time.perf_counter()

# Output the total simulation time for all runs
print(f'TOTAL SIMULATION TIME: {np.round((end - start) / 60, 2)} minutes')