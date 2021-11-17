from pathlib import Path
from datetime import datetime

import ardent
import pytest
import numpy as np


def test_model_roundtrip(run_in_tmpdir):
    # Create a model with various datatypes
    model = ardent.Model()
    model['int_scalar'] = 7
    model['float_scalar'] = 6.022e23
    model['str_scalar'] = 'ARDENT is great'
    model['bool_scalar'] = True
    model['list_int'] = [0, 1, 2]
    model['list_float'] = [10.0, 20.0, 30.0]
    model['list_str'] = ['PWR', 'BWR', 'SFR', 'LMFR']
    model['tuple_int'] = (0, 1, 2)
    model['tuple_float'] = (10.0, 20.0, 30.0)
    model['tuple_str'] = ('HEU', 'LEU', 'HALEU')
    model['set_int'] = {5, 6, 3}
    model['set_float'] = {1.5, 2.5, 3.5}
    model['set_str'] = {'red', 'blue', 'green'}
    model['array_int'] = np.array([0, 1, 2])
    model['array_float'] = np.array([10., 20., 30.])
    model['array_bool'] = np.array([True, False, False, True])
    # Numpy array of strings doesn't work because internally numpy uses UTF-32,
    # which is not supported in h5py
    #model['array_str'] = np.array(['ANL', 'ORNL', 'LANL'])
    model['dict'] = {
        'int': 7,
        'float': 0.0253,
        'str': 'String inside dictionary'
    }

    # Add duplicate key
    with pytest.warns(UserWarning):
        model['int_scalar'] = 8

    # Save to HDF5
    model.save('model.h5')
    assert Path('model.h5').is_file()

    # Load model from HDF5
    new_model = ardent.Model()
    new_model.load('model.h5')

    # Make sure key/value pairs match original model
    for key, value in new_model.items():
        if isinstance(value, np.ndarray):
            np.testing.assert_equal(model[key], value)
        else:
            assert model[key] == value
            assert type(model[key]) == type(value)

        # Test metadata
        assert model.get_metadata(key) == new_model.get_metadata(key)


def test_model_set():
    user = 'test_user'
    time = datetime.now()
    model = ardent.Model()
    model.set('key', 7, user='test_user', time=time)

    assert model['key'] == 7
    assert model.get_metadata('key') == (user, time)
