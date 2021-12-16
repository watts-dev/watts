import openmc
import watts


def build_openmc_model(params):
    model = openmc.Model()

    pu_metal = openmc.Material()
    pu_metal.set_density('sum')
    pu_metal.add_nuclide('Pu239', 3.7047e-02)
    pu_metal.add_nuclide('Pu240', 1.7512e-03)
    pu_metal.add_nuclide('Pu241', 1.1674e-04)
    pu_metal.add_element('Ga', 1.3752e-03)
    model.materials.append(pu_metal)

    sph = openmc.Sphere(r=params['radius'], boundary_type='vacuum')
    cell = openmc.Cell(fill=pu_metal, region=-sph)
    model.geometry = openmc.Geometry([cell])

    model.settings.batches = 50
    model.settings.inactive = 10
    model.settings.particles = 1000
    model.settings.statepoint = {'batches': [10, 20, 30, 40, 50]}

    model.export_to_xml()


def test_openmc_plugin():
    plugin = watts.PluginOpenMC(build_openmc_model)
    assert plugin.model_builder == build_openmc_model

    params = watts.Parameters(radius=6.3)
    results = plugin.workflow(params)
    assert isinstance(results, watts.ResultsOpenMC)
    assert results.parameters['radius'] == 6.3
