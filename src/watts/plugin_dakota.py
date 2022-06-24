# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import os
import glob
from datetime import datetime
from pathlib import Path
import shutil
from typing import List, Optional

import json
import csv
import numpy as np
import pandas as pd
import subprocess

from .fileutils import PathLike, run as run_proc
from .parameters import Parameters
from .plugin import TemplatePlugin
from .results import Results


class ResultsDakota(Results):
    """Dakota simulation results

    Parameters
    ----------
    params
        Parameters used to generate inputs
    name
        Name of workflow producing results
    time
        Time at which workflow was run
    inputs
        List of input files
    outputs
        List of output files

    Attributes
    ----------
    stdout
        Standard output from Dakota run
    output_data
        Dictionary with data from .dat files
    """
    def __init__(self, params: Parameters, name: str, time: datetime,
                 inputs: List[PathLike], outputs: List[PathLike]):
        super().__init__(params, name, time, inputs, outputs)
        self.output_data = self._get_Dakota_output()

    def _get_Dakota_output(self) -> dict:
        """Read all Dakota '.dat' files and return results in a dictionary

        Returns
        -------
        Results from Dakota .dat files

        """

        # Save Dakota's main output '.dat' files
        output_data = {}
        
        if (glob.glob('dakota_opt.dat')):
            with open('dakota_opt.dat') as f:
                reader = csv.reader(f)
                rows = [row for idx, row in enumerate(reader) if idx == 0]
      
            col_names = str(rows[0][0]).split()
            df = pd.read_csv("dakota_opt.dat", sep="\s+", skiprows=1, names=col_names)

            for name in col_names:
                output_data[name] = np.array(df[name])

        # Save Dakota's final output '.dat' files
        if (glob.glob('finaldata1.dat')):
            with open('finaldata1.dat') as fd:
                reader = csv.reader(fd)
                rows = [row for idx, row in enumerate(reader) if idx == 0]

            new_rows = str(rows[0][0]).split()
            output_data['finaldata1'] = np.array([float(i) for i in new_rows])

        return output_data


class PluginDakota(TemplatePlugin):
    """Plugin for running Dakota

    Parameters
    ----------
    template_file
        Templated Dakota input
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when Dakota is run
    show_stderr
        Whether to display output from stderr when Dakota is run

    """

    def __init__(self, template_file: str,  
                 extra_inputs: Optional[List[str]] = None,
                 extra_template_inputs: Optional[List[PathLike]] = None,
                 show_stdout: bool = False, show_stderr: bool = False):
        super().__init__(template_file, extra_inputs, extra_template_inputs,
                         show_stdout, show_stderr)

        dakota_dir = Path(os.environ.get("DAKOTA_DIR", ""))
        self._executable = dakota_dir / f"dakota.sh"
        self.input_name = "dakota_watts_opt.in"
        self._initial_dir = os.getcwd()

    def run(self):

        # Copy all files to the temporary directory.
        # Avoid duplicate files.

        files = os.listdir(self._initial_dir)
        _current_dir = os.getcwd()
        for fname in files:
            if not os.path.isdir(os.path.join(self._initial_dir, fname)):
                if not os.path.exists(os.path.join(_current_dir, fname)):
                    shutil.copy2(os.path.join(self._initial_dir, fname), _current_dir)
                else:
                    print(os.path.join(self._initial_dir, fname), _current_dir + " already exists")   


        """Run Dakota"""

        run_proc([self.executable, "-i", self.input_name])

    def postrun(self, params: Parameters, name: str) -> ResultsDakota:
        """Read Dakota results and create results object

        Parameters
        ----------
        params
            Parameters used to create Dakota model
        name
            Name of the workflow

        Returns
        -------
        Dakota results object
        """

        return super().postrun(params, name)

class PluginDakotaDriver():
    """Plugin for running the Dakota driver

    Parameters
    ----------
    Attributes
    ----------
    """

    def __init__(self, coupled_code_exec: str):

        self.coupled_code_exec = coupled_code_exec

        self.parse_dakota_input()
        self.run_coupled_code()
        self.return_dakota_input()

    def parse_dakota_input(self):
        """Parse Dakota input

        Parameters
        ----------

        Returns
        -------
        """
        from interfacing import interfacing as di # Dakota's interface module        

        params, self.results = di.read_parameters_file()

        # Dump params to external params.json file for future use by the template engine
        params_for_template_engine_file_path = "params.json"
        with open(params_for_template_engine_file_path, 'w') as outfile:
            f = json.dump(params._variables,  outfile, default=lambda o: o.__dict__)
        
        f = open("params.json")
        data = json.load(f)
        f.close()

        f = open("input.txt", "w+")
        with open('input.tmpl') as file:
            while (line := file.readline().rstrip()):

                i_0 = line.index('=')
                i_1 = line.index('<') + 1
                i_2 = line.index('>') 

                f.write(line[0:i_0] + " = " + str(data[line[i_1:i_2]]) + "\n")
        f.close()

    def run_coupled_code(self):
        if os.path.exists(self.coupled_code_exec):
            P = subprocess.check_output(["python", self.coupled_code_exec])
        else:
            raise RuntimeError("Coupled-code script missing.")

        res_output = []
        with open('opt_res.out') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) > 0:
                    new_str = str(row).split()
                    for j in new_str:
                        try:
                            res_output.append(float(j))
                        except:
                            pass

        self.retval = dict([])
        self.retval['fns'] = res_output

    def return_dakota_input(self):

        # Insert extracted values into results
        # Results iterator provides an index, response name, and response
        try:
          for i, n, r in self.results:
            if r.asv.function:
                try:
                    r.function = self.retval['fns'][i]
                except:
                    pass
        # Catch Dakota 6.9 exception where results interface has changed
        # ValueError: too many values to unpack
        except ValueError:
          i = 0
          for n, r in self.results.items():
              r.function = self.retval['fns'][i]
              i+=1
        self.results.write()

        # Dump to external results.json file
        with open('results.json', 'w') as outfile:
            rst = json.dump(self.results,  outfile, default=lambda o: o.__dict__)

