# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from math import cos, pi
import os
import watts

params = watts.Parameters()

# Griffin
params['Griffin_Init_Fuel_Temperature'] = 800.0 # K

# Bison
params['BISON_Initial_Temperature'] = 800.0 # K.
params['BISON_Inifinit_Temperature'] = 800.0 # K.
params['BISON_Outside_HTC'] = 100.0

# Sockeye
params['Sockeye_Evap_Elem_Num'] =15
params['Sockeye_Adia_Elem_Num'] =5
params['Sockeye_Cond_Elem_Num'] =10

params.show_summary(show_metadata=False, sort_by='key')

# MOOSE Workflow
# set your SuperMoose directory as SUPER_MOOSE
# As Sockeye is run through dynamic linking
# set your Sockeye directory as SOCKEYE_DIR
if not os.getenv("SOCKEYE_DIR"):
    raise RuntimeError("SOCKEYE_DIR must be set to enable this example.")

moose_app_type = "super_moose"
app_dir = os.environ[moose_app_type.upper() + "_DIR"]
moose_plugin = watts.PluginMOOSE('MP_ss_griffin.tmpl', n_cpu=40, supp_inputs=['MP_ss_moose.i', 'MP_ss_sockeye.i', '3D_unit_cell_FY21_level-1_bison.e', '3D_unit_cell_FY21_supersimple.e', 'unitcell_nogap_hom_xml_G11_df_MP.xml'])
moose_plugin.moose_exec = app_dir + "/" + moose_app_type.lower() + "-opt"
moose_result = moose_plugin.workflow(params)
for key in moose_result.csv_data:
    print(key, moose_result.csv_data[key])
print(moose_result.inputs)
print(moose_result.outputs)
