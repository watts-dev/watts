# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from contextlib import contextmanager
import errno
import os
import platform
import select
import subprocess
import sys
import tempfile
from typing import Union

if sys.platform != 'win32':
    import fcntl

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


class _TeeStream:
    """This class acts as both a context manager (__enter__ and __exit__
    methods) as well as a file stream (write, flush, and isatty methods).

    Roughly based on code in https://github.com/algrebe/python-tee as well as
    the Python standard library
    """
    _stream = None

    def __init__(self, new_target):
        self._new_target = new_target
        self._old_target = None

    def write(self, message):
        self._new_target.write(message)
        self._old_target.write(message)

    def flush(self):
        self._new_target.flush()
        self._old_target.flush()

    def __enter__(self):
        self._old_target = getattr(sys, self._stream)
        setattr(sys, self._stream, self)

    def __exit__(self, exc_type, exc_inst, exc_tb):
        setattr(sys, self._stream, self._old_target)

    def isatty(self):
        return self._new_target.isatty()


class tee_stdout(_TeeStream):
    """Context manager for simulataneously writing to stdout and another stream"""
    _stream = "stdout"


class tee_stderr(_TeeStream):
    """Context manager for simulataneously writing to stderr and another stream"""
    _stream = "stderr"


def run(args):
    """Function that mimics subprocess.run but actually writes to sys.stdout and
    sys.stderr (not the same as the underlying file descriptors)

    Based on https://stackoverflow.com/a/12272262 and
    https://stackoverflow.com/a/7730201
    """
    # Windows doesn't support select.select and fcntl module so just default to
    # using subprocess.run. In this case, show_output/show_stderr won't work.
    if sys.platform == 'win32':
        subprocess.run(args)
        return

    # Helper function to add the O_NONBLOCK flag to a file descriptor
    def make_async(fd):
        fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)

    # Helper function to read some data from a file descriptor, ignoring EAGAIN errors
    def read_async(fd):
        try:
            return fd.read()
        except IOError as e:
            if e.errno != errno.EAGAIN:
                raise e
            else:
                return ''

    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    make_async(p.stdout)
    make_async(p.stderr)

    while True:
        select.select([p.stdout, p.stderr], [], [], 0)

        stdout_data = read_async(p.stdout)
        stderr_data = read_async(p.stderr)
        if stdout_data:
            sys.stdout.write(stdout_data.decode())
        if stderr_data:
            sys.stderr.write(stderr_data.decode())

        if p.poll() is not None:
            break
