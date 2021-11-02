import jinja2


class TemplateModelBuilder:
    def __init__(self, template_file, **template_kwargs):
        self.template_file = template_file
        with open(template_file, 'r') as fh:
            self.template = jinja2.Template(
                fh.read(),
                undefined=jinja2.StrictUndefined,
                **template_kwargs
            )

    def __call__(self, model, filename=None):
        # Default rendered template filename
        if filename is None:
            filename = self.template_file + '.rendered'

        # Render template and write to file
        with open(filename, 'w') as fh:
            fh.write(self.template.render(**model))
