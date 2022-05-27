# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import os
import glob
import subprocess
import platform
from datetime import datetime
from pathlib import Path
import shutil
from typing import List, Optional

import numpy as np
import pandas as pd

from .fileutils import PathLike, run as run_proc
from .parameters import Parameters
from .plugin import TemplatePlugin
from .results import Results


class ResultsSAS(Results):
    """SAS simulation results

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
        Standard output from SAS run
    csv_data
        Dictionary with data from .csv files
    """
    def __init__(self, params: Parameters, name: str, time: datetime,
                 inputs: List[PathLike], outputs: List[PathLike]):
        super().__init__('SAS', params, name, time, inputs, outputs)
        self.csv_data = self._get_sas_csv_data()

    @property
    def stdout(self) -> str:
        return (self.base_path / "SAS_log.txt").read_text()

    def _get_sas_csv_data(self) -> dict:
        """Read all sas '.csv' files and return results in a dictionary

        Returns
        -------
        Results from sas .csv files

        """
        csv_files = glob.glob("*.csv") # List all csv files

        csv_data = {}
        for file in csv_files:
            if os.path.getsize(file) > 0: # Check if file is empty
                csv_file_df = pd.read_csv(file)
                for column_name in csv_file_df.columns:
                    csv_data[column_name] =  np.array(csv_file_df[column_name])
        return csv_data


class PluginSAS(TemplatePlugin):
    """Plugin for running SAS

    Parameters
    ----------
    template_file
        Templated SAS input
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when SAS is run
    show_stderr
        Whether to display output from stderr when SAS is run

    Attributes
    ----------
    executable
        Path to SAS executable
    conv_channel
        Path to CHANNELtoCSV utility executable
    conv_primar4
        Path to PRIMAR4toCSV utility executable

    """

    def  __init__(self, template_file: str,
                  extra_inputs: Optional[List[str]] = None,
                  extra_template_inputs: Optional[List[PathLike]] = None,
                  show_stdout: bool = False, show_stderr: bool = False):
        super().__init__(template_file, extra_inputs, extra_template_inputs,
                         show_stdout, show_stderr)

        # Check OS to make sure the extension of the executable is correct.
        # Linux and macOS have different executables but both are ".x".
        # The Windows executable is ".exe".
        sas_dir = Path(os.environ.get("SAS_DIR", ""))
        ext = "exe" if platform.system() == "Windows" else "x"
        self._executable = sas_dir / f"sas.{ext}"
        self._conv_channel = sas_dir / f"CHANNELtoCSV.{ext}"
        self._conv_primar4 = sas_dir / f"PRIMAR4toCSV.{ext}"
        self.input_name = "SAS.inp"

    @property
    def conv_channel(self) -> Path:
        return self._conv_channel

    @property
    def conv_primar4(self) -> Path:
        return self._conv_primar4

    @conv_channel.setter
    def conv_channel(self, exe: PathLike):
        if shutil.which(exe) is None:
            raise RuntimeError(f"CHANNELtoCSV utility executable '{exe}' is missing.")
        self._conv_channel = Path(exe)

    @conv_primar4.setter
    def conv_primar4(self, exe: PathLike):
        if shutil.which(exe) is None:
            raise RuntimeError(f"PRIMAR4toCSV utility executable '{exe}' is missing.")
        self._conv_primar4 = Path(exe)

    def run(self):
        """Run SAS"""
        run_proc([self.executable, "-i", self.input_name, "-o", "out.txt"])

    def postrun(self, params: Parameters, name: str) -> ResultsSAS:
        """Read SAS results and create results object

        Parameters
        ----------
        params
            Parameters used to create SAS model
        name
            Name of the workflow

        Returnss
        -------
        SAS results object
        """

        # Convert CHANNEl.dat and PRIMER4.dat to csv files
        # using SAS utilities. Check if files exist because
        # they may not be outputted per user's choice.
        if Path("CHANNEL.dat").is_file():
            with open("CHANNEL.dat", "r") as file_in, open("CHANNEL.csv", "w") as file_out:
                subprocess.run(str(self.conv_channel), stdin=file_in, stdout=file_out)

        if Path("PRIMAR4.dat").is_file():
            with open("PRIMAR4.dat", "r") as file_in, open("PRIMAR4.csv", "w") as file_out:
                subprocess.run(str(self.conv_primar4), stdin=file_in, stdout=file_out)

        return super().postrun(params, name)
