from abc import ABC, abstractmethod

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

    def workflow(self, model):
        self.prerun(model)
        self.run()
        self.postrun(model)


class TemplatePlugin(Plugin):
    def  __init__(self, template_file):
        self.model_builder = TemplateModelBuilder(template_file)

    def prerun(self, model):
        # Render the template
        print("Pre-run for Example Plugin")
        self.model_builder(model)

    def run(self):
        print("Run for Example Plugin")

    def postrun(self, model):
        print("post-run for Example Plugin")



