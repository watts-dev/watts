from abc import ABC, abstractmethod

from .model import Model
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
    def postrun(self, model):
        ...

    def workflow(self, model: Model):
        """Run the complete workflow for the plugin

        Parameters
        ----------
        model
            Model that is used in generating inputs and storing results
        """
        self.prerun(model)
        self.run()
        self.postrun(model)


class TemplatePlugin(Plugin):
    """Plugin that relies on generating a template file

    Parameters
    ----------
    template_file
        Path to template file
    """
    def  __init__(self, template_file: str):
        self.model_builder = TemplateModelBuilder(template_file)

    def prerun(self, model: Model):
        """Render the template based on model parameters

        Parameters
        ----------
        model
            Model used to render template
        """
        # Render the template
        self.model_builder(model)




