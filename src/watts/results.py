# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from datetime import datetime
from pathlib import Path
import shutil
from typing import List

import dill

from .fileutils import PathLike, open_file
from .parameters import Parameters


class Results:
    """Results from running a workflow

    Parameters
    ----------
    params
        Parameters used to generate inputs
    time
        Time at which workflow was run
    inputs
        List of input files
    outputs
        List of output files
    """

    def __init__(self, params: Parameters, name: str, time: datetime,
                 inputs: List[PathLike], outputs: List[PathLike]):
        self.base_path = Path.cwd()
        self.name = name
        self.parameters = Parameters(params)
        self.time = time
        self.inputs = [Path(p) for p in inputs]
        self.outputs = [Path(p) for p in outputs]

    @property
    def plugin(self):
        if type(self) is Results:
            return "Generic"
        else:
            return type(self).__name__[7:]

    @property
    def stdout(self) -> str:
        return (self.base_path / f"{self.plugin}_log.txt").read_text()

    def move_files(self, dst: PathLike):
        """Move input/output files to different directory

        Parameters
        ----------
        dst
            Destination path where files should be moved

        """

        dst_path = Path(dst)
        # Move input/output files and change base -- note that trying to use the
        # Path.replace method doesn't work across filesystems, so instead we use
        # shutil.move
        for i, input in enumerate(self.inputs):
            shutil.move(str(input), str(dst_path / input.name))
            self.inputs[i] = dst_path / input.name
        for i, output in enumerate(self.outputs):
            shutil.move(str(output), str(dst_path / output.name))
            self.outputs[i] = dst_path / output.name
        self.base_path = dst_path

    def save(self, filename: PathLike):
        """Save results to a pickle file

        Parameters
        ----------
        filename
            File to save results to
        """
        with open(filename, 'wb') as fh:
            fh.write(dill.dumps(self))

    @classmethod
    def from_pickle(cls, filename: PathLike):
        """Load results from a pickle file

        Parameters
        ----------
        filename
            Path to load results from
        """
        with open(filename, 'rb') as fh:
            return dill.loads(fh.read())

    def open_folder(self):
        """Open folder containing results"""
        open_file(self.base_path)

    def __repr__(self):
        if self.name:
            return f"<Results{self.plugin}: {self.name}, {self.time})>"
        else:
            return f"<Results{self.plugin}: {self.time})>"

