# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
import sys

from watts.fileutils import tee_stdout, tee_stderr, run


def test_tee_stdout(run_in_tmpdir, capsys):
    # Use tee_stdout to write to stdout and a log file
    dummy_file = Path('log.txt')
    with dummy_file.open('w') as f, tee_stdout(f):
        print('Hello!')

    # Make sure output went to stdout
    captured = capsys.readouterr()
    assert captured.out == 'Hello!\n'

    # Make sure output went to stderr
    assert dummy_file.read_text() == 'Hello!\n'


def test_tee_stderr(run_in_tmpdir, capsys):
    # Use tee_stderr to write to stderr and a log file
    dummy_file = Path('log.txt')
    with dummy_file.open('w') as f, tee_stderr(f):
        sys.stderr.write('Hello!\n')

    # Make sure output went to stdout
    captured = capsys.readouterr()
    assert captured.err == 'Hello!\n'

    # Make sure output went to stderr
    assert dummy_file.read_text() == 'Hello!\n'


def test_run(run_in_tmpdir):
    # Run an executable without catching output but redirect to file
    log_file = Path('env_log.txt')
    with log_file.open('w') as fp:
        subprocess.run(['env'], stdout=fp)
    file_output = log_file.read_text()

    # Using subprocess.run won't catch anything
    with redirect_stdout(io.StringIO()) as f:
        subprocess.run(['env'])
    assert f.getvalue() == ''

    # Using our version of 'run' should catch the output
    with redirect_stdout(io.StringIO()) as f:
        run(['env'])
    assert f.getvalue() == file_output

