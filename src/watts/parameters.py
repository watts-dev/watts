# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from __future__ import annotations
import copy
from collections import namedtuple
from collections.abc import MutableMapping, Mapping, Iterable
from datetime import datetime
from getpass import getuser
import textwrap
from typing import Any, Union, BinaryIO
from warnings import warn

import astropy.units as u
import dill
from prettytable import PrettyTable

# Enable imperial units
u.imperial.enable()

ParametersMetadata = namedtuple('ParametersMetadata', ['user', 'time'])

class Parameters(MutableMapping):
    """User parameters used to generate inputs that are created by plugins

    This class behaves like a normal Python dictionary except that it stores
    metadata on (key, value) pairs and provides the ability to save/load the
    data to a pickle file.

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

    def _save_mapping(self, file_obj: BinaryIO):
        file_obj.write(dill.dumps(self))

    def save(self, filename_or_obj: Union[str, BinaryIO]):
        """Save parameters to a pickle file

        Parameters
        ----------
        filename_or_obj
            Path to open file or file object write to
        """
        if isinstance(filename_or_obj, str):
            with open(filename_or_obj, 'wb') as file_obj:
                self._save_mapping(file_obj)
        else:
            # If file object was passed, use it directly
            self._save_mapping(filename_or_obj)

    def _load_mapping(self, file_obj: BinaryIO):
        # Load parameters from pickle
        data = dill.loads(file_obj.read())

        # Update current instance
        self.update(data)
        self._metadata.update(data._metadata)

    def load(self, filename_or_obj: Union[str, BinaryIO]):
        """Load parameters from a pickle file

        Parameters
        ----------
        filename_or_obj
            Path to pickle file or file object to read from
        """
        if isinstance(filename_or_obj, str):
            with open(filename_or_obj, 'rb') as fh:
                self._load_mapping(fh)
        else:
            # If file object was passed, use it directly
            self._load_mapping(filename_or_obj)

    @classmethod
    def from_pickle(cls, filename_or_obj: Union[str, BinaryIO]) -> Parameters:
        """Return parameters from a pickle file

        Parameters
        ----------
        filename_or_obj
            Path to pickle file or file object to read from
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
