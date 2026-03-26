# SPDX-FileCopyrightText: 2024 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
Example WATTS workflow for DYMOND: a nuclear fuel cycle simulator.

This example models a simplified U.S. fuel cycle with:
- Legacy PWR and BWR fleets (once-through)
- Advanced LWR deployment
- Sodium-cooled fast reactor (SFR) deployment with fuel recycling
- Advanced SFR (ASFR) deployment with recycled fuel
- Reprocessing and hot-metal fabrication facilities

The template is parameterized so you can sweep over key variables
like simulation duration, reactor power, or deployment schedules.
"""

import watts

# ============================================================
# Parameters
# ============================================================
params = watts.Parameters()

# -- Simulation settings --
params['start_year'] = 1960
params['duration'] = 140
params['decay_calc'] = 'fast'

# -- Model settings --
params['depletion_path'] = {"ORIGEN-S": "C:/SCALE-6.3/bin/scalerte.exe"}

# -- Energy demand curve (MW, one value per year starting at start_year) --
params['energy_demand'] = [
    94500, 94320, 94140, 93960, 93780, 93600, 96120, 98640, 101160, 103680,
    106200, 109440, 112680, 115920, 119160, 122400, 127800, 133200, 138600, 144000,
    149400, 157680, 165960, 174240, 182520, 190800, 199620, 208440, 217260, 226080,
    234900, 235260, 235620, 235980, 236340, 236700, 239220, 241740, 244260, 246780,
    249300, 249660, 250020, 250380, 250740, 251100, 252000, 252900, 253800, 254700,
    255600, 259740, 263880, 268020, 272160, 276300, 279900, 283500, 287100, 290700,
    294300, 297720, 301140, 304560, 307980, 311400, 315000, 318600, 322200, 325800,
    329400, 333180, 336960, 340740, 344520, 348300, 351720, 355140, 358560, 361980,
    365400,
]

# -- Reactor types --
params['reactors'] = [
    {
        "name": "PWR",
        "power": 1010.52,
        "efficiency": 0.32547,
        "lifetime": 80,
        "capacity_factor": 0.9,
        "continuous_operation": True,
        "cycle_length": 1.5,
        "refuel_mass": 33591.2,
        "core_size": 82218,
        "fuel_fab": "recipe",
        "fuel": {"haleu": 0.246626, "depu": 0.753374},
        "first_core": [
            {"haleu": 0.131902, "depu": 0.868098},
            {"haleu": 0.196319, "depu": 0.803681},
            {"haleu": 0.260736, "depu": 0.739264},
        ],
        "depletion": {"recipe": "lwr_recipe.json"},
        "waste": "LWR",
        "cooling_time": 5,
    },
    {
        "name": "ALWR",
        "power": 1117,
        "efficiency": 0.3285,
        "lifetime": 80,
        "capacity_factor": 0.93,
        "continuous_operation": True,
        "cycle_length": 1.5,
        "refuel_mass": 32900,
        "core_size": 84778,
        "fuel_fab": "recipe",
        "fuel": {"haleu": 0.282209, "depu": 0.717791},
        "first_core": [
            {"haleu": 0.131902, "depu": 0.868098},
            {"haleu": 0.196319, "depu": 0.803681},
            {"haleu": 0.260736, "depu": 0.739264},
        ],
        "depletion": {"recipe": "lwr_recipe.json"},
        "waste": "LWR",
        "cooling_time": 5,
    },
    {
        "name": "BWR",
        "power": 1060.29,
        "efficiency": 0.3171,
        "lifetime": 80,
        "capacity_factor": 0.9,
        "continuous_operation": True,
        "cycle_length": 2.0,
        "refuel_mass": 46961.2,
        "core_size": 129880,
        "fuel_fab": "recipe",
        "fuel": {"haleu": 0.238037, "depu": 0.761963},
        "first_core": [
            {"haleu": 0.1292, "depu": 0.8707},
            {"haleu": 0.1938, "depu": 0.8062},
            {"haleu": 0.2584, "depu": 0.7415},
        ],
        "depletion": {"recipe": "lwr_recipe.json"},
        "waste": "LWR",
        "cooling_time": 5,
    },
    {
        "name": "SFR",
        "power": 345,
        "efficiency": 0.4,
        "lifetime": 80,
        "capacity_factor": 0.85,
        "continuous_operation": True,
        "cycle_length": 1.5,
        "refuel_mass": 2761.29,
        "core_size": 19329,
        "fuel_fab": "recipe",
        "fuel": {"haleu": 1.0},
        "first_core": [{"haleu": 0.730061, "depu": 0.269939}] * 7,
        "depletion": {"recipe": "sfr_recipe.json"},
        "waste": "SFR_UNF",
        "cooling_time": 5,
    },
    {
        "name": "ASFR",
        "power": 400,
        "efficiency": 0.4,
        "lifetime": 80,
        "capacity_factor": 0.9,
        "continuous_operation": True,
        "cycle_length": 1.5,
        "refuel_mass": 6344.27,
        "core_size": 31721.37,
        "fuel_fab": "crit-search",
        "fuel_lead_time": 1.0,
        "source": {
            "drivers": ["primary_ASFR", "primary_SFR", "haleu"],
            "makeups": ["repu_ASFR", "repu_SFR", "depu"],
        },
        "first_core": [{"u235": 0.11318, "u238": 0.88682}],
        "depletion": {"ORIGEN-S": "ASFR.f33"},
        "waste": "ASFR_UNF",
        "cooling_time": 2,
    },
]

# -- Fabrication --
params['fabrications'] = [
    {
        "name": "hot_metal_fab",
        "capacity": 1e9,
        "process_time": 1.0,
    }
]

# -- Reprocessing --
params['reprocessing_plants'] = [
    {
        "name": "reprocess_ASFR",
        "capacity": 70000,
        "deployment_lead_time": 5,
        "process_time": 1.0,
        "feed": ["ASFR_UNF"],
        "products": {
            "repu_ASFR": {"u": 1.0},
            "primary_ASFR": {"np": 1.0, "pu": 1.0, "am": 1.0, "cm": 1.0},
        },
        "balance_product": "ASFR_HLW",
    },
    {
        "name": "reprocess_SFR",
        "capacity": 70000,
        "deployment_lead_time": 5,
        "process_time": 1.0,
        "feed": ["SFR_UNF"],
        "products": {
            "repu_SFR": {"u": 1.0},
            "primary_SFR": {"np": 1.0, "pu": 1.0, "am": 1.0, "cm": 1.0},
        },
        "balance_product": "SFR_HLW",
    },
]

# -- Storage --
params['storages'] = [
    {"name": "drivers", "materials": ["haleu", "primary_ASFR", "primary_SFR"]},
    {"name": "makeup", "materials": ["depu", "repu_ASFR", "repu_SFR"]},
    {"name": "waste", "materials": ["LWR", "SFR_HLW", "ASFR_HLW"]},
]

# -- Deployments --
params['deployments'] = {
    "legacy_pwrs": {
        "type_name": "PWR",
        "deployment_dates": [
            1970, 1971, 1972, 1973, 1974, 1975, 1976, 1977, 1978, 1980,
            1981, 1982, 1983, 1984, 1985, 1986, 1987, 1988, 1989, 1990,
            1993, 1996, 2016,
        ],
        "deployment_quantity": [
            1.186264937, 0.736493752, 2.309383068, 3.141652593, 3.131135455,
            2.703476098, 1.904115923, 2.879078758, 3.103198793, 1.816408054,
            4.347126562, 1.126658662, 0.987577353, 3.21856294, 5.840439136,
            6.008432952, 4.311693759, 5.066118324, 2.543904788, 2.517295826,
            1.139855938, 1.055743578, 0.968445289,
        ],
        "deployment_method": "condensed",
        "input_connections": ["drivers", "makeup"],
        "output_connections": ["waste"],
    },
    "legacy_bwrs": {
        "type_name": "BWR",
        "deployment_dates": [
            1969, 1970, 1971, 1973, 1974, 1975, 1977, 1979, 1983, 1984,
            1985, 1986, 1987, 1988, 1990,
        ],
        "deployment_quantity": [
            0.603584868, 0.881430762, 1.498782828, 1.789429202, 4.456815274,
            3.676470588, 2.021962545, 0.853610805, 1.198961814, 3.339317021,
            2.151646667, 3.100210529, 2.199922243, 2.233814963, 1.116990006,
        ],
        "deployment_method": "condensed",
        "input_connections": ["drivers", "makeup"],
        "output_connections": ["waste"],
    },
    "vogtle": {
        "type_name": "ALWR",
        "deployment_dates": [2023, 2024],
        "deployment_quantity": [1, 1],
        "deployment_method": "step-wise",
        "input_connections": ["drivers", "makeup"],
        "output_connections": ["waste"],
    },
    "sfr_fleet": {
        "type_name": "SFR",
        "deployment_dates": list(range(2030, 2054)),
        "deployment_quantity": [
            6, 11, 16, 22, 27, 33, 27, 19, 18, 18, 19, 28, 28, 29, 28,
            28, 30, 30, 30, 30, 32, 8, 9, 8,
        ],
        "input_connections": ["drivers", "makeup"],
        "output_connections": ["reprocess_SFR"],
    },
    "asfr_fleet": {
        "type_name": "ASFR",
        "deployment_dates": list(range(2054, 2101)),
        "deployment_quantity": [
            14, 20, 24, 12, 19, 15, 10, 5, 12, 4, 7, 18, 20, 23, 19, 22,
            9, 20, 12, 11, 15, 11, 10, 13, 10, 10, 10, 9, 10, 9, 10, 9,
            10, 10, 10, 10, 10, 11, 10, 11, 10, 11, 9, 12, 10, 9, 10,
        ],
        "input_connections": ["hot_metal_fab"],
        "output_connections": ["reprocess_ASFR"],
    },
    "fab_asfr_fleet": {
        "type_name": "hot_metal_fab",
        "deployment_dates": [2050],
        "deployment_quantity": [1],
        "input_connections": ["drivers", "makeup"],
        "output_connections": ["ASFR"],
    },
    "reprocess_SFR_fleet": {
        "type_name": "reprocess_SFR",
        "deployment_dates": [2051, 2052, 2053, 2054, 2055, 2056, 2057],
        "deployment_quantity": [1, 2, 2, 2, 2, 2, 1],
        "input_connections": ["SFR"],
        "output_connections": ["drivers", "makeup", "waste"],
    },
    "reprocess_ASFR_fleet": {
        "type_name": "reprocess_ASFR",
        "deployment_dates": list(range(2061, 2101)),
        "deployment_quantity": [
            1, 1, 1, 1, 2, 2, 2, 2, 2, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 1,
            1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,
        ],
        "input_connections": ["ASFR"],
        "output_connections": ["drivers", "makeup", "waste"],
    },
    "driver_storages": {
        "type_name": "drivers",
        "deployment_dates": [1960],
        "deployment_quantity": [1],
    },
    "makeup_storages": {
        "type_name": "makeup",
        "deployment_dates": [1960],
        "deployment_quantity": [1],
    },
    "waste_storages": {
        "type_name": "waste",
        "deployment_dates": [2020],
        "deployment_quantity": [1],
    },
}

# -- Events (initial material inventories) --
params['events'] = [
    {
        "type": "timed",
        "time": [0.0],
        "target": "driver_storages",
        "action": "add material",
        "parameters": {"haleu": {"u235": 165e6, "u238": 835e6}},
    },
    {
        "type": "timed",
        "time": [0.0],
        "target": "makeup_storages",
        "action": "add material",
        "parameters": {"depu": {"u235": 2.5e6, "u238": 997.5e6}},
    },
]

# -- Output configuration --
params['output_json_files'] = True

params['output_stocks'] = [
    {
        "name": "storage",
        "storage": {
            "types": ["drivers", "makeup", "waste"],
            "categories": ["facility"],
            "totals": True,
        },
    },
    {
        "name": "unf_storage",
        "reactor": {
            "types": [],
            "categories": ["storage"],
            "totals": True,
        },
    },
]

params['output_flows'] = [
    {
        "name": "reactor",
        "reactor": {
            "types": ["PWR", "BWR", "ALWR", "SFR", "ASFR"],
            "categories": ["facility", "process"],
            "totals": True,
        },
    },
    {
        "name": "reprocessing",
        "reprocessing": {
            "types": ["reprocess_SFR", "reprocess_ASFR"],
            "categories": ["process"],
            "totals": True,
        },
    },
]

params['output_operations'] = {
    "reactor": {"types": [], "states": [], "totals": True},
}

# ============================================================
# Run DYMOND
# ============================================================
dymond_plugin = watts.PluginDYMOND(
    'dymond_template.json',
    show_stdout=True,
    show_stderr=True,
    # extra_inputs=['lwr_recipe.json', 'sfr_recipe.json', 'ASFR.f33'],
)

results = dymond_plugin(params, name='recycle_scenario')

# ============================================================
# Inspect results
# ============================================================
dymond = results.obj

# Time information
print("Times:", dymond.get_times())

# Power generation
power = dymond.get_generated_power()
print("Total power (GW):", power)

# Fuel demand per reactor type
fuel = dymond.stock_fuel_demand(return_sum=False)
for name, arr in fuel.items():
    print(f"  {name} fuel demand: {arr.sum():.1f} kg total")
