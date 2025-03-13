# SPDX-FileCopyrightText: 2024 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
from typing import List, Optional
import pandas as pd
import h5py as h5 
import json

from .plugin import Plugin, PluginGeneric, _find_executable
from .results import Results, ExecInfo
from .fileutils import PathLike
from .parameters import Parameters
from .template import TemplateRenderer


class ResultsDYMOND(Results):
    """DYMOND simulation results

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
    stocks
        Dictionary of cumulative material stored in the model at each time point by agent type and material type
    flows
        Dictionary of material that has entered an agent between each time point by agent type and material type
    operations
        Dictionary of facility operational data (e.g., power produced or material throughput)
    output_data
        Dictionary with information on structure of other dictionaries (model times and nuclides)

    stdout
        standard output from a DYMOND run
    """

    def __init__(self, params: Parameters, exec_info: ExecInfo,
                 inputs: List[Path], outputs: List[Path]):
        super().__init__(params, exec_info, inputs, outputs)
        self.stocks, self.flows, self.operations, self.output_data = self._get_dymond_json_data()

    def _get_dymond_json_data(self) -> dict:
        """Read abbreviated DYMOND output JSON files and return it as dictionaries"""
        for oup in self.outputs:
            if "stocks" in oup:
                stocks_dict = json.read(oup)
            elif "flows" in oup:
                flows_dict = json.read(oup)
            elif "operations" in oup:
                operations_dict = json.read(oup)
            elif "output" in oup:
                output_data_dict = json.read(oup)
        
        return(stocks_dict, flows_dict, operations_dict, output_data_dict)


class PluginDYMOND(PluginGeneric):
    """Plugin for running DYMOND simulations
    
        Parameters
    ----------
    template_file
        Templated DYMOND input
    executable
        Path to DYMOND bash/shell script
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when DYMOND is run
    show_stderr
        Whether to display output from stderr when DYMOND is run

    Attributes
    ----------
    executable
        Path to DYMOND executable
    execute_command
        List of command-line arguments to call the executable
    """


    def __init__(self, 
                 template_file: PathLike,
                 executable: PathLike = 'dymond.sh',
                 extra_inputs: Optional[List[str]] = None,
                 extra_template_inputs: Optional[List[PathLike]] = None,
                 show_stdout: bool = False,
                 show_stderr: bool = False):
        
        executable = _find_executable(executable, 'DYMOND_DIR')
        execute_command = ['{self.executable}', '-i', '{self.input_name}']

        super().__init__(executable, execute_command, template_file, extra_inputs,
                         extra_template_inputs, "DYMOND", show_stdout, show_stderr)     
        
        self.input_name = "DYMOND_input"

    @PluginGeneric.executable.setter
    def executable(self, exe: PathLike):
        if not exe.is_file():
            raise RuntimeError(
                f"{self.plugin_name} module '{exe}' does not exist. The "
                "DYMOND_DIR environment variable needs to be set to a directory "
                "containing the DYMOND scripts and model modules."
            )
        self._executable = Path(exe)    
