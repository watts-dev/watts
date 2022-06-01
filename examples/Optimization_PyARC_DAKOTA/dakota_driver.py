#!/usr/bin/env python

# Dakota will execute this script as generic_driver.py params.in results.out
# The command line arguments will be extracted by dakota.interfacing automatically.

import watts
import sys

# Path to dakota.interfacing
sys.path.insert(0, "/software/Workbench/dakota/share/dakota/Python/dakota")

print("Running Dakota driver")

DakotaDriver = watts.PluginDakotaDriver(coupled_code_exec="watts_pyarc_exec.py")
