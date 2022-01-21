from math import cos, pi
import watts

params = watts.Parameters()
# TH params

# reference
params['griffin_Tf'] = 300  # K
moose_ss_plugin = watts.PluginMOOSE('MP_griffin.tmpl') # we will need also to expend the moose/sockeye template files at the same time!
moose_ss_plugin.moose_exec = "/home/.../griffin-opt"
moose_ss_result = moose_ss_plugin.workflow(params)

# TODO: check on convergence

# null transient
params['griffin_Tf'] = 800  # K
moose_trN_plugin = watts.PluginMOOSE('MP_griffin.tmpl')
moose_trN_plugin.moose_exec = "/home/.../griffin-opt"
moose_trN_result = moose_trN_plugin.workflow(params)

# TODO: check on convergence

# transient
params['griffin_Tf'] = 800  # K
moose_tr_plugin = watts.PluginMOOSE('MP_griffin.tmpl')
moose_tr_plugin.moose_exec = "/home/.../griffin-opt"
moose_tr_result = moose_tr_plugin.workflow(params)
