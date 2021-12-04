from math import cos, pi
import ardent

from openmc_template import build_openmc_model


params = ardent.Parameters()

# TH params

params['He_inlet_temp'] = 600 + 273.15  # K
params['He_outlet_temp'] = 850 + 273.15 # K
params['He_cp'] = 5189.2 # J/kg-K
params['He_K'] =  0.32802   # W/m-K
params['He_density'] = 3.8815   # kg/m3
params['He_viscosity'] = 4.16e-5 # Pa.s
params['He_Pressure'] = 7e6    # Pa
params['Tot_assembly_power'] = 250000 # W

params['Init_P_1'] = 1 # Fraction
params['Init_P_2'] = 1 # Fraction
params['Init_P_3'] = 1 # Fraction
params['Init_P_4'] = 1 # Fraction
params['Init_P_5'] = 1 # Fraction

# Core design params
params['ax_ref'] = 20 # cm
params['num_cool_pins'] = 1*6+2*6+6*2/2
params['num_fuel_pins'] = 6+6+6+3*6+2*6/2+6/3
params['Height_FC'] = 2.0 # m
params['Lattice_pitch'] = 2.0
params['FuelPin_rad'] = 0.90 # cm
params['cool_hole_rad'] = 0.60 # cm
params['Coolant_channel_diam'] = (params['cool_hole_rad'] * 2)/100 # in m
params['Graphite_thickness'] = (params['Lattice_pitch'] - params['FuelPin_rad'] - params['cool_hole_rad']) # cm
params['Assembly_pitch'] = 7.5 * 2 * params['Lattice_pitch'] / (cos(pi/6) * 2)
params['lbp_rad'] = 0.25 # cm
params['mod_ext_rad'] = 0.90 # cm
params['shell_thick'] = 0.05   # FeCrAl
params['liner_thick'] = 0.007  # Cr
params['control_pin_rad'] = 0.99 # cm

# Control use of S(a,b) tables
params['use_sab'] = True
params['use_sab_BeO'] = True
params['use_sab_YH2'] = False

# OpenMC params
params['cl'] = params['Height_FC']*100 - 2 * params['ax_ref'] # cm
params['pf'] = 40 # percent

# printout params
params.show_summary()

# SAM Workflow

sam_plugin = ardent.PluginSAM('sam_template')
sam_plugin._sam_exec = "/home/rhu/projects/SAM/sam-opt"
sam_result = sam_plugin.workflow(params)#, sam_options)
for key in sam_result.csv_data:
    print (key, sam_result.csv_data[key])
print (sam_result.inputs)
print (sam_result.outputs)

# get temperature from SAM results
params['temp'] = sam_result.csv_data['avg_Tgraphite'][-1]
# Run OpenMC plugin
openmc_plugin = ardent.PluginOpenMC(build_openmc_model)
openmc_result = openmc_plugin.workflow(params)
print ("KEFF = ", openmc_result.keff)
print (openmc_result.inputs)
print (openmc_result.outputs)



