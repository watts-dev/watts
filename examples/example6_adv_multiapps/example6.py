# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from math import cos, pi
import os
import watts

# A three-step three-level MultiApps system for a Microreactor Unit Cell is run here
# First step is steady state simulation
# Second step is a Null transient simulation to confirm the steady state obtained
# Third step is a real transient simulation induced by loss of cooling capacity

# set your SuperMoose directory as SUPER_MOOSE
# As Sockeye is run through dynamic linking
# set your Sockeye directory as SOCKEYE_DIR

if not os.getenv("SOCKEYE_DIR"):
    raise RuntimeError("SOCKEYE_DIR must be set to enable this example.")
# MOOSE app type to run
moose_app_type = "super_moose"
app_dir = os.environ[moose_app_type.upper() + "_DIR"]

# Steady State Parameters
params_ss = watts.Parameters()

# Griffin
params_ss['Griffin_Init_Fuel_Temperature'] = 800.0 # K

# Bison
params_ss['BISON_Initial_Temperature'] = 800.0 # K.
params_ss['BISON_Inifinit_Temperature'] = 800.0 # K.
params_ss['BISON_Outside_HTC'] = 100.0

# Sockeye
params_ss['Sockeye_Evap_Elem_Num'] =15
params_ss['Sockeye_Adia_Elem_Num'] =5
params_ss['Sockeye_Cond_Elem_Num'] =10

params_ss.show_summary(show_metadata=False, sort_by='key')

# MOOSE Workflow for steady state
moose_plugin_ss = watts.PluginMOOSE('MP_ss_griffin.tmpl', n_cpu=40, supp_inputs=['MP_ss_moose.i', 'MP_ss_sockeye.i', '3D_unit_cell_FY21_level-1_bison.e', '3D_unit_cell_FY21_supersimple.e', 'unitcell_nogap_hom_xml_G11_df_MP.xml'])
moose_plugin_ss.moose_exec = app_dir + "/" + moose_app_type.lower() + "-opt"
moose_result_ss = moose_plugin_ss.workflow(params_ss)
for key in moose_result_ss.csv_data:
    print(key, moose_result_ss.csv_data[key])
print(moose_result_ss.inputs)
print(moose_result_ss.outputs)

# set up an enviroment variable to pass SS output path to trN and tr workflow
os.environ["SS_PATH"] = str(moose_result_ss.base_path)

# Null Transient Parameters
params_trN = params_ss

# MOOSE Workflow for Null transient
moose_plugin_trN = watts.PluginMOOSE('MP_trN_griffin.tmpl', n_cpu=40, show_stdout=False, supp_inputs=['MP_trN_moose.i', 'MP_trN_sockeye.i', 'unitcell_nogap_hom_xml_G11_df_MP.xml'])
moose_plugin_trN.moose_exec = app_dir + "/" + moose_app_type.lower() + "-opt"
moose_result_trN = moose_plugin_trN.workflow(params_trN)
for key in moose_result_trN.csv_data:
    print(key, moose_result_trN.csv_data[key])
print(moose_result_trN.inputs)
print(moose_result_trN.outputs)

# tolerance for the Null Transient run to tell if the steady state obtained before is valid
rel_diff_tol = 1.0e-8

power_rel_diff = (moose_result_trN.csv_data['integrated_power'][0] - moose_result_trN.csv_data['integrated_power'][-1])/moose_result_trN.csv_data['integrated_power'][0]
if power_rel_diff > rel_diff_tol:
    raise RuntimeError("The Null Transient Run has a transient power; please check the steady state run.")

# Transient Parameters
params_tr = params_ss

# MOOSE Workflow for transient
moose_plugin_tr = watts.PluginMOOSE('MP_tr_griffin.tmpl', n_cpu=40, show_stdout=True, supp_inputs=['MP_tr_moose.i', 'MP_tr_sockeye.i', 'unitcell_nogap_hom_xml_G11_df_MP.xml'])
moose_plugin_tr.moose_exec = app_dir + "/" + moose_app_type.lower() + "-opt"
moose_result_tr = moose_plugin_tr.workflow(params_tr)
for key in moose_result_tr.csv_data:
    print(key, moose_result_tr.csv_data[key])
print(moose_result_tr.inputs)
print(moose_result_tr.outputs)
