from contextlib import contextmanager
import os
import platform
import subprocess
import tempfile
from typing import Union

# Type for arguments that accept file paths
PathLike = Union[str, bytes, os.PathLike]


@contextmanager
def cd_tmpdir():
    """Context manager to change to/return from a tmpdir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            yield
        finally:
            os.chdir(cwd)


def open_file(path: PathLike):
    """Open a file in explorer/finder/nautilus

    Parameters
    ----------
    path
        Path to directory
    """
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
