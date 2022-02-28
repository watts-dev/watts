# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from collections.abc import Mapping

import astropy.units as u
import h5py

# Normally saving parameters to HDF5 is as simple as calling:
#
#   obj.create_dataset(key, data=value)
#
# However, in some cases we need to transform the value before writing or add
# extra metadata in the dataset. To do this, we setup a mapping of Python types
# to functions that create a dataset.

def _generate_save_func(dtype):
    def make_dataset(obj, key, value):
        dataset = obj.create_dataset(key, data=dtype(value))
        return dataset
    return make_dataset

_default_save_func = _generate_save_func(lambda x: x)

def _quantity_save_func(obj, key, value):
    dataset = _default_save_func(obj, key, value)
    dataset.attrs['unit'] = str(value.unit)
    return dataset

_SAVE_FUNCS = {
    'set': _generate_save_func(list),
    'Quantity': _quantity_save_func
}

# In an HDF5 file, all iterable objects just appear as plain arrays (represented
# by h5py as numpy arrays). To "round trip" data correctly, we again setup a
# mapping of Python types to functions that load data out of a datset and
# perform any transformation needed.

def _generate_load_func(dtype):
    return lambda obj, value: dtype(value)

def _quantity_load_func(obj, value):
    return u.Quantity(value, obj.attrs['unit'])

_LOAD_FUNCS = {
    'tuple': _generate_load_func(tuple),
    'list': _generate_load_func(list),
    'set': _generate_load_func(set),
    'float': _generate_load_func(float),
    'int': _generate_load_func(int),
    'bool': _generate_load_func(bool),
    'Quantity': _quantity_load_func
}


def save_mapping(mapping, h5_obj):
    for key, value in mapping.items():
        if isinstance(value, Mapping):
            # If this item is a dictionary, make recursive call
            group = h5_obj.create_group(key)
            save_mapping(value, group)
        else:
            # Convert type if necessary. If the type is not listed, return a
            # "null" function that just returns the original value
            func = _SAVE_FUNCS.get(type(value).__name__, _default_save_func)
            dset = func(h5_obj, key, value)
            dset.attrs['type'] = type(value).__name__


def load_mapping(mapping, h5_obj):
    for key, obj in h5_obj.items():
        if isinstance(obj, h5py.Dataset):
            # If dataset stores a string type, it needs to be decoded so
            # that it doesn't return a bytes object
            if h5py.check_string_dtype(obj.dtype) is not None:
                if obj.shape == ():
                    value = obj[()].decode()
                else:
                    value = obj[()].astype('str')
            else:
                value = obj[()]

            # Convert type if indicated. If the type is not listed, return a
            # "null" function that just returns the original value
            func = _LOAD_FUNCS.get(obj.attrs['type'], lambda obj, x: x)
            mapping[key] = func(obj, value)

        elif isinstance(obj, h5py.Group):
            # For groups, load the mapping recursively
            mapping[key] = {}
            load_mapping(mapping[key], obj)


