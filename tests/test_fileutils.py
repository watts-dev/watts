from pathlib import Path
import sys

from ardent.fileutils import tee_stdout, tee_stderr


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
