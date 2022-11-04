# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import watts
import jinja2
import pytest


def test_undefined_template(run_in_tmpdir):
    # Create template expecting variable
    with open('example_template', 'w') as fh:
        fh.write("{{ variable }}")

    # Create plugin to build template
    plugin = watts.PluginGeneric('cat', ['{self.executable}', '{self.input_name}'], 'example_template')

    # Passing parameters with 'variable' set should work
    params = watts.Parameters(variable=1)
    plugin.prerun(params)
    with open('input_rendered', 'r') as fh:
        rendered = fh.read()
    assert rendered == '1'

    # Passing empty parameters should raise jinja2.UndefinedError
    empty_params = watts.Parameters()
    with pytest.raises(jinja2.UndefinedError) as e:
        plugin.prerun(empty_params)

def test_extra_template_inputs(run_in_tmpdir):
    # Create templates expecting a variable
    with open('main_template', 'w') as fh:
        fh.write("{{ x }}")
    with open('extra_template', 'w') as fh:
        fh.write("{{ y }}")

    # Create plugin to build template
    plugin = watts.PluginGeneric(
        'cat', ['{self.executable}', '{self.input_name}'],
        'main_template', extra_template_inputs=['extra_template'])

    # Pass parameters with 'x' and 'y' set
    params = watts.Parameters(x=1, y=2)
    plugin.prerun(params)
    with open('input_rendered', 'r') as fh:
        rendered = fh.read()
    assert rendered == '1'
    with open('extra_template', 'r') as fh:
        rendered = fh.read()
    assert rendered == '2'
