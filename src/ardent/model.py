from collections.abc import MutableMapping, Mapping

import h5py


class Model(MutableMapping):
    def __init__(self):
        self._dict = {}

    def __getitem__(self, key):
        return self._dict[key]

    def __setitem__(self, key, value):
        self._dict[key] = value

    def __delitem__(self, key):
        del self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def show_summary(self):
        for key, value in self.items():
            print(f'{key}: {value}')

    def _save_mapping(self, mapping, h5_obj):
        for key, value in mapping.items():
            if isinstance(value, Mapping):
                # If this item is a dictionary, make recursive call
                group = h5_obj.create_group(key)
                self._save_mapping(value, group)
            else:
                dset = h5_obj.create_dataset(key, data=value)
                dset.attrs['type'] = type(value).__name__

    def save(self, filename):
        with h5py.File(filename, 'w') as h5file:
            self._save_mapping(self, h5file)

    def _load_mapping(self, mapping, h5_obj):
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

                # Convert to tuple/list if indicated
                if obj.attrs['type'] == 'tuple':
                    mapping[key] = tuple(value)
                elif obj.attrs['type'] == 'list':
                    mapping[key] = list(value)
                else:
                    mapping[key] = value

            elif isinstance(obj, h5py.Group):
                # For groups, load the mapping recursively
                mapping[key] = {}
                self._load_mapping(mapping[key], obj)

    def load(self, filename):
        with h5py.File(filename, 'r') as h5file:
            self._load_mapping(self, h5file)

# TODO: Relationship between state (for which results are dependent) and common
# model
