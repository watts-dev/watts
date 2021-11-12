from abc import ABC, abstractmethod
import os
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np
import pandas as pd

from .template import TemplateModelBuilder


class Plugin(ABC):
    """Class defining the Plugin interface"""

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
    """Plugin for running OpenMC"""

    def __init__(self, model_builder):
        self.model_builder = model_builder

    def prerun(self, model):
        self.model_builder(model)

    def run(self, **kwargs):
        import openmc
        self._run_time = time.time()
        openmc.run(**kwargs)

    def postrun(self, model):
        import openmc
        # Determine most recent statepoint
        tstart = self._run_time
        last_statepoint = None
        for sp in Path.cwd().glob('statepoint.*.h5'):
            mtime = sp.stat().st_mtime
            if mtime >= tstart:
                tstart = mtime
                last_statepoint = sp

        # Make sure statepoint was found
        if last_statepoint is None:
            raise RuntimeError("Couldn't find statepoint resulting from OpenMC simulation")

        # Get k-effective and set it on model
        with openmc.StatePoint(last_statepoint) as sp:
            keff = sp.k_combined
        results = {
            'keff': keff.nominal_value,
            'keff_stdev': keff.std_dev
        }
        model['openmc_results'] = results


class TemplatePlugin(Plugin):
    def  __init__(self, template_file):
        self.model_builder = TemplateModelBuilder(template_file)

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


class PluginSAM(TemplatePlugin):
    def  __init__(self, template_file):
        super().__init__(template_file)
        self.sam_inp_name = "SAM.i"
        self.sam_tmp_folder = "tmp_SAM" # TODO: provide consistency in where we are running the calculation
        self.SAM_exec = "../sam-opt-mpi"

    def workflow(self, model): # TODO: move this logic as part of the Plugin base class.
        self.prerun(model)
        self.run()
        self.postrun(model)

    def prerun(self, model):
        # Render the template
        print("Pre-run for SAM Plugin")
        self.model_builder(model)

    def run(self):
        print("Run for SAM Plugin")

        if os.path.exists(self.sam_tmp_folder):
            shutil.rmtree(self.sam_tmp_folder)
        os.mkdir(self.sam_tmp_folder)

        shutil.copy("sam_template.rendered", self.sam_tmp_folder+"/"+self.sam_inp_name)
        os.chdir(self.sam_tmp_folder)

        if os.path.isfile(self.SAM_exec) is False:
            raise RuntimeError("SAM executable missing")

        # Run SAM and stores error message to 'error_log.txt'
        with open('../error_log.txt', "w") as outfile:
            subprocess.run([self.SAM_exec + " -i "+self.sam_inp_name+" > "+self.sam_inp_name[:-2]+"_out.txt"], shell=True, stderr=outfile)

    def postrun(self, model):
        print("post-run for SAM Plugin")
        self.save_SAM_csv(model)

    def save_SAM_csv(self, model):
        csv_file_name = self.sam_inp_name[:-2] + "_csv.csv"
        # Save SAM's main output '.csv' files
        if os.path.isfile(csv_file_name):
            csv_file_df = pd.read_csv(csv_file_name)
            for column_name in csv_file_df.columns:
                model[column_name] = np.array(csv_file_df[column_name])

        # Read SAM's vector postprocesssor '.csv' files and save the parameters as individual array
        exist_name = []
        for file in os.listdir():
            if file.startswith("SAM_csv_") and not file.endswith("_0000.csv"):
                vector_csv_df = pd.read_csv(file)
                csv_param = list(set(list(vector_csv_df.columns)) - set(set(["id", "x", "y", "z"])))
                model[file[:-4]] = np.array(vector_csv_df[csv_param[0]]).astype(np.float64)

                for name in ["id", "x", "y", "z"]:
                    new_name = file[:-8] + name
                    if new_name not in exist_name:
                        model[new_name] = np.array(vector_csv_df[name]).astype(np.float64)
                        exist_name.append(file[:-8] + name)

        os.chdir("../") # TODO: provide consistency in where we are running the calculation
        shutil.rmtree(self.sam_tmp_folder)

