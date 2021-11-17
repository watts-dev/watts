import ardent

model = ardent.Model()
model['Velocity_multiplication_factor'] = 1.0
model['He_inlet_temp'] = 590 + 273.15
model['He_outlet_temp'] = 850 + 273.15
model['He_cp'] = 5189.2
model['He_density'] = 3.8815
model['He_Pressure'] = 7e6
model['Tot_reactor_power'] = 1000.0
model['num_cool_pins'] = 10
model['Coolant_channel_XS'] = 25.6
model.save('model.h5')
model.show_summary()
print()

plugin = ardent.PluginSAM('sam_template')
plugin.prerun(model)

# Show rendered template
with open('sam_template.rendered', 'r') as f:
    print(f.read())
