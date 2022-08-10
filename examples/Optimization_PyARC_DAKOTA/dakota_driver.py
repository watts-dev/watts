#!/usr/bin/env python
import sys
from watts.plugin_dakota import run_dakota_driver

sys.path.insert(0, '{{ dakota_path }}')
run_dakota_driver(coupled_code_exec='{{  coupled_code_exec  }}')
