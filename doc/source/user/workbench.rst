.. _workbench:

Setup WATTS in NEAMS Workbench Environment
------------------------------------------

The `NEAMS Workbench <https://www.ornl.gov/onramp/neams-workbench>` is a tool
that facilitates the use of multiple tools in analysis
by providing a commom user interface for model creation, review, execution, output,
and visualization for integrated codes. Instructions on how to download and install
Workbench can be found on the Workbench
`Gitlab repository <https://code.ornl.gov/neams-workbench/downloads>`.

To set up WATTS in the Workbench environment, you first need to first provide the path to
where Workbench is installed in `workbench.sh` under the `scripts` directory. You can
then run `setup_conda_wb.sh` under the same directory to set up WATTS within
the Workbench environment.

Optional: To install OpenMC in the Workbench environemnt, run `setup_openmc.sh`.

To finish setting up WATTS, open Workbench and go to the `File` tab at the top-left corner
then select `Configurations` from the drop menu. In the `Application configurations`
window, click `Add` on the top most row then select `Watts` from the pop-up window.
In the list of `Application Options`, input the path of `watts_ui.py` to `Executable`.
The file should exist by default in `/watts/src/watt_ui/`. Next, click `Load Grammar`.
Click `OK` to complete the setup.

Optional: Environment variables can be added be added under `Run Environment`.

WATTS Workbench Input File
++++++++++++++++++++++++++

To create a new WATTS input file in Workbench, go to `File`, select `New File`,
and select `WATTS files (*.son)` from the drop down menu. An existing `*.son`
file can also be dragged and dropped to the Workbench window.

The WATTS input file utilizes a hierarchical block-based system where a block
is defined with opening and closing curly braces `{ }`. A `watts` block is first
created within which other blocks and variables can be defined.

Plugins
~~~~~~~

The `plugins` block is required. Within the `plugins` blocks are
`plugin` sub-blocks where WATTS plugins are defined.

.. code-block:: text
    plugins{
        plugin(ID1){
            code = moose
            template = "sam_template"
            exec_dir = SAM_DIR
            exec_name = "sam-opt"
            extra_inputs=["file1", "file2", "file3"]
            extra_template_inputs=["template1", "template2", "template3"]
            show_stderr = False
            show_stdout = False
        }

        plugin(ID2){
            code = PyARC
            template = "pyarc_template"
            executable = "path/to/pyarc/executable"
            show_stderr = False
            show_stdout = False
        }
    }

Multiple `plugin` sub-blocks can be defined within the `plugins` block where
each plugin is given a unique identity, as represented by `(ID1)` and `(ID2)`
in the snippet above. For each sub-block the basic inputs are::

     `code` : Name of the application
     `template` : Name of the template file
     `show_stderr` : Option to display error
     `show_stdout` : Option to display output
     `exec_dir` : Environment variable that points to the directory in which the application's executable is stored
     `extra_inputs` : Additional non-templated input files
     `extra_template_inputs` : Additional tempalted input files
     `exec_name` : Name of the executable
     `executable` : Path to the executable

Note that user must provide either BOTH `exec_dir` and `exec_name` or
ONLY `executable`. Additionally, there are  application-specific inputs
that can be provided to the plugins such as::

    `extra_args` (multiple apps) : Extra arguments to applications
    'transfer_params' (multiple apps) : Output to transfer between applications for multi-apps run
    `plotfl_to_csv` (RELAP5) : Option to convert `plotfl` file to `csv` file
    `conv_channel` (SAS) : Path to `CHANNELtoCSV.x`
    `conv_primar4` (SAS) : Path to `PRIMAR4toCSV.x`
    `auto_link_files` (Dakota) : List of files for Dakota to link automatically
    `scores` (OpenMC) : List of filters for tallies
    `score_names` (OpenMC) : List of user-given names for tally filters

Currently all applications/codes already integrated to WATTS can be run on Workbench, these include
PyARC, OpenMC, SERPENT, ABCE, MCNP, MOOSE, SAS, Dakota, Serpent, and RELAP5.

For OpenMC, multiple `scores` can be provided at once. If provided, the number of `score_names` must be the
same as the number of `scores`. For instance, ::

    scores = ["elastic", "nu-fission"]
    score_names = ["total_elastic_scatter_rate", "total_fission_neutron_prod"]

and there are N tallies where N > 1, then the outputs of the run will be named as::

    total_elastic_scatter_rate_1, total_elastic_scatter_rate_2, ..., total_elastic_scatter_rate_N
    total_fission_neutron_prod_1, total_fission_neutron_prod_2, ..., total_fission_neutron_prod_N

If `score_names` is not provided, `scores` will be used as the base name for the outputs.

Workflow level
~~~~~~~~~~~~~~

The `workflow_level1` block is required. The plugin to be used is specified
by the `plugin` keyword::

    plugin = ID1

where 'ID1' is the ID of the plugin provided in the `plugins` block. When performing
a multi-app run where more than one plugins are used, the sequence of the run is
determined by the order of plugins. For example, when the order of the plugins is::

    plugin = ID1
    plugin = ID2

Workbench will run ID1 first then ID2. On the other than, when the order is ::

    plugin = ID2
    plugin = ID1

Workbench will instead run ID1 first then ID2.

The`variable` sub-block is where the values of the templated variables are
specified, as shown below::

    variables{
        param(T_inlet) {value = 873.15}
        param(T_outlet) {value = 1000.15}
        param(flow_area) {value = 3.14e-4}
        param(component_name) {value = pipe1}
        param(Dh) {value = 1 unit = m}
        param(location) {list = [top bottom left right]}
        param(length) {list = [3.0 5.0 7.0 10.0]}
        param(T_mean) {func = "0.5 * ( T_inlet + T_outlet )"}
        param(wall_bc) {bool = "True"}
    }

Each `param` has a unique ID represented by the string in the parantheses
shown in the snippet above. A `param` can accept different types of inputs
depending on the provided key word provided. The `value` keyword is used
for when a numeric or a string is provided. A `unit` keyword can be added
if a user intends to utilize WATTS' internal unit-conversion capability.
The `list` keyword is used for a list of numerics or strings. The `bool`
keyword is used for booleans. The `func` keyword is used when a user
intends to perform arithmetic with existing `param`. Note that each elemet
in `func` must be separated by a space.

Execution
+++++++++

Three types of executions can be performed by WATTS on Workbench, namely
direct execution, parametric study, and Picard iteration.

Direct execution
~~~~~~~~~~~~~~~~

Direct execution is the simplest execution type. The user only needs to
provide `workflow_dir`, `plugins` block, and `workflow_level1` block to
perform direct execution.

Parametric study
~~~~~~~~~~~~~~~~

To perform parametric study, a `parametric` block needs to be added to
the `workflow_level1` block as follows::

    workflow_level1{
        plugin = ID1
        variables{
            param(He_inlet_temp) {value = 873.15}
            param(He_outlet_temp) {value = 1023.15}
            ...
        }
        parametric{
        changing_params = "heat_source"
        changing_values = [0, 1e5, 2e5, 3e5]
        }
    }

where `changing_params` is the parameter whose values are varied and
`changing_values` is a list of intended varied values.

Picard iteration
~~~~~~~~~~~~~~~~

To perform Picard iteration, the `iteration` block needs to be added
to the `workflow_level1` block::

    workflow_level1{
        plugin = ID1
        variables{
            param(He_inlet_temp) {value = 873.15}
            param(He_outlet_temp) {value = 1023.15}
            ...
        }
        iteration{
            plugin = ID2
            nmax = 10
            convergence_params = "keff"
            convergence_criteria = 0.0001
            to_sub_params = ["avg_Tf_1" "avg_Tf_2" "avg_Tf_3" "avg_Tf_4" "avg_Tf_5"]
            to_main_params = ["Init_P_1" "Init_P_2" "Init_P_3" "Init_P_4" "Init_P_5"]
        }
    }

`plugin` in the `iteration` block is the plugin ID (ID2 in this example) of the
application that will be used along with the the first plugin (ID1 in this example)
to perform iteration. `nmax` is the maximum number of iterations,
`convergence_params` is the parameter used for evaluating convergence,
`convergence_criteria` is the tolerance for
convergence, `to_sub_params` and `to_main_params` are lists of parameters whose
values are iterated between the two applications where they each must have at least
one parameter. Note that the parameter supplied to `convergence_params` must be
an output from the second plugin. For instance, in the above example, "keff" is
an output produced by the plugin of "ID2". Note that the choice of "keff" in
this example is arbitrary and `convergence_params` should be chosen according to
the applications used and the objective of iteration runs.
