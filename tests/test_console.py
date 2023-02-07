# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import os
import tempfile

from click.testing import CliRunner
import pytest
import watts
from watts.console import main


@pytest.fixture(autouse=True, scope='module')
def setup_db():
    db_path = watts.Database.get_default_path()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Get current directory and change to temporary
        orig_dir = os.getcwd()
        os.chdir(tmpdir)

        # Set database default path
        watts.Database.set_default_path('tmp_db')
        try:
            yield
        finally:
            watts.Database.set_default_path(db_path)
            os.chdir(orig_dir)


@pytest.fixture(autouse=True, scope='module')
def setup_results(setup_db):
    # Create plugin expecting a single variable
    with open('input_template', 'w') as fh:
        fh.write("{{ variable }}")

    # Setup plugin for running 'cat'
    cat = watts.PluginGeneric(
        executable='cat',
        execute_command='{self.executable} {self.input_name}',
        template_file='input_template',
        plugin_name='cat'
    )

    # Create parameters and execute plugin
    params = watts.Parameters()
    for var in [10, 20, 30]:
        params['variable'] = var
        cat(params, name=f'var={var}')

    yield


def test_console_results(setup_results):
    runner = CliRunner()
    result = runner.invoke(main, 'results')
    full_output = result.stdout
    assert len(full_output.split('\n')) == 8

    result = runner.invoke(main, 'results --plugin cat')
    assert result.stdout == full_output

    result = runner.invoke(main, 'results --name var=20')
    assert len(result.stdout.split('\n')) == 6

    result = runner.invoke(main, 'results --job-id 0')
    assert result.stdout == full_output

    result = runner.invoke(main, 'results --last-job')
    assert result.stdout == full_output

    result = runner.invoke(main, 'results --database none')
    assert len(result.stdout.split('\n')) == 5


def test_console_dir(setup_results):
    db = watts.Database()
    runner = CliRunner()
    for index in range(3):
        result = runner.invoke(main, f'dir {index}')
        assert result.stdout.rstrip() == str(db[index].base_path)

    # Check erroneous database
    result = runner.invoke(main, 'dir --database giraffe 100')
    assert result.exit_code == 1


def test_console_stdout(setup_results):
    db = watts.Database()
    runner = CliRunner()
    for index in range(3):
        result = runner.invoke(main, f'stdout {index}')
        assert result.stdout.rstrip() == db[index].stdout

    # Check erroneous database
    result = runner.invoke(main, 'stdout --database giraffe 100')
    assert result.exit_code == 1


def test_console_rm(setup_results):
    db = watts.Database()
    assert len(db) == 3

    runner = CliRunner()
    runner.invoke(main, 'rm 1')
    assert len(db) == 2

    runner.invoke(main, 'rm --all')
    assert len(db) == 0
