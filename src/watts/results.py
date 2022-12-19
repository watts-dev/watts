# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from collections import namedtuple
from datetime import datetime
from pathlib import Path
import shutil
from typing import List

import dill

from .fileutils import PathLike, open_file
from .parameters import Parameters


ExecInfo = namedtuple('ExecInfo', ['job_id', 'plugin', 'name', 'timestamp'])


class Results:
    """Results from running a workflow

    Parameters
    ----------
    params
        Parameters used to generate inputs
    exec_info
        Execution information (job ID, plugin name, time, etc.)
    inputs
        List of input files
    outputs
        List of output files

    Attributes
    ----------
    base_path
        Path to directory storing results
    inputs
        List of input files
    job_id
        Integer ID of job
    outputs
        List of output files
    parameters
        Parameters used to generate inputs
    plugin
        Name of plugin
    stdout
        Standard output from execution
    time
        Time at which plugin was executed

    """

    def __init__(self, params: Parameters, exec_info: ExecInfo,
                 inputs: List[PathLike], outputs: List[PathLike]):
        self.base_path = Path.cwd()
        self.exec_info = exec_info
        self.parameters = Parameters(params)
        self.inputs = [Path(p) for p in inputs]
        self.outputs = [Path(p) for p in outputs]

    @property
    def plugin(self) -> str:
        return self.exec_info.plugin

    @property
    def time(self) -> datetime:
        return datetime.fromtimestamp(self.exec_info.timestamp * 1e-9)

    @property
    def job_id(self) -> int:
        return self.exec_info.job_id

    @property
    def name(self) -> str:
        return self.exec_info.name

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
            result =  dill.loads(fh.read())

        # For older results objects, add in execution info tuple
        if not hasattr(result, 'exec_info'):
            job_id = None
            plugin = type(result).__name__[7:]
            name = result.__dict__['name']
            dt = result.__dict__['time']
            timestamp = int(dt.timestamp() * 1e6) * 1000
            result.exec_info = ExecInfo(job_id, plugin, name, timestamp)

        return result

    def open_folder(self):
        """Open folder containing results"""
        open_file(self.base_path)

    def __repr__(self):
        if self.name:
            return f"<Results{self.plugin}: {self.name}, {self.time})>"
        else:
            return f"<Results{self.plugin}: {self.time})>"

