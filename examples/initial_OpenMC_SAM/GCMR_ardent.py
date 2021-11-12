from math import cos, pi
import ardent

from GCMR_OpenMC import build_openmc_model


model = ardent.Model()

# Core design params
model['ax_ref'] = 20
model['num_cpu'] = 60
model['Lattice_pitch'] = 2.0
model['Assembly_pitch'] = 7.5 * 2 * model['Lattice_pitch'] / (cos(pi/6) * 2)
model['fuel_rad'] = 0.90
model['lbp_rad'] = 0.25
model['mod_ext_rad'] = 0.90
model['shell_thick'] = 0.05   # FeCrAl
model['liner_thick'] = 0.007  # Cr
model['cool_hole_rad'] = 0.60
model['control_pin_rad'] = 0.99

# Control use of S(a,b) tables
model['use_sab'] = True
model['use_sab_BeO'] = True
model['use_sab_YH2'] = False

# OpenMC params
model['temp'] = 300
model['cl'] = 160
model['pf'] = 40

# Run OpenMC plugin
openmc_plugin = ardent.OpenmcPlugin(build_openmc_model)
openmc_plugin.prerun(model)
openmc_plugin.run()
openmc_plugin.postrun(model)

# Save results
model.save('gcmr_with_openmc.h5')
