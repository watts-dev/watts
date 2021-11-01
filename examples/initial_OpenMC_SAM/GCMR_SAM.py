import ardent
import math
model = ardent.Model()
model['He_inlet_temp'] = 600 + 273.15  # K
model['He_outlet_temp'] = 850 + 273.15 # K
model['He_cp'] = 5189.2 # J/kg-K
model['He_K'] =  0.32802   # W/m-K
model['He_density'] = 3.8815   # kg/m3
model['He_viscosity'] = 4.16e-5 # Pa.s
model['He_Pressure'] = 7e6    # Pa
model['Tot_assembly_power'] = 250000 # W
model['num_cool_pins'] = 1*6+2*6+6*2/2
model['num_fuel_pins'] = 6+6+6+3*6+2*6/2+6/3
model['Height_FC'] = 2.0 # m
cool_hole_rad = 0.60 # cm
Lattice_pitch = 2.0 # cm
fuel_rad = 0.90 # cm
model['FuelPin_rad'] = fuel_rad # cm
model['Coolant_channel_diam'] = (cool_hole_rad * 2)/100 # in m
model['Graphite_thickness'] = (Lattice_pitch - fuel_rad - cool_hole_rad) # cm
model.save('model.h5')
model.show_summary()
print()

model_builder = ardent.TemplateModelBuilder('sam_template')

plugin = ardent.PluginSAM(model_builder)
plugin.workflow(model)

model.show_summary()