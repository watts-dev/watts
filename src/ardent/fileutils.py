from contextlib import contextmanager
import os
from tempfile import TemporaryDirectory


@contextmanager
def cd_tmpdir():
    """Context manager to change to/return from a tmpdir."""
    with TemporaryDirectory() as tmpdir:
        cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            yield
        finally:
            os.chdir(cwd)
