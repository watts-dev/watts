# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
import os

import pytest
import openmc
import watts


@pytest.fixture(scope='module', autouse=True)
def data_library():
    """Create data library with only Am244"""
    lib = openmc.data.DataLibrary()
    lib.register_file(Path(__file__).with_name('Am244.h5'))
    lib.export_to_xml()

    # Temporarily set cross sections to the library just created
    os.environ['OPENMC_CROSS_SECTIONS'] = str(Path.cwd() / 'cross_sections.xml')


def build_openmc_model(params):
    model = openmc.model.Model()

    am244 = openmc.Material()
    am244.set_density('sum')
    am244.add_nuclide('Am244', 0.02)
    model.materials.append(am244)

    sph = openmc.Sphere(r=params['radius'], boundary_type='vacuum')
    cell = openmc.Cell(fill=am244, region=-sph)
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

    params = watts.Parameters(radius=11.45)
    result = plugin(params, name="OpenMC run")

    # Sanity checks
    assert isinstance(result, watts.ResultsOpenMC)
    assert result.parameters['radius'] == 11.45
    assert result.name == "OpenMC run"
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
    last_result = db[-1]
    assert last_result.parameters['radius'] == result.parameters['radius']
    assert last_result.name == result.name
    assert last_result.inputs == result.inputs
    assert last_result.outputs == result.outputs
    assert last_result.keff.n == result.keff.n
    assert last_result.keff.s == result.keff.s


@pytest.fixture
def am_model():
    """Model of a 10 cm sphere of Am244"""
    model = openmc.model.Model()
    mat = openmc.Material()
    mat.add_nuclide('Am244', 1.0)
    mat.set_density('g/cm3', 10.0)
    sph = openmc.Sphere(r=10.0, boundary_type='vacuum')
    cell = openmc.Cell(fill=mat, region=-sph)
    model.geometry = openmc.Geometry([cell])
    model.settings.batches = 10
    model.settings.inactive = 0
    model.settings.particles = 1000
    return model


def test_extra_inputs(run_in_tmpdir, am_model):
    am_model.export_to_xml()
    # Export model to XML

    # Use OpenMC plugin with extra inputs
    plugin = watts.PluginOpenMC(extra_inputs=['geometry.xml', 'materials.xml', 'settings.xml'])
    params = watts.Parameters()
    result = plugin(params)

    input_names = {p.name for p in result.inputs}
    assert input_names == {'geometry.xml', 'materials.xml', 'settings.xml'}


def test_arbitrary_function(run_in_tmpdir, am_model):
    # Add a plot to the model and export
    plot = openmc.Plot()
    plot.filename = 'watts_plot'
    plot.pixels = (100, 100)
    plot.width = (20.0, 20.0)
    am_model.plots.append(plot)
    am_model.export_to_xml()

    # Use OpenMC plugin to run a geometry plot
    plugin = watts.PluginOpenMC(extra_inputs=Path.cwd().glob('*.xml'))
    params = watts.Parameters()
    result = plugin(params, function=openmc.plot_geometry)

    # Generated plot should be in outputs
    output_names = {p.name for p in result.outputs}
    assert 'watts_plot.png' in output_names
