# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to run an
ABCE calculation. This example uses a coal-to-nuclear transition
scenario.
"""

import watts
from pathlib import Path
import numpy as np
import time
import logging


# Initialize settings
template_name = "abce_template.txt"
results_path = Path.cwd() / "results" / "ABCE_C2N_example"
results_path.mkdir(exist_ok=True, parents=True)

watts.Database.set_default_path(results_path)

# Initialize parameterization
params = watts.Parameters()

# Set up parameter lists
PTC_qty_list = np.linspace(start=0, stop=30, num=2)  # $/MWh
peak_demand_list = np.linspace(start=76000, stop=80000, num=2)  # MWh


# Start the runs
start = time.perf_counter()

for PTC_qty in PTC_qty_list:
    params["PTC_qty"] = PTC_qty

    for peak_demand in peak_demand_list:
        params["peak_demand"] = peak_demand

        params.show_summary(show_metadata=True, sort_by="key")

        abce_plugin = watts.PluginABCE(
            template_name, show_stdout=True, show_stderr=True
        )

        abce_result = abce_plugin(params, extra_args=["-f"])

end = time.perf_counter()

logging.info(f"TOTAL SIMULATION TIME: {np.round(end-start)/60} minutes")
