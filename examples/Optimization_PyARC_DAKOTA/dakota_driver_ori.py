#!/usr/bin/env python
import watts
import sys
sys.path.insert(0, '/software/Workbench/dakota/share/dakota/Python/dakota')
DakotaDriver = watts.PluginDakotaDriver(coupled_code_exec='watts_pyarc_exec.py')
