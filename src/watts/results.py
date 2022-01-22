#SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
#SPDX-License-Identifier: MIT

from datetime import datetime
from pathlib import Path
import shutil
from typing import List

import h5py

import watts
from .fileutils import PathLike, open_file
from .parameters import Parameters


class Results:
    """Results from running a workflow

    Parameters
    ----------
    plugin
        Name of the plugin that created the results
    params
        Parameters used to generate inputs
    time
        Time at which workflow was run
    inputs
        List of input files
    outputs
        List of output files
    """

    def __init__(self, plugin: str, params: Parameters, time: datetime,
                 inputs: List[PathLike], outputs: List[PathLike]):
        self.base_path = Path.cwd()
        self.plugin = plugin
        self.parameters = Parameters(params)
        self.time = time
        self.inputs = [Path(p) for p in inputs]
        self.outputs = [Path(p) for p in outputs]

    def move_files(self, dst: PathLike):
        """Move input/output files to different directory

        Parameters
        ----------
        dst
            Destination path where files should be moved

        """

        dst_path = Path(dst)
#Move input / output files and change base-- note that trying to use the
#Path.replace method doesn't work across filesystems, so instead we use
#shutil.move
        for i, input in enumerate(self.inputs):
            shutil.move(str(input), str(dst_path / input.name))
            self.inputs[i] = dst_path / input.name
        for i, output in enumerate(self.outputs):
            shutil.move(str(output), str(dst_path / output.name))
            self.outputs[i] = dst_path / output.name
        self.base_path = dst_path

    def _save(self, obj: h5py.Group):
        obj.attrs['plugin'] = self.plugin
        obj.attrs['time'] = self.time.isoformat()
        param_group = obj.create_group('parameters')
        self.parameters.save(param_group)
        inputs = [str(p) for p in self.inputs]
        obj.create_dataset('inputs', data=inputs)
        outputs = [str(p) for p in self.outputs]
        obj.create_dataset('outputs', data=outputs)

    @staticmethod
    def _load(obj: h5py.Group):
            time = datetime.fromisoformat(obj.attrs['time'])
            parameters = Parameters.from_hdf5(obj['parameters'])
            inputs = list(obj['inputs'][()].astype('str'))
            inputs = [Path(p) for p in inputs]
            outputs = list(obj['outputs'][()].astype('str'))
            outputs = [Path(p) for p in outputs]
            return time, parameters, inputs, outputs

    @classmethod
    def from_hdf5(cls, filename: PathLike):
        """Load results from an HDF5 file

        Parameters
        ----------
        filename
            Path to load results from
        """
        with h5py.File(filename, 'r') as h5file:
            plugin = h5file.attrs['plugin']
            if plugin == 'OpenMC':
                result = watts.ResultsOpenMC._from_hdf5(h5file)
            elif plugin == 'MOOSE':
                result = watts.ResultsMOOSE._from_hdf5(h5file)
            else:
                raise RuntimeError(f"Unrecognized plugin in results: {plugin}")

        result.base_path = Path(filename).parent
        return result

    def open_folder(self):
        """Open folder containing results"""
        open_file(self.base_path)
