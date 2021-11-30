import os
import shutil
import subprocess

import numpy as np
import pandas as pd

from .parameters import Parameters
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

    def options(self, SAM_exec):
        """Input SAM user-specified options

        Parameters
        ----------
        SAM_exec
            Path to SAM executable
        """
        self.SAM_exec = SAM_exec
        self.sam_inp_name = "SAM.i"
        self.sam_tmp_folder = "tmp_SAM" # TODO: provide consistency in here we are running the calculation

    def prerun(self, model: Parameters):
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

        log_file_name = "SAM_log.txt"
        if os.path.isfile(log_file_name):
            os.remove(log_file_name)

        shutil.copy("sam_template.rendered", self.sam_tmp_folder+"/"+self.sam_inp_name)
        os.chdir(self.sam_tmp_folder)

        # Check if SAM executable exists.
        with open("../" + log_file_name, "a+") as outfile:
            if os.path.isfile(self.SAM_exec) is False:
                outfile.write("SAM executable is missing. \n")
                raise RuntimeError("SAM executable missing. Please specify path to SAM executable. ")

        # Run SAM and store  error message to SAM log file
        with open("../" + log_file_name, "a+") as outfile:
            subprocess.run([self.SAM_exec + " -i "+self.sam_inp_name+" > "+self.sam_inp_name[:-2]+"_out.txt"], shell=True, stderr=outfile)

        # Copy SAM output to SAM log file
        if os.path.isfile(self.sam_inp_name[:-2]+"_out.txt"):
            with open(self.sam_inp_name[:-2]+"_out.txt") as infile:
                with open("../" + log_file_name, "a+") as outfile:
                    for line in infile:
                        outfile.write(line)

    def postrun(self, model: Parameters):
        """Read SAM results and store in model

        Parameters
        ----------
        model
            Model to store SAM results in
        """
        print("post-run for SAM Plugin")
        self._save_SAM_csv(model)

    def _save_SAM_csv(self, model):
        """Read all SAM '.csv' files and store in model

        Parameters
        ----------
        model
            Model to store SAM results in
        """
        csv_file_name = self.sam_inp_name[:-2] + "_csv.csv"
        # Save SAM's main output '.csv' files
        if os.path.isfile(csv_file_name):
            csv_file_df = pd.read_csv(csv_file_name)
            for column_name in csv_file_df.columns:
                model.set(column_name, np.array(csv_file_df[column_name]), user='plugin_sam')

        # Read SAM's vector postprocesssor '.csv' files and save the parameters as individual array
        exist_name = []
        for file in os.listdir():
            if file.startswith(self.sam_inp_name[:-2] + "_csv_") and not file.endswith("_0000.csv"):
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
