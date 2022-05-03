# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from abc import ABC, abstractmethod
from datetime import datetime
import uuid
from pathlib import Path
import shutil
from typing import Optional, List

from .database import Database
from .fileutils import cd_tmpdir, PathLike
from .parameters import Parameters
from .results import Results
from .template import TemplateRenderer


class Plugin(ABC):
    """Class defining the Plugin interface

    Parameters
    ----------
    extra_inputs
        Extra (non-templated) input files
    """

    def __init__(self, extra_inputs: Optional[List[PathLike]] = None):
        self.extra_inputs = []
        if extra_inputs is not None:
            self.extra_inputs = [Path(f).resolve() for f in extra_inputs]

    @abstractmethod
    def prerun(self, params):
        ...

    @abstractmethod
    def run(self):
        ...

    @abstractmethod
    def postrun(self, params) -> Results:
        ...

    def __call__(self, params: Parameters, name: str = 'Workflow', **kwargs) -> Results:
        """Run the complete workflow for the plugin

        Parameters
        ----------
        params
            Parameters used in generating inputs
        name
            Name for workflow
        **kwargs
            Keyword arguments passed to the `run` method

        Returns
        -------
        Results from running workflow
        """
        db = Database()

        with cd_tmpdir():
            # Copy extra inputs to temporary directory
            cwd = Path.cwd()
            for path in self.extra_inputs:
                shutil.copy(str(path), str(cwd))  # Remove str() for Python 3.8+

            # Run workflow in temporary directory
            self.prerun(params)
            self.run(**kwargs)
            result = self.postrun(params, name)

            # Create new directory for results and move files there
            workflow_path = db.path / uuid.uuid4().hex
            workflow_path.mkdir()
            try:
                result.move_files(workflow_path)
            except Exception:
                # If error occurred, make sure we remove results directory so it
                # doesn't pollute database
                shutil.rmtree(workflow_path)
                raise

        # Add result to database
        db.add_result(result)

        return result


class TemplatePlugin(Plugin):
    """Plugin that relies on generating a template file

    Parameters
    ----------
    template_file
        Path to template file
    extra_inputs
        Extra (non-templated) input files
    extra_template_inputs
        Extra templated input files

    """
    def __init__(self, template_file: PathLike, extra_inputs: Optional[List[PathLike]] = None,
                 extra_template_inputs: Optional[List[PathLike]] = None):
        super().__init__(extra_inputs)
        self.render_template = TemplateRenderer(template_file)
        self.extra_render_templates = []
        if extra_template_inputs is not None:
            self.extra_render_templates = [TemplateRenderer(f, '') for f in extra_template_inputs]

    def _get_result_input(self, input_filename: str):
        """Get the data needed to create the postrun results object

        Parameters
        ----------
        input_filename
            Name of the input file for the plugin code

        Returns
        -------
        tuple of data used to create the results object
        """
        time = datetime.fromtimestamp(self._run_time * 1e-9)
        inputs = [p.name for p in self.extra_inputs]
        inputs.append(input_filename)
        for renderer in self.extra_render_templates:
            inputs.append(renderer.template_file.name)
        outputs = [p for p in Path.cwd().iterdir() if p.name not in inputs]
        return time, inputs, outputs

    def prerun(self, params: Parameters, filename: Optional[str] = None):
        """Render the template based on model parameters

        Parameters
        ----------
        params
            Parameters used to render template
        filename
            Filename for rendered template
        """
        # Render the template
        self.render_template(params, filename=filename)
        for render_template in self.extra_render_templates:
            render_template(params)
