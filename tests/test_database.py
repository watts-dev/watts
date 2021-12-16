from datetime import datetime
from pathlib import Path

import pytest
import watts


@pytest.fixture(autouse=True, scope='module')
def restore_database_path():
    db_path = watts.Database.get_default_path()
    yield
    watts.Database.set_default_path(db_path)


def get_result():
    return watts.ResultsOpenMC(
        params=watts.Parameters(value=1, lab='Argonne'),
        time=datetime.now(),
        inputs=['geometry.xml'],
        outputs=['statepoint.50.h5'],
    )


def test_change_default_dir(run_in_tmpdir):
    watts.Database.set_default_path('new_database')

    # Make sure creating database uses new default path
    db = watts.Database()
    assert db.path.is_dir()
    assert db.path.name == 'new_database'

    # Creating another database should return the same object
    db2 = watts.Database()
    assert db2 is db


def test_specify_path(run_in_tmpdir):
    db = watts.Database(path='somewhere')
    assert db.path.is_dir()
    assert db.path.name == 'somewhere'

    # Calling Database() again with same arguments should give same instance
    db2 = watts.Database(path='somewhere')
    assert db2 is db

    # Shouldn't matter whether path is relative or absolute
    cwd = Path.cwd()
    db3 = watts.Database(path=cwd / 'somewhere')
    assert db3 is db


def test_add_results(run_in_tmpdir):
    db = watts.Database('tmp_db')

    db.add_result(get_result())
    db.add_result(get_result())

    # Basic sanity checks
    assert len(db.results) == 2
    for result in db.results:
        assert isinstance(result, watts.ResultsOpenMC)
        assert result.parameters['value'] == 1
        assert result.parameters['lab'] == 'Argonne'
        assert len(result.inputs) == 1
        assert len(result.outputs) == 1

    # Ensure database can be cleared
    db.clear()
    assert len(db.results) == 0
