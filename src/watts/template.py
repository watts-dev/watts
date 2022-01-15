# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
from typing import Optional

import jinja2

from .fileutils import PathLike
from .parameters import Parameters


class TemplateModelBuilder:
    def __init__(self, template_file: PathLike, **template_kwargs):
        self.template_file = Path(template_file)
        self.template = jinja2.Template(
            self.template_file.read_text(),
            undefined=jinja2.StrictUndefined,
            **template_kwargs
        )

    def __call__(self, params: Parameters, filename: Optional[PathLike] = None):
        # Default rendered template filename
        if filename is None:
            name = self.template_file.name
            out_path = self.template_file.with_name(f'{name}.rendered')
        else:
            out_path = Path(filename)

        # Render template and write to file
        out_path.write_text(self.template.render(**params))
