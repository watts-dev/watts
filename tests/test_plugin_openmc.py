# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import openmc
import watts


def build_openmc_model(params):
    model = openmc.model.Model()

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

    tally = openmc.Tally()
    tally.scores = ['nu-fission', 'fission', 'absorption']
    model.tallies.append(tally)

    model.export_to_xml()


def test_openmc_plugin():
    plugin = watts.PluginOpenMC(build_openmc_model)
    assert plugin.model_builder == build_openmc_model

    params = watts.Parameters(radius=6.38)
    result = plugin.workflow(params)

    # Sanity checks
    assert isinstance(result, watts.ResultsOpenMC)
    assert result.parameters['radius'] == 6.38
    assert len(result.statepoints) == 5
    input_names = {p.name for p in result.inputs}
    assert input_names == {'geometry.xml', 'materials.xml', 'settings.xml', 'tallies.xml'}
    output_names = {p.name for p in result.outputs}
    assert 'OpenMC_log.txt' in output_names
    assert len(result.tallies) == 1
    assert len(result.tallies[0].filters) == 0
    assert result.tallies[0].scores == ['nu-fission', 'fission', 'absorption']

    # k-eff should be "reasonable"
    assert 0.95 < result.keff.n < 1.05

    # value of nu should be greater than 3 for this problem
    nu_fission, fission, absorption = result.tallies[0].mean.ravel()
    assert nu_fission / fission > 3.0

    # nu-fission/absorption > keff since there's leakage
    assert nu_fission / absorption > result.keff.n

    # Make sure result was added to database and agrees
    db = watts.Database()
    last_result = db.results[-1]
    assert last_result.parameters['radius'] == result.parameters['radius']
    assert last_result.inputs == result.inputs
    assert last_result.outputs == result.outputs
    assert last_result.keff.n == result.keff.n
    assert last_result.keff.s == result.keff.s


def test_extra_inputs(run_in_tmpdir):
    # Create inputs manually -- 10 cm sphere of pure Pu239
    model = openmc.model.Model()
    mat = openmc.Material()
    mat.add_nuclide('Pu239', 1.0)
    mat.set_density('g/cm3', 10.0)
    sph = openmc.Sphere(r=10.0, boundary_type='vacuum')
    cell = openmc.Cell(fill=mat, region=-sph)
    model.geometry = openmc.Geometry([cell])
    model.settings.batches = 10
    model.settings.inactive = 0
    model.settings.particles = 1000
    model.export_to_xml()

    # Use OpenMC plugin with extra inputs
    plugin = watts.PluginOpenMC(extra_inputs=['geometry.xml', 'materials.xml', 'settings.xml'])
    params = watts.Parameters()
    result = plugin.workflow(params)

    input_names = {p.name for p in result.inputs}
    assert input_names == {'geometry.xml', 'materials.xml', 'settings.xml'}
