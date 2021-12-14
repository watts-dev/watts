from pathlib import Path
from datetime import datetime

import ardent
import pytest
import numpy as np
import h5py

def _compare_params(params, other):
    # Make sure key/value pairs match original parameters
    for key, value in other.items():
        if isinstance(value, np.ndarray):
            np.testing.assert_equal(params[key], value)
        else:
            assert params[key] == value
            assert type(params[key]) == type(value)

        # Test metadata
        assert params.get_metadata(key) == other.get_metadata(key)


def test_parameters_roundtrip(run_in_tmpdir):
    # Create parameters with various datatypes
    params = ardent.Parameters()
    params['int_scalar'] = 7
    params['float_scalar'] = 6.022e23
    params['str_scalar'] = 'ARDENT is great'
    params['bool_scalar'] = True
    params['list_int'] = [0, 1, 2]
    params['list_float'] = [10.0, 20.0, 30.0]
    params['list_str'] = ['PWR', 'BWR', 'SFR', 'LMFR']
    params['tuple_int'] = (0, 1, 2)
    params['tuple_float'] = (10.0, 20.0, 30.0)
    params['tuple_str'] = ('HEU', 'LEU', 'HALEU')
    params['set_int'] = {5, 6, 3}
    params['set_float'] = {1.5, 2.5, 3.5}
    params['set_str'] = {'red', 'blue', 'green'}
    params['array_int'] = np.array([0, 1, 2])
    params['array_float'] = np.array([10., 20., 30.])
    params['array_bool'] = np.array([True, False, False, True])
    # Numpy array of strings doesn't work because internally numpy uses UTF-32,
    # which is not supported in h5py
    #params['array_str'] = np.array(['ANL', 'ORNL', 'LANL'])
    params['dict'] = {
        'int': 7,
        'float': 0.0253,
        'str': 'String inside dictionary'
    }

    # Add duplicate key
    with pytest.warns(UserWarning):
        params['int_scalar'] = 8

    # Save to HDF5
    params.save('params.h5')
    assert Path('params.h5').is_file()

    # Load parameters from HDF5
    new_params = ardent.Parameters.from_hdf5('params.h5')

    # Compare original parameters with one loaded from file
    _compare_params(params, new_params)


def test_parameters_set():
    user = 'test_user'
    time = datetime.now()
    params = ardent.Parameters()
    params.set('key', 7, user='test_user', time=time)

    assert params['key'] == 7
    assert params.get_metadata('key') == (user, time)


def test_parameters_not_toplevel(run_in_tmpdir):
    """Test saving/loading parameters when not at top-level of HDF5 file"""
    params = ardent.Parameters(var_one=1, var_two='two', var_three=3.0)

    # Write parameters to /mygroup within test.h5
    with h5py.File('test.h5', 'w') as fh:
        group = fh.create_group('mygroup')
        params.save(group)

    # Read parameters from /mygroup
    with h5py.File('test.h5', 'r') as fh:
        group = fh['mygroup']
        new_model = ardent.Parameters.from_hdf5(group)

    # Compare original parameters with one from group in file
    _compare_params(params, new_model)

def test_parameters_show_summary(capsys):
    params = ardent.Parameters()
    params['colors'] = ('teal', 'grey', 'blue')
    params['one'] = 1
    params['two'] = 2
    params['three'] = 3
    params['four'] = 4
    params['five'] = 5

    filters = {'time': lambda x: x > params.get_metadata('three').time}
    params.show_summary(show_metadata=False, sort_by='key', filter_by=filters)
    out, err = capsys.readouterr()

    expected_out = (
        "+-----------+-------+\n"
        "| PARAMETER | VALUE |\n"
        "+-----------+-------+\n"
        "| five      | 5     |\n"
        "| four      | 4     |\n"
        "+-----------+-------+\n"
    )
    assert out == expected_out
