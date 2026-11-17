# SPDX-FileCopyrightText: 2024 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
import shutil
import subprocess
from typing import List, Optional
import os
import pandas as pd

from .plugin import Plugin
from .results import Results, ExecInfo
from .fileutils import PathLike
from .parameters import Parameters
from .template import TemplateRenderer


class ResultsGCMAT(Results):
    """GCMAT simulation results

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
        Standard output from GCMAT run
    csv_data
        Data from the output CSV file
    """
    def __init__(self, params: Parameters, exec_info: ExecInfo,
                 inputs: List[PathLike], outputs: List[PathLike]):
        super().__init__(params, exec_info, inputs, outputs)
        self.csv_data = self._get_gcmat_csv_data()

    def _get_gcmat_csv_data(self) -> pd.DataFrame:
        """Read GCMAT output CSV file and return results as a DataFrame"""
        output_file = next((p for p in self.outputs if p.name == 'GUIOutputs.csv'), None)
        if output_file and output_file.exists():
            return pd.read_csv(output_file)
        else:
            return pd.DataFrame()  # Return an empty DataFrame if no CSV file is found


class PluginGCMAT(Plugin):
    """Plugin for running GCMAT

    Parameters
    ----------
    template_file
        Template file used to generate the input files
    extra_inputs
        Extra (non-templated) input files
    show_stdout
        Whether to display output from stdout when GCMAT is run
    show_stderr
        Whether to display output from stderr when GCMAT is run

    """
    def __init__(self, template_file: PathLike,
                 extra_inputs: Optional[List[PathLike]] = None,
                 show_stdout: bool = False, show_stderr: bool = False):
        super().__init__(extra_inputs, show_stdout, show_stderr)
        self.template_file = template_file
        self.plugin_name = 'GCMAT'
        self.renderer = TemplateRenderer(template_file)
        self.gcmat_dir = os.getenv('GCMAT_DIR')
        if not self.gcmat_dir:
            raise EnvironmentError("GCMAT_DIR environment variable is not set.")

        # Include './run_repast.sh' as the executable and all files in the 'data' folder as default extra inputs
        self.executable = Path(self.gcmat_dir) / "run_repast.sh"
        self.default_extra_inputs = list((Path(self.gcmat_dir) / "complete_model" / "data").glob("**/*"))

        # Initialize output_folder attribute
        self.output_folder = None

    def prerun(self, params: Parameters) -> None:
        """Generate GCMAT input files

        Parameters
        ----------
        params
            Parameters used by the GCMAT template
        """
        # Render the template to create the input file
        input_file = Path("gc_input.txt")
        self.renderer(params, filename=input_file)

        # Copy the input file to the required directory
        model_directory = Path(self.gcmat_dir) / "complete_model"
        target_directory = model_directory / "data/scenariosNuclear/default_UserInputs"
        target_directory.mkdir(parents=True, exist_ok=True)
        shutil.copy(input_file, target_directory / "demandScenarioV2.txt")

    def run(self, end_year: int = 2080, output_folder: str = "testout", **kwargs):
        """Run GCMAT

        Parameters
        ----------
        end_year
            The year to end the simulation
        output_folder
            The folder where outputs will be stored
        kwargs
            Additional keyword arguments to pass to the subprocess
        """
        # use the absolute path for the output folder
        self.output_folder = os.path.join(self.gcmat_dir, output_folder)
        param_string = f'1\tendAt\t{end_year}'
        command = [str(self.executable), param_string, subprocess.check_output('realpath .', shell=True).strip().decode('utf-8'), output_folder]
        # Run the GCMAT simulation
        subprocess.run(command, cwd=self.gcmat_dir, **kwargs)

    def postrun(self, params: Parameters, exec_info: ExecInfo) -> ResultsGCMAT:
        """Collect information from GCMAT simulation and create results object

        Parameters
        ----------
        params
            Parameters used to create GCMAT model
        exec_info
            Execution information

        Returns
        -------
        GCMAT results object
        """
        output_folder = Path(self.output_folder)  # Retrieve the stored
        # Only collect the GUIOutputs.csv file
        # can add more files if needed
        outputs = []
        gui_outputs_file = output_folder / "GUIOutputs.csv"
        if gui_outputs_file.exists():
            outputs.append(gui_outputs_file)
        return ResultsGCMAT(params, exec_info, self.extra_inputs, outputs)
