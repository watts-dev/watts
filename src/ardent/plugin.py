from abc import ABC, abstractmethod


class Plugin(ABC):
    def __init__(self, template_file):
        ...

    @abstractmethod
    def prerun(self, model):
        # Fill in the template to create real inputs

        # Run arbitrary user scripts
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


class ExamplePlugin(Plugin):
    def  __init__(self, model_builder):
        self.model_builder = model_builder

    def workflow(self, model):
        prerun_crash = self.prerun(model)
        if prerun_crash is False:
            run_crash = self.run()
            if run_crash is False:
                postrun_crash = self.postrun()

    def prerun(self, model):
        # Render the template
        prerun_crash = False
        print("Pre-run for Example Plugin")
        self.model_builder(model)
        return prerun_crash

    def run(self):
        run_crash = False
        print("Run for Example Plugin")
        return run_crash

    def postrun(self):
        post_crash = False
        print("post-run for Example Plugin")
        return post_crash
