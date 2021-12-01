from pathlib import Path
import shutil
from typing import List, Union
from warnings import warn

import platformdirs

from .results import Results


class Database:
    """Database of simulation results

    Parameters
    ----------
    path
        Path to database directory

    Attributes
    ----------
    path
        Base path for the database directory
    default_path
        Path used by default when creating instances if no path is specified
    results
        List of simulation results in database

    """

    _default_path = platformdirs.user_data_path('ardent')
    _instances = {}

    def __new__(cls, path=None):
        # If no path specified, use global default
        if path is None:
            path = cls._default_path

        # If this class has already been instantiated before, return the
        # corresponding instance
        if path in Database._instances:
            return Database._instances[path]
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
        path.mkdir(exist_ok=True)
        self._path = path

        # Read previous results
        self._results = []
        for dir in sorted(self.path.iterdir(), key=lambda x: x.stat().st_ctime):
            try:
                self._results.append(Results.from_hdf5(dir / ".result_info.h5"))
            except Exception:
                warn(f"Could not read results from {dir}")

        # Add instance to class-wide dictionary
        Database._instances[path] = self

    @property
    def path(self) -> Path:
        return self._path

    @property
    def default_path(self) -> Path:
        return self._default_path

    @default_path.setter
    def default_path(self, path):
        self.set_default_path(path)

    @staticmethod
    def set_default_path(path: Union[str, Path]):
        """Set the default path used when instances are created

        Parameters
        ----------
        path
            Default path to use
        """

        Database._default_path = Path(path)

    @property
    def results(self) -> List[Results]:
        return self._results

    def add_result(self, result: Results):
        """Add a result to the database

        Parameters
        ----------
        result
            Simulation results to add

        """
        self._results.append(result)

        # Save result info that can be recreated
        result.save(result.base_path / ".result_info.h5")

    def clear(self):
        """Remove all results from database"""
        for dir in self.path.iterdir():
            shutil.rmtree(dir)
        self.results.clear()

    def show_summary(self):
        """Show a summary of results in database"""
        for result in self.results:
            rel_path = result.base_path.relative_to(self.path)
            print(result.time, result.plugin, str(rel_path),
                  f"({len(result.inputs)} inputs)",
                  f"({len(result.outputs)} outputs)")
