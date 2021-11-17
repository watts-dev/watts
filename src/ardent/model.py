from collections import namedtuple
from collections.abc import MutableMapping, Mapping, Iterable
from datetime import datetime
from getpass import getuser
from typing import Any
from warnings import warn

import h5py


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

ModelMetadata = namedtuple('ModelMetadata', ['user', 'time'])


class Model(MutableMapping):
    """Model storing information that is read/written by plugins

    The model class behaves like a normal Python dictionary except that it
    stores metadata on (key, value) pairs and provides the ability to save/load
    the data to an HDF5 file.

    """
    def __init__(self, *args, **kwargs):
        self._dict = {}
        self._metadata = {}

        # Mimic the behavior of a normal dict object.
        if args:
            if isinstance(args, Mapping):
                # dict(mapping)
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
        if key in self._dict:
            warn(f"Key {key} has already been added to model")
        self._dict[key] = value
        self._metadata[key] = ModelMetadata(user, time)

    def get_metadata(self, key: Any) -> ModelMetadata:
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

    def show_summary(self):
        """Display a summary of key/value pairs"""
        for key, value in self.items():
            metadata = self._metadata[key]
            print(f'{key}: {value} (added by {metadata.user} at {metadata.time})')

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

    def save(self, filename: str):
        """Save model parameters to an HDF5 file

        Parameters
        ----------
        filename
            Path to HDF5 file to write
        """
        with h5py.File(filename, 'w') as h5file:
            self._save_mapping(self, h5file)

    def _load_mapping(self, mapping, h5_obj, root=True):
        # Helper function to get metadata
        def metadata_from_obj(obj):
            user = obj.attrs['user']
            time = datetime.fromisoformat(obj.attrs['time'])
            return ModelMetadata(user, time)

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

    def load(self, filename: str):
        """Load model parameters from an HDF5 file

        Parameters
        ----------
        filename
            HDF5 file to load model from
        """
        with h5py.File(filename, 'r') as h5file:
            self._load_mapping(self, h5file)
