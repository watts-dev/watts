# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import csv
import json
import os
from pathlib import Path
import pickle
import subprocess
from typing import List, Optional

import numpy as np
import pandas as pd

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import PluginGeneric, _find_executable
from .results import Results, ExecInfo


class ResultsDakota(Results):
    """Dakota simulation results

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
        Standard output from Dakota run
    output_data
        Dictionary with data from .dat files
    """
    def __init__(self, params: Parameters, exec_info: ExecInfo,
                 inputs: List[PathLike], outputs: List[PathLike]):
        super().__init__(params, exec_info, inputs, outputs)
        self.output_data = self._get_Dakota_output(params)

    def _get_Dakota_output(self, params: Parameters) -> dict:
        """Read all Dakota '.dat' files and return results in a dictionary

        Returns
        -------
        Results from Dakota .dat files

        """

        dakota_out_file_name = params.get('dakota_out_file', 'dakota_opt.dat')

        # Save Dakota's main output '.dat' files
        output_data = {}

        if Path(dakota_out_file_name).exists():
            with open(dakota_out_file_name) as f:
                col_names = f.readline().split()
            df = pd.read_csv(dakota_out_file_name, sep="\s+", skiprows=1, names=col_names)

            for name in col_names:
                output_data[name] = np.array(df[name])

        # Save Dakota's final output '.dat' files
        if Path('finaldata1.dat').exists():
            with open('finaldata1.dat') as fd:
                reader = csv.reader(fd)
                rows = [row for idx, row in enumerate(reader) if idx == 0]

            new_rows = str(rows[0][0]).split()
            output_data['finaldata1'] = np.array([float(i) for i in new_rows])

        return output_data


class PluginDakota(PluginGeneric):
    """Plugin for running Dakota

    Parameters
    ----------
    template_file
        Templated Dakota input
    executable
        Path to Dakota script
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when Dakota is run
    show_stderr
        Whether to display output from stderr when Dakota is run

    Attributes
    ----------
    executable
        Path to DAKOTA script
    execute_command
        List of command-line arguments used to call the executable

    """
    def __init__(
        self,
        template_file: str,
        executable: PathLike = 'dakota.sh',
        extra_inputs: Optional[List[str]] = None,
        extra_template_inputs: Optional[List[PathLike]] = None,
        auto_link_files: Optional[str] = None,
        show_stdout: bool = False,
        show_stderr: bool = False
    ):
        executable = _find_executable(executable, 'DAKOTA_DIR')
        execute_command = ['{self.executable}', '-i', '{self.input_name}']
        super().__init__(
            executable, execute_command, template_file, extra_inputs,
            extra_template_inputs, show_stdout, show_stderr)

        self.input_name = template_file
        self.plugin_name = "Dakota"
        self._auto_link_files = auto_link_files

        # Setup to automatically include all 'extra_inputs' and 'extra_template_inputs'
        # to Dakota's "link files" option. Create a string of the file names in
        # 'extra_inputs' and 'extra_template_inputs'.
        if self._auto_link_files is not None:
            dakota_link_files = []
            if extra_inputs is not None:
                dakota_link_files.extend(list(extra_inputs))

            if extra_template_inputs is not None:
                dakota_link_files.extend(list(extra_template_inputs))

            self.dakota_link_files_string = " ".join(f"'{item}'" for item in dakota_link_files)

    def prerun(self, params: Parameters, filename: Optional[str] = None):
        """ Change the permisison of the Dakota driver file

        Parameters
        ----------
        params
            Parameters used to render template
        """

        # Store the string for the "link_files" in params.
        if self._auto_link_files is not None:
            params[self._auto_link_files] = self.dakota_link_files_string

        super().prerun(params)
        if 'dakota_driver_name' in params.keys():
            os.chmod(params['dakota_driver_name'], 0o755)

    @property
    def execute_command(self):
        return [str(self.executable), "-i", self.input_name]


def run_dakota_driver(coupled_code_exec: str):
    """ Function to execute the workflow for data
    exchange between Dakota and the coupled code
    in the Dakota driver script.

    Parameters
    ----------
    coupled_code_exec
        The name of the WATTS python script of the
        coupled code.
    """
    results = _parse_dakota_input()
    retval = _run_coupled_code(coupled_code_exec)
    _return_dakota_input(results, retval)


def _parse_dakota_input() -> Results:
    """Parse Dakota input

    Parameters
    ----------

    Returns
    -------
    results
        Results from Dakota's output file
    """

    from interfacing import interfacing as di # Dakota's interface module

    params, results = di.read_parameters_file()

    # Dump params to external params.json file for future use by the template engine
    params_for_template_engine_file_path = "params.json"
    with open(params_for_template_engine_file_path, 'w') as outfile:
        f = json.dump(params._variables,  outfile, default=lambda o: o.__dict__)
    return(results)


def _run_coupled_code(coupled_code_exec: str) -> dict:
    """ Run the coupled code

    Parameters
    ----------
    coupled_code_exec
        The name of the WATTS python script of the
        coupled code.

    Returns
    -------
    retval
        Processed output from the coupled code.
    """

    if not os.path.exists(coupled_code_exec):
        raise FileNotFoundError("Coupled-code script missing.")

    subprocess.check_output(["python", coupled_code_exec])

    # Read the 'opt_res.out' pickle file and
    # store the results to 'res_output' for data
    # transfer with Dakota.
    if os.path.exists('opt_res.out'):
        db = pickle.load(open('opt_res.out', 'rb'))
        if 'dakota_descriptors' in db.keys():
            res_output = []
            for key in db['dakota_descriptors']:
                res_output.append(db[db['dakota_descriptors'][key]])
    else:
        raise RuntimeError("'opt_res.out' file is missing.")

    return {'fns': res_output}


def _return_dakota_input(results: Results, retval: dict):
    """ Return the output of the coupled code
    to Dakota.

    Parameters
    ----------
    results
        Results from Dakota's output file
    retval
        Processed output from the coupled code.
    """

    # Insert extracted values into results
    # Results iterator provides an index, response name, and response
    try:
        for i, n, r in results:
            if r.asv.function:
                # Returns the response function value from the coupled
                # code to Dakota (for pre Dakota v6.9).
                try:
                    r.function = retval['fns'][i]
                except:
                    pass
    # Catch Dakota 6.9 exception where results interface has changed
    # ValueError: too many values to unpack
    except ValueError:
        for i, (n, r) in enumerate(results.items()):
            r.function = retval['fns'][i]
    results.write()

    # Dump to external results.json file
    with open('results.json', 'w') as outfile:
        rst = json.dump(results, outfile, default=lambda o: o.__dict__)
