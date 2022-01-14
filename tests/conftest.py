# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import tempfile
import pytest
import watts


@pytest.fixture
def run_in_tmpdir(tmpdir):
    orig = tmpdir.chdir()
    try:
        yield
    finally:
        orig.chdir()


@pytest.fixture(autouse=True, scope='session')
def set_tmp_database():
    with tempfile.TemporaryDirectory() as tmpdir:
        watts.Database.set_default_path(tmpdir)
        yield
