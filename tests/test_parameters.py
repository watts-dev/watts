# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
from datetime import datetime
import warnings

from astropy.units import Quantity, kilometer
import watts
import pytest
import numpy as np


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
    params = watts.Parameters()
    params['int_scalar'] = 7
    params['float_scalar'] = 6.022e23
    params['str_scalar'] = 'WATTS is great'
    params['bool_scalar'] = True
    params['quantity_scalar'] = Quantity(3.0, 'J/kg')
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
    params['array_quantity'] = np.array([1.0, 2.0, 5.0]) * kilometer
    params['array_str'] = np.array(['ANL', 'ORNL', 'LANL'])
    params['dict'] = {
        'int': 7,
        'float': 0.0253,
        'str': 'String inside dictionary'
    }

    # Save to pickle file
    params.save('params.pkl')
    assert Path('params.pkl').is_file()

    # Load parameters from pickle file
    new_params = watts.Parameters.from_pickle('params.pkl')

    # Compare original parameters with one loaded from file
    _compare_params(params, new_params)


def test_parameters_set():
    user = 'test_user'
    time = datetime.now()
    params = watts.Parameters()
    params.set('key', 7, user='test_user', time=time)

    assert params['key'] == 7
    assert params.get_metadata('key') == (user, time)


def test_parameters_show_summary(capsys):
    params = watts.Parameters()
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


def test_parameters_duplicates():
    params = watts.Parameters(a=3)

    # By default, overwriting a parameter shouldn't produce a warning. If a
    # warning is given, the filter below will result in a test failure
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        params['a'] = 8

    # In this case, we expect a warning to be produced
    params.warn_duplicates = True
    with pytest.warns(UserWarning):
        params['a'] = 8


def test_unit_conversion(run_in_tmpdir):
    params = watts.Parameters()

    # Test with various unit conversion formats
    params['He_inlet_temp'] = Quantity(600, "Celsius")  # 873.15 K
    params['He_cp'] = Quantity(4.9184126, "BTU/(kg*K)") # 5189.2 J/kg-K
    params['He_Pressure'] = Quantity(7.0, "MPa") # 7e6 Pa
    params['Height_FC'] = Quantity(2000, "mm") # 2 m

    # Check that unit conversion in the MOOSE plugin is correct
    params_si = params.convert_units(system='si')

    assert params_si["He_inlet_temp"] == 873.15    # K
    assert round(params_si["He_cp"], 1) == 5189.2  # J/kg-K
    assert params_si["He_Pressure"] == 7_000_000.0 # Pa
    assert params_si["Height_FC"] == 2.0           # m

    # Check that unit conversion in the openmc plugin is correct
    params_cgs = params.convert_units(system='cgs')

    assert params_cgs["He_inlet_temp"] == 873.15         # K
    assert round(params_cgs["He_cp"], -3) == 51892000.0  # J/g-K
    assert params_cgs["He_Pressure"] == 70_000_000.0     # P/s
    assert params_cgs["Height_FC"] == 200.0              # cm
