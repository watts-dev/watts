from abc import ABC, abstractmethod

from .template import TemplateModelBuilder


class Plugin(ABC):
    def __init__(self, template_file):
        ...

    @abstractmethod
    def prerun(self, model):
        # Fill in the template to create real inputs

        # Run arbitrary user scripts
        ...

    @abstractmethod
    def run(self):
        ...

    @abstractmethod
    def postrun(self, model):
        ...


class OpenmcPlugin(Plugin):
    def __init__(self, model_builder):
        self.model_builder = model_builder

    def prerun(self, model):
        self.model_builder(model)


class TemplatePlugin(Plugin):
    def  __init__(self, template_file):
        self.model_builder = TemplateModelBuilder(template_file)

    def prerun(self, model):
        # Render the template
        self.model_builder(model)

    def run(self):
        ...

    def postrun(self):
        ...
