# SPDX-FileCopyrightText: 2022-2025 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
import sys

import pytest

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


@pytest.mark.skipif(sys.platform == 'win32', reason="O_NONBLOCK not available on Windows")
def test_run_captures_all_output(run_in_tmpdir):
    # Emit enough output to fill multiple pipe-buffer reads (typically 64 KB),
    # then verify every byte is captured.  This is a regression test for the
    # post-exit drain: without draining after p.poll() returns, the last chunk
    # of buffered data could be silently dropped.
    line = "x" * 79 + "\n"   # 80 bytes per line
    n_lines = 2000            # 160 000 bytes — well past one pipe-buffer read
    script = f"import sys; [sys.stdout.write({line!r}) for _ in range({n_lines})]"

    with redirect_stdout(io.StringIO()) as f:
        run([sys.executable, '-c', script])

    captured = f.getvalue()
    assert captured == line * n_lines, (
        f"Expected {n_lines * 80} bytes but got {len(captured)}; "
        "output was likely truncated due to missing post-exit drain"
    )

