import os
from pathlib import Path
import sys
from typing import Optional
import getopt
import subprocess

from astropy.units import Quantity
import numpy as np
# this needs to be installed in Workbench
# environment (follow example from setup_openmc or setup_dassh)
import watts
from wasppy import xml2obj

###
# etc nstauff$ cp watts.py /Applications/Workbench-5.0.0.app/Contents/rte/
# pywatts nstauff$ mkdir bin
# pywatts nstauff$ ln -s /Applications/Workbench-5.0.0.app/Contents/bin/sonvalidxml bin/sonvalidxml
# pywatts nstauff$ ln -s /Applications/Workbench-5.0.0.app/Contents/wasppy ./
# if needed - change wasppy/xml2obj.py line 89 - if isinstance(src, (str,bytes)):
# chmod 777 watts_ui.py
# execute with command: `python watts_ui.py -i examples/watts_comprehensive.son`
###


def load_obj(input_path, watts_path):
    """Converts son file to xml stream and create python data structure

    Parameters
    ----------
    input_path
        Path
    watts_path
        Path to Watts

    Returns
    -------
    xlm stream

    """
    sonvalidxml = watts_path + "/bin/sonvalidxml"
    schema = watts_path + "/etc/watts.sch"
    cmd = ' '.join([sonvalidxml, schema, input_path])
    xmlresult = subprocess.check_output(cmd, shell=True)
    # obtain pieces of input by name for convenience
    return xml2obj.xml2obj(xmlresult)


def create_plugins(plugins):
    """Create a dictionary to store plugins

    Parameters
    ----------
    plugins
        User input plugins

    Returns
    -------
    watts_plugins
        Watts plugins for storing user input plugins info

    """
    watts_plugins = {}
    for it, plg in enumerate(watts_wb.plugins.plugin):
        nested_plugins = {}

        # Initialize
        nested_plugins['exec_dir'] = None
        nested_plugins['extra_inputs'] = None
        nested_plugins['extra_template_inputs'] = None
        nested_plugins['show_stderr'] = False
        nested_plugins['show_stdout'] = False
        nested_plugins['plotfl_to_csv'] = False

        # Save string plugin inputs
        nested_plugins['code'] = str(plg.code.value).strip('\"')
        nested_plugins['template'] = str(plg.template.value).strip('\"')
        if plg.exec_dir is not None:
            nested_plugins['exec_dir'] = str(plg.exec_dir.value).strip('\"')
        if plg.exec_name is not None:
            nested_plugins['exec_name'] = str(plg.exec_name.value).strip('\"')
        if plg.auto_link_files is not None:
            nested_plugins['auto_link_files'] = str(
                plg.auto_link_files.value).strip('\"')
        if plg.conv_channel is not None:
            nested_plugins['conv_channel'] = str(
                plg.conv_channel.value).strip('\"')
        if plg.conv_primar4 is not None:
            nested_plugins['conv_primar4'] = str(
                plg.conv_primar4.value).strip('\"')

        # Save list plugin inputs
        if plg.extra_inputs is not None:
            nested_plugins['extra_inputs'] = convert_to_list(plg.extra_inputs)
        if plg.extra_template_inputs is not None:
            nested_plugins['extra_template_inputs'] = convert_to_list(
                plg.extra_template_inputs)
        if plg.scores is not None:
            nested_plugins['scores'] = convert_to_list(plg.scores)
        if plg.score_names is not None:
            nested_plugins['score_names'] = convert_to_list(plg.score_names)
        if plg.extra_args is not None:
            nested_plugins['extra_args'] = convert_to_list(plg.extra_args)

        # Save bool plugin inputs
        if plg.show_stderr is not None and str(plg.show_stderr.value).capitalize() == 'True':
            nested_plugins['show_stderr'] = True
        if plg.show_stdout is not None and str(plg.show_stdout.value).capitalize() == 'True':
            nested_plugins['show_stdout'] = True
        if plg.plotfl_to_csv is not None and str(plg.plotfl_to_csv.value).capitalize() == 'True':
            nested_plugins['plotfl_to_csv'] = True

        watts_plugins[str(plg.id)] = nested_plugins

    return watts_plugins


def create_watts_params(variables):
    """Creates a dictionary for input parameters

    Parameters
    ----------
    variables
        User input variables

    Returns
    -------
    params
        Watts params for storing user input variables

    """
    params = watts.Parameters()
    params_id = []
    for it, param in enumerate(variables):
        param_id = str(param.id).strip('\"')
        if param.value is not None:
            if isfloat(str(param.value.value)):
                if param.unit is not None:
                    params[param_id] = Quantity(
                        float(str(param.value.value)), str(param.unit.value))
                else:
                    params[param_id] = float(str(param.value.value))
            else:
                params[param_id] = str(param.value.value)
        elif param.list is not None:
            params[param_id] = convert_to_list(param.list)
        elif param.func is not None:
            func = ''
            input_func = str(param.func.value).strip('\"').split()
            for n, val in enumerate(input_func):
                string = str(input_func[n])
                if string in params_id:
                    func += str(params[string])
                else:
                    func += string
            params[param_id] = eval(func)
        elif param.bool is not None:
            bool_str = str(param.bool.value).strip('\"')
            if bool_str.upper() == "TRUE":
                params[param_id] = True
            else:
                params[param_id] = False

        params_id.append(str(param.id))

    return (params)


def convert_to_list(wb_list):
    """Convert a Workbench list to Python list

    Parameters
    ----------
    wb_list
        Workbench list to convert

    Returns
    -------
    convert_list
        Converted Python list

    """
    convert_list = []
    for n, val in enumerate(wb_list.value):
        string = str(wb_list.value[n]).strip('\"')
        if isfloat(string):
            convert_list.append(float(string))
        else:
            convert_list.append(string)
    return (convert_list)


def get_last_value(watts_params, name_list):
    """Extract the value of the last index from the
    results created by WATTS plugins for iteration workflow

    Parameters
    ----------
    watts_params
        WATTS params
    name_list
        List of name of params to extract values

    Returns
    -------
    watts_params
        Updated WATTS params

    """
    for param_name in name_list:
        if isinstance(watts_params[param_name], (list, np.ndarray)):
            watts_params[param_name] = watts_params[param_name][-1]
    return (watts_params)


def isfloat(num):
    """Check whether entries of a list are numeric

    Parameters
    ----------
    num
        Entry of list

    Returns
    -------
    True
        If entry is numeric

    """
    try:
        float(num)
        return True
    except ValueError:
        return False


def run_workflow(watts_params, wf_level, plugin_ID, watts_plugins):
    """Run workflow

    Parameters
    ----------
    watts_params
        Watts params with stored user input parameters
    wf_level
        Level of workflow
    plugin_ID
        ID of plugin
    plugin
        Dictionary of plugin

    Returns
    -------
    app_result
        WATTS results

    """
    if wf_level.iteration is not None:
        watts_params, app_result_plugin_1, app_result_plugin_2 = run_iterate(
            watts_params,  watts_plugins, wf_level)

        # Combine the results from plugins 1 and 2 into a dictionary
        app_result = {'app_result_plugin_1': app_result_plugin_1,
                      'app_result_plugin_2': app_result_plugin_1}

        return (app_result, watts_params)

    elif wf_level.parametric is not None:
        watts_params, app_result = run_parametric(
            watts_params,  watts_plugins[plugin_ID], wf_level)

        return (app_result, watts_params)

    elif wf_level.optimization is not None:
        operation = wf_level.optimization
        ...
    else:
        watts_params, app_result = run_direct(
            watts_params, watts_plugins[plugin_ID])

        return (app_result, watts_params)


def run_direct(watts_params, plugin):
    """Run workflow

    Parameters
    ----------
    watts_params
        Watts params with stored user input parameters
    plugin
        Dictionary of plugin

    Returns
    -------
    watts_params
        Updated WATTS parameters
    app_result
        WATTS results

    """

    # Provide the environment variable that is the path
    # to the directory of the application. If environment
    # variable is not set, provide the path to the directory
    # instead.
    if plugin['exec_dir'] is not None:
        if plugin['exec_dir'] in os.environ:
            app_dir = Path(os.environ[plugin['exec_dir']])
        else:
            app_dir = Path(plugin['exec_dir'])

    if plugin['code'].upper() == 'MOOSE':
        if 'exec_name' not in plugin:
            raise RuntimeError(
                "Please specify executable name of the MOOSE application.")

        app_plugin = watts.PluginMOOSE(
            template_file=plugin['template'],
            executable=app_dir / plugin['exec_name'],
            extra_inputs=plugin['extra_inputs'],
            extra_template_inputs=plugin['extra_template_inputs'],
            show_stdout=plugin['show_stdout'],
            show_stderr=plugin['show_stderr'])

    elif plugin['code'].upper() == 'PYARC':
        app_plugin = watts.PluginPyARC(
            template_file=plugin['template'],
            extra_inputs=plugin['extra_inputs'],
            extra_template_inputs=plugin['extra_template_inputs'],
            show_stdout=plugin['show_stdout'],
            show_stderr=plugin['show_stderr'])

    elif plugin['code'].upper() == 'RELAP5':
        app_plugin = watts.PluginRELAP5(
            template_file=plugin['template'],
            extra_inputs=plugin['extra_inputs'],
            extra_template_inputs=plugin['extra_template_inputs'],
            plotfl_to_csv=plugin['plotfl_to_csv'],
            show_stdout=plugin['show_stdout'],
            show_stderr=plugin['show_stderr'])

    elif plugin['code'].upper() == 'SAS':
        app_plugin = watts.PluginSAS(
            template_file=plugin['template'],
            extra_inputs=plugin['extra_inputs'],
            extra_template_inputs=plugin['extra_template_inputs'],
            show_stdout=plugin['show_stdout'],
            show_stderr=plugin['show_stderr'])

        if 'conv_channel' in plugin:
            app_plugin.conv_channel = Path(plugin['conv_channel'])
        if 'conv_primar4' in plugin:
            app_plugin.conv_primar4 = Path(plugin['conv_primar4'])

    elif plugin['code'].upper() == 'SERPENT':
        app_plugin = watts.PluginSerpent(
            template_file=plugin['template'],
            extra_inputs=plugin['extra_inputs'],
            extra_template_inputs=plugin['extra_template_inputs'],
            show_stdout=plugin['show_stdout'],
            show_stderr=plugin['show_stderr'])

    elif plugin['code'].upper() == 'DAKOTA':
        app_plugin = watts.PluginDakota(
            template_file=plugin['template'],
            extra_inputs=plugin['extra_inputs'],
            extra_template_inputs=plugin['extra_template_inputs'],
            auto_link_files=plugin['auto_link_files'],
            show_stdout=plugin['show_stdout'],
            show_stderr=plugin['show_stderr'])

    elif plugin['code'].upper() == 'ABCE':
        app_plugin = watts.PluginABCE(
            template_file=plugin['template'],
            extra_inputs=plugin['extra_inputs'],
            extra_template_inputs=plugin['extra_template_inputs'],
            show_stdout=plugin['show_stdout'],
            show_stderr=plugin['show_stderr'])

    elif plugin['code'].upper() == 'MCNP':
        app_plugin = watts.PluginMCNP(
            template_file=plugin['template'],
            extra_inputs=plugin['extra_inputs'],
            extra_template_inputs=plugin['extra_template_inputs'],
            show_stdout=plugin['show_stdout'],
            show_stderr=plugin['show_stderr'])

    elif plugin['code'].upper() == 'OPENMC':
        sys.path.insert(0, os.getcwd())
        from openmc_template import build_openmc_model

        app_plugin = watts.PluginOpenMC(
            model_builder=build_openmc_model,
            extra_inputs=plugin['extra_inputs'],
            show_stdout=plugin['show_stdout'],
            show_stderr=plugin['show_stderr'])  # show only error

    else:
        raise RuntimeError("Please provide the correct application name.")

    # Set 'extra_args' if available
    if 'extra_args' in plugin:
        app_plugin(watts_params, extra_args=plugin['extra_args'])

    # Run plugins and save to app_result
    app_result = app_plugin(watts_params)

    # Store output data from app_result to watts_params
    # Special treatment for OpenMC
    if plugin['code'].upper() == 'OPENMC':
       # Save keff results
        if hasattr(app_result, 'keff'):
            watts_params['keff'] = app_result.keff

        # Save tally results
        if 'scores' in plugin:
            for n_score, score in enumerate(plugin['scores']):
                tallies = app_result.tallies[0].get_values(
                    scores=[score]).ravel()
                for i, result in enumerate(tallies):
                    if 'score_names' in plugin:
                        watts_params[f"{plugin['score_names'][n_score]}_{i}"] = result
                    else:
                        watts_params[f"{score}_{i}"] = result
    else:
        if hasattr(app_result, 'csv_data'):
            for key in app_result.csv_data:
                watts_params[key] = app_result.csv_data[key]
        elif hasattr(app_result, 'output_data'):
            for key in app_result.output_data:
                watts_params[key] = app_result.output_data[key]
        elif hasattr(app_result, 'results_data'):
            for key in app_result.results_data:
                watts_params[key] = app_result.results_data[key]
        else:
            for key in app_result:
                watts_params[key] = app_result[key]

    return (watts_params, app_result)


def run_iterate(watts_params, plugin, wf_level):
    """Run workflow

    Parameters
    ----------
    watts_params
        Watts params with stored user input parameters
    plugin
        Dictionary of plugin
    wf_level
        Level of workflow

    Returns
    -------
    watts_params
        Updated WATTS parameters
    app_result
        WATTS results

    """
    operation = wf_level.iteration
    plugin_1 = str(operation.plugin_main.value).strip('\"')
    plugin_2 = str(operation.plugin_sub.value).strip('\"')
    nmax = float(str(operation.nmax.value))
    tolerance = float(str(operation.convergence_criteria.value))
    convergence_params = str(operation.convergence_params.value).strip('\"')
    to_sub_params = convert_to_list(operation.to_sub_params)
    to_main_params = convert_to_list(operation.to_main_params)

    convergence_list = []
    conv = True
    while conv:

        # Run the main plugin
        watts_params, app_result_plugin_1 = run_direct(
            watts_params, watts_plugins[plugin_1])

        # Extract the values of the last index of the iterating
        # parameters. This step is necessary because the results
        # created by WATTS plugins could be list or ndarray with
        # multiple values (especially for MOOSE based app).
        watts_params = get_last_value(watts_params, to_sub_params)

        # Run the sub plugin
        watts_params, app_result_plugin_2 = run_direct(
            watts_params, watts_plugins[plugin_2])

        # Extract the values of the last index of the iterating
        # parameters. This step is necessary because the results
        # created by WATTS plugins could be list or ndarray with
        # multiple values (especially for MOOSE based app).
        watts_params = get_last_value(watts_params, to_main_params)

        convergence_list.append(watts_params[convergence_params])

        if len(convergence_list) > 1 and ((convergence_list[-1] - convergence_list[-2])/convergence_list[-1]) < tolerance:
            conv = False
            if len(convergence_list) > nmax:
                conv = False

    watts_params["convergence_list"] = convergence_list

    return (watts_params, app_result_plugin_1, app_result_plugin_2)


def run_parametric(watts_params, plugin, wf_level):
    """Run workflow

    Parameters
    ----------
    watts_params
        Watts params with stored user input parameters
    plugin
        Dictionary of plugin
    wf_level
        Level of workflow

    Returns
    -------
    watts_params
        Updated WATTS parameters
    app_result
        WATTS results

    """
    operation = wf_level.parametric
    parametric_name = str(operation.changing_params.value).strip('\"')
    parametric_list = []
    app_result = {}
    for n, val in enumerate(operation.changing_values.value):
        watts_params[parametric_name] = float(str(val))
        parametric_list.append(float(str(val)))

        watts_params, app_result_parametric = run_direct(
            watts_params, watts_plugins[plugin_ID])
        # Store the results from each individual run to
        # the 'app_result' dictionary as individual tuple.
        app_result[f"run_{n}"] = app_result_parametric

    watts_params[f"{parametric_name}_list"] = parametric_list
    return (watts_params, app_result)


# Need to update and get properly from workbench the executable path and the argument
watts_path = "/Users/zhieejhiaooi/Documents/ANL/watts-devel/watts/src/watts_ui/"
opts, args = getopt.getopt(sys.argv[1:], "hi:o:", ["ifile=", "ofile="])
for opt, arg in opts:
    if opt == "-i":
        input_path = os.getcwd() + "/" + str(arg)

# Load Watts workbench
watts_wb = load_obj(input_path, watts_path).watts

# Change the working directory to the directory where
# the extra input files are stored. This is necessary
# due to how WATTS copies extra input files to the
# temporary working directory.
if watts_wb.workflow_dir is not None:
    os.chdir(str(watts_wb.workflow_dir.value).strip('\"'))

# Load plugins
if watts_wb.plugins is not None:
    watts_plugins = create_plugins(watts_wb.plugins)

# Start workflow
if watts_wb.workflow_level1 is not None:

    print("Executing Workflow Level 1")

    wf_level = watts_wb.workflow_level1

    plugin_ID = None
    if wf_level.plugin is not None:
        plugin_ID = str(wf_level.plugin.value)

    if wf_level.variables is not None:
        variables = wf_level.variables.param

        # Create WATTS params to store user input variables
        watts_params = create_watts_params(variables)
        watts_params.show_summary(show_metadata=False, sort_by='key')

        # Run workflow
        app_result, watts_params = run_workflow(
            watts_params, wf_level, plugin_ID, watts_plugins)

        watts_params.show_summary(show_metadata=False, sort_by='key')
