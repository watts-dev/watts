# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
import shutil
import subprocess
from typing import List, Optional

import numpy as np
import pandas as pd

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import PluginGeneric, _find_executable
from .results import Results, ExecInfo


class ResultsRELAP5(Results):
    """RELAP5 simulation results

    Parameters
    ----------
    params
        Parameters used to generate inputs
    exec_info
        Execution information (job ID, plugin name, time, etc.)
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
    def __init__(self, params: Parameters, exec_info: ExecInfo,
                 inputs: List[PathLike], outputs: List[PathLike]):
        super().__init__(params, exec_info, inputs, outputs)
        self.csv_data = self._get_relap5_csv_data()

    def _get_relap5_csv_data(self) -> dict:
        """Read relap5 '.csv' file and return results in a dictionary

        Returns
        -------
        Results from relap5 .csv files

        """
        csv_data = {}
        if Path('R5-out.csv').exists():
            csv_file_df = pd.read_csv('R5-out.csv')
            for column_name in csv_file_df.columns:
                csv_data[column_name] =  np.array(csv_file_df[column_name])
        return csv_data

class PluginRELAP5(PluginGeneric):
    """Plugin for running RELAP5

    Parameters
    ----------
    template_file
        Templated RELAP5 input
    executable
        Path to RELAP5 executable
    plotfl_to_csv
        Whether to convert RELAP5's plotfl file to CSV file
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when RELAP5 is run
    show_stderr
        Whether to display output from stderr when RELAP5 is run

    """

    def  __init__(
        self,
        template_file: str,
        executable: PathLike = 'relap5.x',
        plotfl_to_csv: bool = True,
        extra_inputs: Optional[List[str]] = None,
        extra_template_inputs: Optional[List[PathLike]] = None,
        show_stdout: bool = False,
        show_stderr: bool = False
    ):
        executable = _find_executable(executable, 'RELAP5_DIR')
        execute_command = ['{self.executable}', '-i', '{self.input_name}']
        super().__init__(
            executable, execute_command, template_file, extra_inputs,
            extra_template_inputs, show_stdout, show_stderr)
        self.input_name = "RELAP5.i"
        self.plotfl_to_csv = plotfl_to_csv

    def run(self, extra_args: Optional[List[str]] = None):
        """Run RELAP5

        Parameters
        ----------
        extra_args
            Extra arguments to be appended when running the RELAP5 executable
        """

        # Copy all necessary files to the temporary directory. RELAP5 requires
        # the executable file and the license key to be in the same directory as
        # the input file to run. Users can also add all fluid property files
        # here.
        cwd = Path.cwd()
        for fname in self.executable.parent.iterdir():
            shutil.copy2(str(fname), str(cwd))

        # Create a list for RELAP5 input command and append any extra
        # options to it.
        if extra_args is None:
            extra_args = []
        command = self.execute_command + extra_args

        # run_proc() does not work with RELAP5-3D.
        # The extra argument of 'stdout' to subprocess.Popen() in run_proc() somehow prevents RELAP5 from running.
        # As a work-around, we explicitly use subprocess.Popen() here without specifying 'stdout=subprocess.PIPE')
        p = subprocess.Popen(command)
        stdout, stderr = p.communicate()

    def postrun(self, params: Parameters, exec_info: ExecInfo) -> ResultsRELAP5:
        """Read RELAP5 results and create results object

        Parameters
        ----------
        params
            Parameters used to create RELAP5 model
        exec_info
            Execution information

        Returns
        -------
        RELAP5 results object
        """

        # Convert RELAP5's plotfl file to CSV file for processing
        if self.plotfl_to_csv:
            if Path('plotfl').exists():
                self._plotfl_to_csv()
            else:
                raise RuntimeError(
                    "Output plot file 'plotfl' is missing. Please make sure you "
                    "are running the correct version of RELAP5-3D or the plot "
                    "file is named correctly."
                )

        return super().postrun(params, exec_info)

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
        data_dict = {'channel': channel_list, 'id': id_list}

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
        return [i for i, file_i in enumerate(file) if keyword in file_i]

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
        while '' in value_list:
            value_list.remove('')

        # Remove first element, i.e. markers
        del value_list[0]

        return value_list
