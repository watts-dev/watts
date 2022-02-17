# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from __future__ import annotations
import copy
from collections import namedtuple
from collections.abc import MutableMapping, Mapping, Iterable
from datetime import datetime
from getpass import getuser
import textwrap
from typing import Any, Union
from warnings import warn

from astropy import units as u
import h5py
from prettytable import PrettyTable


# Enable imperial units
u.imperial.enable()

_SAVE_FUNCS = {
    'set': list
}

_LOAD_FUNCS = {
    'tuple': tuple,
    'list': list,
    'set': set,
    'float': float,
    'int': int,
    'bool': bool
}

ParametersMetadata = namedtuple('ParametersMetadata', ['user', 'time'])

class Parameters(MutableMapping):
    """User parameters used to generate inputs that are created by plugins

    This class behaves like a normal Python dictionary except that it stores
    metadata on (key, value) pairs and provides the ability to save/load the
    data to an HDF5 file.

    Attributes
    ----------
    warn_duplicates : bool
        Whether to write a warning if a key is added and already exists

    """
    def __init__(self, *args, **kwargs):
        self._dict = {}
        self._metadata = {}
        self._warn_duplicates = False

        # Mimic the behavior of a normal dict object.
        if args:
            assert len(args) == 1
            args = args[0]
            if isinstance(args, Mapping):
                # dict(mapping)
                if hasattr(args, 'get_metadata'):
                    for key, value in args.items():
                        metadata = args.get_metadata(key)
                        self.set(key, value, **metadata._asdict())
                else:
                    for key, value in args.items():
                        self[key] = value
            elif isinstance(args, Iterable):
                # dict(iterable)
                for key, value in args:
                    self[key] = value
        elif kwargs:
            # dict(**kwargs)
            for key, value in kwargs.items():
                self[key] = value

    def __getitem__(self, key):
        return self._dict[key]

    def __setitem__(self, key, value):
        self.set(key, value)

    def __delitem__(self, key):
        del self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    @property
    def warn_duplicates(self) -> bool:
        return self._warn_duplicates

    @warn_duplicates.setter
    def warn_duplicates(self, value):
        if not isinstance(value, bool):
            raise ValueError("warn_duplicates attribute must be a boolean.")
        self._warn_duplicates = value

    def set(self, key: Any, value: Any, *, user: str = None, time: datetime = None):
        """Explicitly set a key/value pair with metadata

        Parameters
        ----------
        key
            Key used in dictionary
        value
            Corresponding value in dictionary
        user
            Username associated with key/value pair
        time
            Time associated with key/value pair
        """
        if user is None:
            user = getuser()
        if time is None:
            time = datetime.now()
        if self._warn_duplicates and key in self._dict:
            warn(f"Key {key} has already been added to parameters")
        self._dict[key] = value
        self._metadata[key] = ParametersMetadata(user, time)

    def get_metadata(self, key: Any) -> ParametersMetadata:
        """Get metadata associated with a key

        Parameters
        ----------
        key
            Key to find metadata for

        Returns
        -------
        Associated metadata

        """
        return self._metadata[key]

    def show_summary(self, show_metadata=True, sort_by='key', filter_by={}):
        """Display a summary of the parameters

        Parameters
        ----------
        show_metadata
            Whether to print user and timestamp associated with key/value pair
        sort_by
            Field to sort by ('key', 'value', 'user', 'time'; default is 'key')
        filter_by
            Dictionary defining filters to apply to fields. The dictionary keys
            describe the fields and must be one of 'key', 'value', 'user', or
            'time'. The dictionary values are functions that will be applied to
            values in that field. A row will be displayed in the summary only
            if all functions applied to the values in that row return true.

        Examples
        --------
        Print all the parameters sorted by timestamp:

        >>> params.show_summary(sort_by='time')

        Print only the parameters added by <username>:

        >>> params.show_summary(filter_by={'user': lambda x: x == 'username'})
        """
        field_to_name = {
            'key': 'PARAMETER',
            'value': 'VALUE',
            'user': 'ADDED BY',
            'time': 'TIMESTAMP'
        }

        # Create a nicely-formatted table to display parameters
        headers = list(field_to_name.values())
        table = PrettyTable(field_names=headers, align='l')

        # Add rows to the table
        for key, value in self.items():
            md = self._metadata[key]

            # Apply the filters
            field_to_value = {
                'key': key, 'value': value, 'user': md.user, 'time': md.time}
            for field, filt in filter_by.items():
                if not filt(field_to_value[field]):
                    break
            else:
                table.add_row(
                    [key, textwrap.fill(str(value), width=40), md.user, md.time])

        # Sort and print summary
        if not show_metadata:
            headers = headers[:2]
        print(table.get_string(fields=headers, sortby=field_to_name[sort_by]))

    def _save_mapping(self, mapping, h5_obj):
        # Helper function to add metadata
        def add_metadata(obj, metadata):
            obj.attrs['user'] = metadata.user
            obj.attrs['time'] = metadata.time.isoformat()

        for key, value in mapping.items():
            if isinstance(value, Mapping):
                # If this item is a dictionary, make recursive call
                group = h5_obj.create_group(key)
                if isinstance(mapping, type(self)):
                    add_metadata(group, self._metadata[key])
                self._save_mapping(value, group)
            else:
                # Convert type if necessary. If the type is not listed, return a
                # "null" function that just returns the original value
                func = _SAVE_FUNCS.get(type(value).__name__, lambda x: x)
                file_value = func(value)

                dset = h5_obj.create_dataset(key, data=file_value)
                dset.attrs['type'] = type(value).__name__
                if isinstance(mapping, type(self)):
                    add_metadata(dset, self._metadata[key])

    def save(self, filename_or_obj: Union[str, h5py.Group]):
        """Save parameters to an HDF5 file/group

        Parameters
        ----------
        filename_or_obj
            Path to HDF5 file or HDF5 group object to write to
        """
        if isinstance(filename_or_obj, str):
            with h5py.File(filename_or_obj, 'w') as h5file:
                self._save_mapping(self, h5file)
        else:
            # If HDF5 file/group was passed, use it directly
            self._save_mapping(self, filename_or_obj)

    def _load_mapping(self, mapping, h5_obj, root=True):
        # Helper function to get metadata
        def metadata_from_obj(obj):
            user = obj.attrs['user']
            time = datetime.fromisoformat(obj.attrs['time'])
            return ParametersMetadata(user, time)

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
                func = _LOAD_FUNCS.get(obj.attrs['type'], lambda x: x)
                mapping[key] = func(value)

                if root:
                    self._metadata[key] = metadata_from_obj(obj)

            elif isinstance(obj, h5py.Group):
                # For groups, load the mapping recursively
                mapping[key] = {}
                if root:
                    self._metadata[key] = metadata_from_obj(obj)

                self._load_mapping(mapping[key], obj, root=False)

    def load(self, filename_or_obj: Union[str, h5py.Group]):
        """Load parameters from an HDF5 file

        Parameters
        ----------
        filename_or_obj
            Path to HDF5 file or HDF5 group object to read from
        """
        if isinstance(filename_or_obj, str):
            with h5py.File(filename_or_obj, 'r') as fh:
                self._load_mapping(self, fh)
        else:
            # If HDF5 file/group was passed, use it directly
            self._load_mapping(self, filename_or_obj)

    @classmethod
    def from_hdf5(cls, filename_or_obj: Union[str, h5py.Group]) -> Parameters:
        """Return parameters from HDF5 file/group

        Parameters
        ----------
        filename_or_obj
            Path to HDF5 file or HDF5 group object to read from
        """
        params = cls()
        params.load(filename_or_obj)
        return params

    def convert_units(self, system: str = 'si', temperature: str = 'K',
                     inplace: bool = False) -> Parameters:
        """Perform unit conversion

        Parameters
        ----------
        system
            Desired unit system: 'si' or 'cgs'
        temperature
            Desired unit for temperature conversions
        inplace
            Whether to modify the parameters (True) or return a copy (False)

        Returns
        -------
        A :class:`Parameters` instance with converted units
        """
        params = self if inplace else copy.deepcopy(self)

        for key, value in params.items():
            if isinstance(value, u.Quantity):
                # Unit conversion for temperature needs to be done separately because
                # astropy uses a different method to convert temperature.
                if value.unit.physical_type == 'temperature':
                    params[key] = value.to(temperature, equivalencies=u.temperature()).value
                else:
                    params[key] = getattr(value, system).value

        return params
