from abc import ABC, abstractmethod
import os, sys, shutil
import csv


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
        run_crash = self.run()
        postrun_crash = self.postrun()

    def prerun(self, model):
        # Render the template
        print("Pre-run for Example Plugin")
        self.model_builder(model)

    def run(self):
        print("Run for Example Plugin")
        

    def postrun(self):
        print("post-run for Example Plugin")

class PluginSAM(Plugin):
    def  __init__(self, model_builder):
        self.model_builder = model_builder

    def workflow(self, model):
        prerun_crash = self.prerun(model)
        run_crash = self.run()
        postrun_crash = self.postrun()

    def prerun(self, model):
        # Render the template
        print("Pre-run for SAM Plugin")
        self.model_builder(model)

    def run(self):
        print("Run for SAM Plugin")
        sam_inp_name = "SAM.i"
        sam_tmp_folder = "tmp_SAM"
        if os.path.exists(sam_tmp_folder):
            shutil.rmtree(sam_tmp_folder)
        os.mkdir(sam_tmp_folder)

        shutil.copy("sam_template.rendered", sam_tmp_folder+"/"+sam_inp_name)
        os.chdir(sam_tmp_folder)
        SAM_exec = "../sam-opt-mpi"
        if os.path.isfile(SAM_exec) is False:
            raise RuntimeError("SAM executable missing")
        os.system(SAM_exec+" -i "+sam_inp_name+" > "+sam_inp_name+".out")

    def postrun(self, model):
        print("post-run for SAM Plugin")
        # TODO: find all '.cvs' files
        # TODO: save results form CVS files into 'model'
        model['SAM_result'] = 0


