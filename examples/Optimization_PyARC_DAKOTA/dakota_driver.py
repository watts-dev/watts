#!/usr/bin/env python

# Dakota will execute this script as
#   generic_driver.py params.in results.out
# The command line arguments will be extracted by dakota.interfacing automatically.
# necessary python modules
import os
import sys
import json

sys.path.insert(0, "/home/nstauff/PROCEDURES/Workbench/dec2018/Linux/rte/../wasppy")
sys.path.insert(0, "/home/nstauff/PROCEDURES/dakota/bin/../share/dakota/Python/dakota/") # dakota_install/share/dakota/Python/dakota
import waspdrive # Workbench Analysis Sequence Processor driver module
from interfacing import interfacing as di # Dakota's interface module

# ----------------------------
# Parse Dakota parameters file
# ----------------------------

params, results = di.read_parameters_file()

#dump params to external params.json file for future use by the template engine
params_for_template_engine_file_path = "params.json"
with open(params_for_template_engine_file_path, 'w') as outfile:
    f=json.dump(params._variables,  outfile, default=lambda o: o.__dict__)
#note that in object params, _variables is an OrderedDict
#params.descriptors will output this ordered _variables
# -------------------------------
# Pre-processing
# Convert and send to application
# Or copy parameters into template to generate input file
# -------------------------------

# Set up the data structures
continuous_vars = [params[k] for k in params.descriptors]
#continuous_vars are defined in dakota .in file as cdv_descriptor

active_set_vector = 0

# Alternatively, the ASV can be accessed by index in
# function, gradient, hessian order
#for i, bit in enumerate(results["obj_fn"].asv):
#    if bit:
#        active_set_vector += 1 << i

# Obtain the drive module's input
# This file contains the application information and extraction logic
import glob
driver_inputs = glob.glob("*.drive")
if len(driver_inputs) == 0:
    raise ValueError("Unable to find drive file in "+os.getcwd()+"; did you forget to copy or link the file?")

driver_document = waspdrive.process_drive_input(driver_inputs[0])
rtncode=waspdrive.run_external_app(driver_document, params_for_template_engine_file_path)

#follow the logic in ddi file to extract required responses
res_output=waspdrive.extract_results(driver_document)

retval = dict([])
retval['fns']=res_output


# ----------------------------
# Return the results to Dakota
# ----------------------------

# Insert extracted values into results
# Results iterator provides an index, response name, and response
try:
  for i, n, r in results:
    if r.asv.function:
        try:
            r.function = retval['fns'][i]
        except:
            pass
# Catch Dakota 6.9 exception where results interface has changed
# ValueError: too many values to unpack            
except ValueError: 
  i = 0
  for n, r in results.items():
      r.function = retval['fns'][i]
      i+=1
results.write()

#dump to external results.json file
with open('results.json', 'w') as outfile:
    rst=json.dump(results,  outfile, default=lambda o: o.__dict__)

