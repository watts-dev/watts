from abc import ABC, abstractmethod

from .database import Database
from .fileutils import cd_tmpdir
from .model import Parameters
from .results import Results
from .template import TemplateModelBuilder


class Plugin(ABC):
    """Class defining the Plugin interface"""

    @abstractmethod
    def prerun(self, model):
        ...

    @abstractmethod
    def run(self):
        ...

    @abstractmethod
    def postrun(self, model) -> Results:
        ...

    @staticmethod
    def _get_unique_dir(path, name):
        if not (path / name).exists():
            return path / name

        # Try adding number as suffix
        i = 1
        while True:
            unique_name = f"{name}_{i}"
            if not (path / unique_name).exists():
                return path / unique_name
            i += 1

    def workflow(self, model: Parameters, name='Workflow'):
        """Run the complete workflow for the plugin

        Parameters
        ----------
        model
            Model that is used in generating inputs and storing results
        name
            Unique name for workflow
        """
        db = Database()

        # Create new directory for results
        workflow_path = self._get_unique_dir(db.path, name)
        workflow_path.mkdir()

        with cd_tmpdir():
            # Run workflow in temporary directory
            self.prerun(model)
            self.run()
            result = self.postrun(model)

            # Move files to results directory
            result.move_files(workflow_path)

        # Add result to database
        db.add_result(result)

        return result


class TemplatePlugin(Plugin):
    """Plugin that relies on generating a template file

    Parameters
    ----------
    template_file
        Path to template file
    """
    def  __init__(self, template_file: str):
        self.model_builder = TemplateModelBuilder(template_file)

    def prerun(self, model: Parameters):
        """Render the template based on model parameters

        Parameters
        ----------
        model
            Model used to render template
        """
        # Render the template
        print("Pre-run for Example Plugin")
        self.model_builder(model)
