import os
import shutil
import subprocess

import numpy as np
import pandas as pd

from .model import Model
from .plugin import TemplatePlugin


class PluginSAM(TemplatePlugin):
    """Plugin for running SAM

    Parameters
    ----------
    template_file
        Templated SAM input
    """
    def  __init__(self, template_file: str):
        super().__init__(template_file)
        self.sam_inp_name = "SAM.i"
        self.sam_tmp_folder = "tmp_SAM" # TODO: provide consistency in where we are running the calculation
        self.SAM_exec = "../sam-opt-mpi"

    def prerun(self, model: Model):
        """Generate the SAM input based on the template

        Parameters
        ----------
        model
            Model used when rendering template

        """
        # Render the template
        print("Pre-run for SAM Plugin")
        super().prerun(model)

    def run(self):
        """Run SAM"""
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

    def postrun(self, model: Model):
        """Read SAM results and store in model

        Parameters
        ----------
        model
            Model to store SAM results in
        """
        print("post-run for SAM Plugin")
        self._save_SAM_csv(model)

    def _save_SAM_csv(self, model):
        csv_file_name = self.sam_inp_name[:-2] + "_csv.csv"
        # Save SAM's main output '.csv' files
        if os.path.isfile(csv_file_name):
            csv_file_df = pd.read_csv(csv_file_name)
            for column_name in csv_file_df.columns:
                model.set(column_name, np.array(csv_file_df[column_name]), user='plugin_sam')

        # Read SAM's vector postprocesssor '.csv' files and save the parameters as individual array
        exist_name = []
        for file in os.listdir():
            if file.startswith("SAM_csv_") and not file.endswith("_0000.csv"):
                vector_csv_df = pd.read_csv(file)
                csv_param = list(set(list(vector_csv_df.columns)) - set(set(["id", "x", "y", "z"])))
                model.set(file[:-4], np.array(vector_csv_df[csv_param[0]]).astype(np.float64), user='plugin_sam')

                for name in ["id", "x", "y", "z"]:
                    new_name = file[:-8] + name
                    if new_name not in exist_name:
                        model.set(new_name, np.array(vector_csv_df[name]).astype(np.float64), user='plugin_sam')
                        exist_name.append(file[:-8] + name)

        os.chdir("../") # TODO: provide consistency in where we are running the calculation
        shutil.rmtree(self.sam_tmp_folder)
