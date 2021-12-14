from datetime import datetime
from pathlib import Path

import watts
import numpy as np


def test_results_openmc(run_in_tmpdir):
    params = watts.Parameters(city='Chicago', population=2.7e6)
    now = datetime.now()

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


    results = watts.ResultsOpenMC(params, now, inputs, outputs)

    # Sanity checks
    assert results.plugin == 'OpenMC'
    assert results.parameters == params
    assert results.time == now
    assert results.inputs == inputs
    assert results.outputs == outputs
    assert results.stdout == "this is output\n"

    # Other attributes
    assert len(results.statepoints) == 1

    # Saving
    p = Path('myresults.h5')
    results.save(p)
    assert p.is_file()

    # Ensure results read from file match
    new_results = watts.Results.from_hdf5(p)
    assert isinstance(new_results, watts.ResultsOpenMC)
    assert new_results.parameters == results.parameters
    assert new_results.time == results.time
    assert new_results.inputs == results.inputs
    assert new_results.outputs == results.outputs
    assert new_results.stdout == results.stdout


def test_results_sam(run_in_tmpdir):
    params = watts.Parameters(city='Chicago', population=2.7e6)
    now = datetime.now()

    # Create some fake input files
    sam_inp = Path('SAM.i')
    sam_inp.touch()
    inputs = [sam_inp]

    # Create fake output files
    csv = Path('SAM_csv.csv')
    csv.write_text("""\
prop1,prop2
3.5,1
4.0,2
5.0,3
    """)
    stdout = Path('SAM_log.txt')
    stdout.write_text('SAM standard out\n')
    outputs = [csv, stdout]

    results = watts.ResultsSAM(params, now, inputs, outputs)

    # Sanity checks
    assert results.plugin == 'SAM'
    assert results.parameters == params
    assert results.time == now
    assert results.inputs == inputs
    assert results.outputs == outputs

    # Other attributes
    assert results.stdout == 'SAM standard out\n'
    np.testing.assert_equal(results.csv_data['prop1'], [3.5, 4.0, 5.0])
    np.testing.assert_equal(results.csv_data['prop2'], [1, 2, 3])

    # Saving
    p = Path('myresults.h5')
    results.save(p)
    assert p.is_file()

    # Ensure results read from file match
    new_results = watts.Results.from_hdf5(p)
    assert isinstance(new_results, watts.ResultsSAM)
    assert new_results.parameters == results.parameters
    assert new_results.time == results.time
    assert new_results.inputs == results.inputs
    assert new_results.outputs == results.outputs
    assert new_results.stdout == results.stdout
