# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import watts
import pytest


def test_plugin_output_dir(run_in_tmpdir):
    # Create templates expecting a variable
    with open('main_template', 'w') as fh:
        fh.write("{{ x }}")

    # Create plugin to build template
    plugin = watts.PluginGeneric(
        'cat', ['{self.executable}', '{self.input_name}'], 'main_template')

    # Pass parameters with 'x'
    params = watts.Parameters(x=1)

    # Execute plugin with specified output directory
    res = plugin(params, output_dir='funky')
    assert res.base_path.name == 'funky'

    # Trying the same output directory again should fail
    with pytest.raises(FileExistsError):
        plugin(params, output_dir='funky')
