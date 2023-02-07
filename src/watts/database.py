# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from collections.abc import Sequence
from pathlib import Path
import pprint
import shutil
from typing import Union
from warnings import warn

import platformdirs

from .results import Results


class Database(Sequence):
    """Database of simulation results

    Parameters
    ----------
    path
        Path to database directory

    Attributes
    ----------
    default_path
        Path used by default when creating instances if no path is specified
    job_id
        Integer ID assigned to new results
    path
        Base path for the database directory
    results
        List of simulation results in database

    """

    _default_path = platformdirs.user_data_path('watts')
    _instances = {}

    def __new__(cls, path=None):
        # If no path specified, use global default
        if path is None:
            path = cls._default_path

        # If this class has already been instantiated before, return the
        # corresponding instance
        abs_path = Path(path).resolve()
        if abs_path in Database._instances:
            return Database._instances[abs_path]
        else:
            return super().__new__(cls)

    def __init__(self, path=None):
        # If no path specified, use global default
        if path is None:
            path = self._default_path

        # If instance has already been created, no need to perform setup logic
        if path in Database._instances:
            return

        # Create database directory if it doesn't already
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        self._path = path

        # Read previous results
        self._results = []
        for dir in sorted(self.path.iterdir(), key=lambda x: x.stat().st_ctime):
            try:
                self._results.append(Results.from_pickle(dir / ".result_info.pkl"))
            except Exception:
                warn(f"Could not read results from {dir}")

        # Determine unique job ID based on what has already been used
        used_job_ids = set()
        for result in self:
            job_id = getattr(result, 'job_id', None)
            if job_id is not None:
                used_job_ids.add(job_id)
        self.job_id = max(used_job_ids, default=-1) + 1

        # Add instance to class-wide dictionary
        Database._instances[path.resolve()] = self

    def __repr__(self):
        return pprint.pformat(self._results)

    def __getitem__(self, index):
        return self._results[index]

    def __len__(self):
        return len(self._results)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def default_path(self) -> Path:
        return self.get_default_path()

    @default_path.setter
    def default_path(self, path):
        self.set_default_path(path)

    @classmethod
    def set_default_path(cls, path: Union[str, Path]):
        """Set the default path used when instances are created

        Parameters
        ----------
        path
            Default path to use
        """

        cls._default_path = Path(path).resolve()

    @classmethod
    def get_default_path(cls) -> Path:
        """Get the default path used when instances are created

        Returns
        -------
        Default path
        """
        return cls._default_path

    def add_result(self, result: Results):
        """Add a result to the database

        Parameters
        ----------
        result
            Simulation results to add

        """
        self._results.append(result)

        # Save result info that can be recreated
        result.save(result.base_path / ".result_info.pkl")

    def clear(self):
        """Remove all results from database"""
        for dir in self.path.iterdir():
            shutil.rmtree(dir)
        self._results.clear()

    def remove(self, result: Results):
        """Remove a single result from the database

        Parameters
        ----------
        result
            Result to remove from the database

        """
        self._results.remove(result)
        shutil.rmtree(result.base_path)

    def show_summary(self):
        """Show a summary of results in database"""
        for result in self._results:
            rel_path = result.base_path.relative_to(self.path)
            print(result.time, result.plugin, str(rel_path),
                  f"({len(result.inputs)} inputs)",
                  f"({len(result.outputs)} outputs)")
