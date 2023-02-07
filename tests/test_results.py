# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
import time

import watts
import numpy as np


def test_results_openmc(run_in_tmpdir):
    params = watts.Parameters(city='Chicago', population=2.7e6)
    plugin = 'OpenMC'
    name = "🎲"
    timestamp = time.time_ns()
    exec_info = watts.ExecInfo(123, plugin, name, timestamp)

    # Create some fake input files
    geom_xml = Path('geometry.xml')
    geom_xml.touch()
    mats_xml = Path('material.xml')
    mats_xml.touch()
    inputs = [geom_xml, mats_xml]

    # Create fake output files
    sp = Path('statepoint.50.h5')
    sp.touch()
    log_file = Path('OpenMC_log.txt')
    log_file.write_text("this is output\n")
    outputs = [sp, log_file]

    results = watts.ResultsOpenMC(params, exec_info, inputs, outputs)

    # Sanity checks
    assert results.plugin == 'OpenMC'
    assert results.parameters == params
    assert results.job_id == 123
    assert results.name == name
    assert results.exec_info.timestamp == timestamp
    assert results.inputs == inputs
    assert results.outputs == outputs
    assert results.stdout == "this is output\n"

    # Other attributes
    assert len(results.statepoints) == 1

    # Saving
    p = Path('myresults.pkl')
    results.save(p)
    assert p.is_file()

    # Ensure results read from file match
    new_results = watts.Results.from_pickle(p)
    assert isinstance(new_results, watts.ResultsOpenMC)
    assert new_results.parameters == results.parameters
    assert new_results.job_id == results.job_id
    assert new_results.plugin == results.plugin
    assert new_results.name == results.name
    assert new_results.time == results.time
    assert new_results.inputs == results.inputs
    assert new_results.outputs == results.outputs
    assert new_results.stdout == results.stdout


def test_results_moose(run_in_tmpdir):
    params = watts.Parameters(city='Chicago', population=2.7e6)
    name = 'Elk'
    timestamp = time.time_ns()
    exec_info = watts.ExecInfo(1984, 'MOOSE', name, timestamp)

    # Create some fake input files
    moose_inp = Path('MOOSE.i')
    moose_inp.touch()
    inputs = [moose_inp]

    # Create fake output files
    csv = Path('MOOSE_csv.csv')
    csv.write_text("""\
prop1,prop2
3.5,1
4.0,2
5.0,3
    """)
    stdout = Path('MOOSE_log.txt')
    stdout.write_text('MOOSE standard out\n')
    outputs = [csv, stdout]

    results = watts.ResultsMOOSE(params, exec_info, inputs, outputs)

    # Sanity checks
    assert results.plugin == 'MOOSE'
    assert results.parameters == params
    assert results.job_id == 1984
    assert results.name == name
    assert results.exec_info.timestamp == timestamp
    assert results.inputs == inputs
    assert results.outputs == outputs

    # Other attributes
    assert results.stdout == 'MOOSE standard out\n'
    np.testing.assert_equal(results.csv_data['prop1'], [3.5, 4.0, 5.0])
    np.testing.assert_equal(results.csv_data['prop2'], [1, 2, 3])

    # Saving
    p = Path('myresults.pkl')
    results.save(p)
    assert p.is_file()

    # Ensure results read from file match
    new_results = watts.Results.from_pickle(p)
    assert isinstance(new_results, watts.ResultsMOOSE)
    assert new_results.parameters == results.parameters
    assert new_results.job_id == results.job_id
    assert new_results.plugin == results.plugin
    assert new_results.name == results.name
    assert new_results.time == results.time
    assert new_results.inputs == results.inputs
    assert new_results.outputs == results.outputs
    assert new_results.stdout == results.stdout


def test_results_sas(run_in_tmpdir):
    params = watts.Parameters(city='Chicago', population=2.7e6)
    plugin = 'SAS'
    name = 'Sassy!'
    timestamp = time.time_ns()
    exec_info = watts.ExecInfo(57, plugin, name, timestamp)

    # Create some fake input files
    sas_inp = Path('sas.inp')
    sas_inp.touch()
    inputs = [sas_inp]

    # Create fake output files
    csv = Path('SAS_csv.csv')
    csv.write_text("""\
prop1,prop2
3.5,1
4.0,2
5.0,3
    """)
    stdout = Path('SAS_log.txt')
    stdout.write_text('SAS standard out\n')
    outputs = [csv, stdout]

    results = watts.ResultsSAS(params, exec_info, inputs, outputs)

    # Sanity checks
    assert results.plugin == 'SAS'
    assert results.parameters == params
    assert results.job_id == 57
    assert results.name == name
    assert results.exec_info.timestamp == timestamp
    assert results.inputs == inputs
    assert results.outputs == outputs

    # Other attributes
    assert results.stdout == 'SAS standard out\n'
    np.testing.assert_equal(results.csv_data['prop1'], [3.5, 4.0, 5.0])
    np.testing.assert_equal(results.csv_data['prop2'], [1, 2, 3])

    # Saving
    p = Path('myresults.pkl')
    results.save(p)
    assert p.is_file()

    # Ensure results read from file match
    new_results = watts.Results.from_pickle(p)
    assert isinstance(new_results, watts.ResultsSAS)
    assert new_results.parameters == results.parameters
    assert new_results.plugin == results.plugin
    assert new_results.job_id == results.job_id
    assert new_results.name == results.name
    assert new_results.time == results.time
    assert new_results.inputs == results.inputs
    assert new_results.outputs == results.outputs
    assert new_results.stdout == results.stdout


def test_results_relap5(run_in_tmpdir):
    params = watts.Parameters(city='Chicago', population=2.7e6)
    plugin = 'RELAP5'
    name = 'SinglePipe'
    timestamp = time.time_ns()
    exec_info = watts.ExecInfo(5, plugin, name, timestamp)

    # Create some fake input files
    relap5_inp = Path('relap5.i')
    relap5_inp.touch()
    inputs = [relap5_inp]

    # Create fake output files
    csv = Path('R5-out.csv')
    csv.write_text("""\
prop1,prop2
3.5,1
4.0,2
5.0,3
    """)
    stdout = Path('RELAP5_log.txt')
    stdout.write_text('RELAP5 standard out\n')
    outputs = [csv, stdout]

    results = watts.ResultsRELAP5(params, exec_info, inputs, outputs)

    # Sanity checks
    assert results.plugin == plugin
    assert results.parameters == params
    assert results.job_id == 5
    assert results.name == name
    assert results.exec_info.timestamp == timestamp
    assert results.inputs == inputs
    assert results.outputs == outputs

    # Other attributes
    assert results.stdout == 'RELAP5 standard out\n'
    np.testing.assert_equal(results.csv_data['prop1'], [3.5, 4.0, 5.0])
    np.testing.assert_equal(results.csv_data['prop2'], [1, 2, 3])

    # Saving
    p = Path('myresults.pkl')
    results.save(p)
    assert p.is_file()

    # Ensure results read from file match
    new_results = watts.Results.from_pickle(p)
    assert isinstance(new_results, watts.ResultsRELAP5)
    assert new_results.parameters == results.parameters
    assert new_results.plugin == results.plugin
    assert new_results.job_id == results.job_id
    assert new_results.name == results.name
    assert new_results.time == results.time
    assert new_results.inputs == results.inputs
    assert new_results.outputs == results.outputs
    assert new_results.stdout == results.stdout


def test_results_dakota(run_in_tmpdir):
    params = watts.Parameters(city='Chicago', population=2.7e6)
    plugin = 'Dakota'
    name = 'North_Dakota'
    timestamp = time.time_ns()
    exec_info = watts.ExecInfo(99, plugin, name, timestamp)

    # Create some fake input files
    dakota_inp = Path('dakota.inp')
    dakota_inp.touch()
    inputs = [dakota_inp]

    # Create fake output files
    csv = Path('dakota_opt.dat')
    csv.write_text("""\
prop1  prop2
3.5  1
4.0  2
5.0  3
    """)
    stdout = Path('Dakota_log.txt')
    stdout.write_text('DAKOTA standard out\n')
    outputs = [csv, stdout]

    results = watts.ResultsDakota(params, exec_info, inputs, outputs)

    # Sanity checks
    assert results.plugin == 'Dakota'
    assert results.parameters == params
    assert results.job_id == 99
    assert results.name == name
    assert results.exec_info.timestamp == timestamp
    assert results.inputs == inputs
    assert results.outputs == outputs

    # Other attributes
    assert results.stdout == 'DAKOTA standard out\n'
    np.testing.assert_equal(results.output_data['prop1'], [3.5, 4.0, 5.0])
    np.testing.assert_equal(results.output_data['prop2'], [1, 2, 3])

    # Saving
    p = Path('myresults.pkl')
    results.save(p)
    assert p.is_file()

    # Ensure results read from file match
    new_results = watts.Results.from_pickle(p)
    assert isinstance(new_results, watts.ResultsDakota)
    assert new_results.parameters == results.parameters
    assert new_results.plugin == results.plugin
    assert new_results.job_id == results.job_id
    assert new_results.name == results.name
    assert new_results.time == results.time
    assert new_results.inputs == results.inputs
    assert new_results.outputs == results.outputs
    assert new_results.stdout == results.stdout
