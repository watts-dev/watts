from collections.abc import MutableMapping

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

    def save(self, filename):
        with h5py.File(filename, 'w') as h5file:
            for key, value in self.items():
                h5file.create_dataset(key, data=value)

    def load(self, filename):
        with h5py.File(filename, 'r') as h5file:
            for key, dset in h5file.items():
                self[key] = dset[()]

# TODO: Relationship between state (for which results are dependent) and common
# model
