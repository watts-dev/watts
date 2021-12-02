from math import cos, pi
import ardent

from openmc_template import build_openmc_model


model = ardent.Model()

# TH params

model['He_inlet_temp'] = 600 + 273.15  # K
model['He_outlet_temp'] = 850 + 273.15 # K
model['He_cp'] = 5189.2 # J/kg-K
model['He_K'] =  0.32802   # W/m-K
model['He_density'] = 3.8815   # kg/m3
model['He_viscosity'] = 4.16e-5 # Pa.s
model['He_Pressure'] = 7e6    # Pa
model['Tot_assembly_power'] = 250000 # W
model['Init_P_1'] = 1 # Fraction
model['Init_P_2'] = 1 # Fraction
model['Init_P_3'] = 1 # Fraction
model['Init_P_4'] = 1 # Fraction
model['Init_P_5'] = 1 # Fraction

# Core design params
model['ax_ref'] = 20 # cm
model['num_cool_pins'] = 1*6+2*6+6*2/2
model['num_fuel_pins'] = 6+6+6+3*6+2*6/2+6/3
model['Height_FC'] = 2.0 # m
model['Lattice_pitch'] = 2.0
model['FuelPin_rad'] = 0.90 # cm
model['cool_hole_rad'] = 0.60 # cm
model['Coolant_channel_diam'] = (model['cool_hole_rad'] * 2)/100 # in m
model['Graphite_thickness'] = (model['Lattice_pitch'] - model['FuelPin_rad'] - model['cool_hole_rad']) # cm
model['Assembly_pitch'] = 7.5 * 2 * model['Lattice_pitch'] / (cos(pi/6) * 2)
model['lbp_rad'] = 0.25 # cm
model['mod_ext_rad'] = 0.90 # cm
model['shell_thick'] = 0.05   # FeCrAl
model['liner_thick'] = 0.007  # Cr
model['control_pin_rad'] = 0.99 # cm

# Control use of S(a,b) tables
model['use_sab'] = True
model['use_sab_BeO'] = True
model['use_sab_YH2'] = False

# OpenMC params
model['cl'] = model['Height_FC']*100 - 2 * model['ax_ref'] # cm
model['pf'] = 40 # percent

# SAM Workflow

sam_plugin = ardent.PluginSAM('sam_template')
sam_plugin.sam_tmp_folder = "tmp_SAM"
sam_exec = "../../sam-opt-mpi"  # Path to SAM executable
sam_option = sam_plugin.options(SAM_exec=sam_exec)
sam_plugin.workflow(model)#, sam_options)
model.show_summary()

# get temperature from SAM results
model['temp'] = model['avg_Tgraphite'][-1]
# Run OpenMC plugin
openmc_plugin = ardent.PluginOpenMC(build_openmc_model)
openmc_plugin.workflow(model)


# Save results
model.show_summary()
model.save('gcmr_with_openmc.h5')
