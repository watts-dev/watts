# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import os
import glob
import subprocess
import platform
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path
import shutil
import time
from typing import List, Optional

import numpy as np
import pandas as pd

from .fileutils import PathLike, run as run_proc, tee_stdout, tee_stderr
from .parameters import Parameters
from .plugin import TemplatePlugin
from .results import Results


class ResultsRELAP5(Results):
    """RELAP5 simulation results

    Parameters
    ----------
    params
        Parameters used to generate inputs
    time
        Time at which workflow was run
    inputs
        List of input files
    outputs
        List of output files

    Attributes
    ----------
    stdout
        Standard output from RELAP5 run
    csv_data
        Dictionary with data from .csv files
    """
    def __init__(self, params: Parameters, time: datetime,
                 inputs: List[PathLike], outputs: List[PathLike]):
        super().__init__('RELAP5-3D', params, time, inputs, outputs)
        self.csv_data = self._get_relap5_csv_data()

    @property
    def stdout(self) -> str:
        return (self.base_path / "RELAP5_log.txt").read_text()

    def _get_relap5_csv_data(self) -> dict:
        """Read relap5 '.csv' file and return results in a dictionary

        Returns
        -------
        Results from relap5 .csv files

        """
        csv_data = {}
        if os.path.exists('R5-out.csv'):
            csv_file_df = pd.read_csv('R5-out.csv')
            for column_name in csv_file_df.columns:
                csv_data[column_name] =  np.array(csv_file_df[column_name])
        return csv_data

class PluginRELAP5(TemplatePlugin):
    """Plugin for running RELAP5

    Parameters
    ----------
    template_file
        Templated RELAP5 input
    show_stdout
        Whether to display output from stdout when RELAP5 is run
    show_stderr
        Whether to display output from stderr when RELAP5 is run
    plotfl_to_csv
        Whether to convert RELAP5-3D's plotfl file to CSV file
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    extra_options
        Extra options for running RELAP5

    Attributes
    ----------
    relap5_dir
        Path to RELAP5 executable

    """

    def  __init__(self, template_file: str, show_stdout: bool = False,
                  show_stderr: bool = False, plotfl_to_csv: bool = True,
                  extra_inputs: Optional[List[str]] = None,
                  extra_template_inputs: Optional[List[PathLike]] = None,
                  extra_options: Optional[List[str]] = None):
        super().__init__(template_file, extra_inputs, extra_template_inputs)

        # Check OS to make sure the extension of the executable is correct.
        # Linux and macOS have different executables but both are ".x".
        # The Windows executable is ".exe".

        self._relap5_dir = Path(os.environ.get("RELAP5_DIR", ""))
        self.ext = "exe" if platform.system() == "Windows" else "x"
        self._relap5_exec = f"relap5.{self.ext}"

        self.relap5_inp_name = "RELAP5.i"
        self.show_stdout = show_stdout
        self.show_stderr = show_stderr
        self.plotfl_to_csv = plotfl_to_csv
        self.extra_options = extra_options

    @property
    def relap5_dir(self) -> Path:
        return self._relap5_dir

    @relap5_dir.setter
    def relap5_dir(self, relap5_directory:PathLike):
        if shutil.which(Path(relap5_directory) / f"relap5.{self.ext}") is None:
            raise RuntimeError("RELAP5-3D executable is missing.")
        self._relap5_dir = Path(relap5_directory)

    def prerun(self, params: Parameters):
        """Generate the RELAP5 input based on the template

        Parameters
        ----------
        params
            Parameters used when rendering template
        """
        # Render the template
        # Make a copy of params and convert units if necessary
        # The original params remains unchanged

        params_copy = params.convert_units()

        print("Pre-run for RELAP5 Plugin")
        self._run_time = time.time_ns()
        super().prerun(params_copy, filename=self.relap5_inp_name)

        # Copy all necessary files to the temporary directory.
        # RELAP5 requires the executable file and the license key 
        # to be in the same directory as the input file to run.
        # Users can also add all fluid property files here. 

        files = os.listdir(self._relap5_dir)
        for fname in files:
            shutil.copy2(os.path.join(self._relap5_dir, fname), os.getcwd())

        # Create a list for RELAP5 input command and append any extra
        # options to it.

        self._relap5_input = [self._relap5_exec, '-i', self.relap5_inp_name]
        if isinstance(self.extra_options, list):
            for options in self.extra_options:
                self._relap5_input.append(options) 

    def run(self):
        """Run RELAP5"""

        print("Run for RELAP5 Plugin")

        log_file = Path("RELAP5_log.txt")

        # run_proc() does not work with RELAP5-3D.
        # The extra argument of 'stdout' to subprocess.Popen() in run_proc() somehow prevents RELAP5 from running.
        # As a work-around, we explicitly use subprocess.Popen() here without specifying 'stdout=subprocess.PIPE')

        with log_file.open("w") as outfile:
            func_stdout = tee_stdout if self.show_stdout else redirect_stdout
            func_stderr = tee_stderr if self.show_stderr else redirect_stderr
            with func_stdout(outfile), func_stderr(outfile):
                p = subprocess.Popen(self._relap5_input)
                stdout, stderr = p.communicate()

    def postrun(self, params: Parameters) -> ResultsRELAP5:
        """Read RELAP5 results and create results object

        Parameters
        ----------
        params
            Parameters used to create RELAP5 model

        Returns
        -------
        RELAP5 results object
        """
        print("Post-run for RELAP5 Plugin")

        # Convert RELAP5's plotfl file to CSV file for processing
        if self.plotfl_to_csv:
            if os.path.exists('plotfl'):
                self._plotfl_to_csv()
            else:
                raise RuntimeError("Output plot file 'plotfl' is missing. Please make sure you are running the correct version of RELAP5-3D or the plot file is named correctly.")

        time, inputs, outputs = self._get_result_input(self.relap5_inp_name)
        return ResultsRELAP5(params, time, inputs, outputs)

    # The RELAP5-3D version used here does not generate csv output files.
    # It generates a text file with a particular format that needs to
    # be converted to a csv file before the results can be extracted.

    def _plotfl_to_csv(self):
        """Converts RELAP5's plotfl file to csv.

        """

        with open('plotfl') as f:
            contents = f.readlines() 
            
        # Get markers for 'contents'
        n_plotinf = self._check_string(contents, 'plotinf')
        n_plotalf = self._check_string(contents, 'plotalf')
        n_plotnum = self._check_string(contents, 'plotnum')
        n_plotrec = self._check_string(contents, 'plotrec')

        # Break 'contents' into 3 sections: channel, ID, values 
        channels = contents[n_plotalf[0] : n_plotnum[0]]
        ids = contents[n_plotnum[0] : n_plotrec[0]]
        values = contents[n_plotrec[0] : ]

        # Extract values
        channel_list = self._extract_value(channels)
        id_list = self._extract_value(ids)

        # Create a dictionary to store data
        data_dict = {'channel': channel_list,
                'id': id_list}

        for i in range(len(n_plotrec)):
            i_start = n_plotrec[i] - n_plotrec[0] # Subtract n_plotrec[0] to offset the the 'content' above 'values'
            i_end = n_plotrec[i] - n_plotrec[0] + (n_plotrec[1] - n_plotrec[0]) # Add "n_plotrec[1] - n_plotrec[0]" to reach the last line of 'values'
            value_list = np.double(self._extract_value(values[i_start : i_end]))
            data_dict[f"value_t_{i}"] = value_list
            
        # Convert the dictionary into DataFrame
        df = pd.DataFrame(data_dict)
        df.set_index('channel', inplace=True)
        df = df.T

        # Create new column for DataFrame
        new_col = []
        for i in range(len(df.columns)):
            new_col.append(f"{df.columns[i]}-{df.iloc[0][i]}")
            
        df.columns = new_col 
        df = df[1:] # Remove the volume ID row

        # Save DataFrame as csv
        df.to_csv('R5-out.csv')

    def _check_string(self, file, keyword: str) -> list:
        """Looks for certain keyword markers in the plotfl file.

        Parameters
        ----------
        file
            RELAP5 output file
        keyword
            Keyword whose location to look for
        Returns
        -------
        A list of line number of the keyword markers in the plotfl file

        """
        n_line = []
        for i in range(len(file)): 
            if keyword in file[i]:
                n_line.append(i)
        return n_line

    def _extract_value(self, contents):
        """Extracts values from the plotfl file according to the keyword markers.

        Parameters
        ----------
        contents
            RELAP5 output file broken up according to the keyword markers
        Returns
        -------
        List of extracted values.

        """
        value_list = []
        s = ''
        for line in contents:
            value_list.append(s.strip())
            s = ''
            for char_val in line:
                if char_val != ' ':
                    s += str(char_val)
                else:
                    value_list.append(s.strip())
                    s = ''
        value_list.append(s.strip())           
        
        # Remove all spaces
        while('' in value_list):
            value_list.remove('')
        
        # Remove first element, i.e. markers
        del value_list[0] 
        
        return value_list