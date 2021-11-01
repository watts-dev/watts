import ardent
import jinja2
import pytest


def test_undefined_template(run_in_tmpdir):
    # Create template expecting variable
    with open('example_template', 'w') as fh:
        fh.write("{{ variable }}")

    # Create plugin to build template
    model_builder = ardent.TemplateModelBuilder('example_template')
    plugin = ardent.ExamplePlugin(model_builder)

    # Passing model with 'variable' set should work
    model = ardent.Model(variable=1)
    plugin.prerun(model)
    with open('example_template.rendered', 'r') as fh:
        rendered = fh.read()
    assert rendered == '1'

    # Passing empty model should raise jinja2.UndefinedError
    empty_model = ardent.Model()
    with pytest.raises(jinja2.UndefinedError) as e:
        plugin.prerun(empty_model)
