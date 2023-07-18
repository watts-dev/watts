.. _usage:

Detailed Usage
--------------

WATTS consists of a set of Python classes that can manage simulation workflows
for one or multiple codes. It provides the following capabilities:

- An isolated execution environment when running a code;
- The ability to use placeholder values in input files that are filled in
  programmatically;
- Seamless :ref:`unit conversions <units>` when working with multiple codes;
- A managed database that simulation inputs and outputs are automatically saved
  to; and
- Python classes that provide extra post-processing and analysis capabilities
  for each code.

Parameters
++++++++++

The parameters that are used to "fill in" input files with placeholders are
managed by the :class:`~watts.Parameters` class. This class mostly behaves like
a Python dictionary but has a few extra capabilities. Setting parameters can be
done as follows::

    params = watts.Parameters()
    params['temperature'] = 550.0
    params['option'] = True
    params['values'] = [10.0, 20.0, 0.05]

Like a Python dictionary, key/value pairs can also be set when instantiating the
object::

    params = watts.Parameters(
        temperature=550.0,
        option=True,
        values=[10.0, 20.0, 0.05]
    )

Parameters can be saved to a pickle file::

    params.save('parameters.pkl')

and later re-created using the :meth:`~watts.Parameters.from_pickle` method::

    loaded_params = watts.Parameters.from_pickle('parameters.pkl')

By themselves, :class:`~watts.Parameters` are not very useful, but when
combined with plugin classes, they become building blocks for sophisticated
workflows.

.. _units:

Units
~~~~~

To handle codes that use different unit systems, WATTS relies on the
:class:`~astropy.units.Quantity` class from :mod:`astropy.units` to perform unit
conversion on parameters to ensure that the correct units are used for each
code. For instance, MOOSE-based codes use the SI units while OpenMC uses the CGS
units. With the built-in unit-conversion capability, a parameter needs only to
be set once in any unit system and WATTS can automatically convert it to the
correct unit for different codes. To use the unit-conversion capability,
parameters need to be set using the :class:`~astropy.units.Quantity` class as
follows::

    from astropy.units import Quantity

    params['radius'] = Quantity(9.9, "mm")
    params['inlet_temperature'] = Quantity(600, "Celsius")
    params['c_p'] = Quantity(4.9184126, "BTU/(kg*K)")

with the format of ``Quantity(value, unit)``.

Plugins
+++++++

Using a particular code within WATTS requires a "plugin" that controls input
file generation, execution, and post-processing. To see a full list of available
plugins, refer to :ref:`plugins`. Below, the general functionality of the plugin
classes is discussed and applies to nearly all classes.

Execution
~~~~~~~~~

Running a code via :mod:`watts` is as simple as creating an instance of a plugin
class and then calling that instance as though it were a function. Here, we will
show an example using the :class:`~watts.PluginMCNP` class that demonstrates a
simulation using MCNP. Let's say we have the following input file for MCNP that
we want to run:

.. code-block:: text

    Bare sphere of plutonium
    1    1    0.04 -1  imp:n=1
    2    0          1  imp:n=0

    1    so   6.5

    m1   94239.70c 0.04
    kcode 10000 1.0 50 150
    ksrc 0 0 0

If the filename of the input file is ``sphere_model``, we start by creating a
:class:`watts.PluginMCNP` object::

    plugin_mcnp = watts.PluginMCNP("sphere_model")

Calling the plugin class then executes the code::

    result = plugin_mcnp()

When you call a plugin, it will return an instance of a subclass of
:class:`~watts.Results` (see :ref:`results` for further details).

Note that when a plugin is called, a temporary directory with all necessary
files is created and used while the underlying code is running. Once the call is
complete, the input and output files are moved to the :ref:`database
<usage_database>` and the temporary directory is removed. To retain the
temporary directory for debugging purposes, the ``cleanup`` argument can be
used::

    result = plugin_mcnp(cleanup=False)

.. _usage_templates:

Templated Inputs
~~~~~~~~~~~~~~~~

For any code that use text-based input files, :mod:`watts` relies on the `Jinja
<https://jinja.palletsprojects.com>`_ templating engine for handling templated
variables and expressions. The templated input file looks like a normal input
file where some values have been replaced with **variables**, which are denoted
by ``{{`` and ``}}`` pairs and get replaced with actual values when the template
is *rendered*. For example, the example MCNP input file above could be templated
as follows:

.. code-block:: text

    Bare sphere of plutonium
    1    1    0.04 -1  imp:n=1
    2    0          1  imp:n=0

    1    so   {{ radius }}

    m1   94239.70c 0.04
    kcode 10000 1.0 50 150
    ksrc 0 0 0

The input file now contains a placeholder, ``{{ radius }}``, that will be filled
in at the time the plugin is called. Before creating and calling our plugin, we
need to specify the parameter using the :class:`~watts.Parameters` class::

    params = watts.Parameters()
    params['radius'] = 6.0

As before, we create an instance of :class:`~watts.PluginMCNP` but instead of
calling it with no arguments, we pass it the :class:`~watts.Parameters`
instance::

    plugin_mcnp = watts.PluginMCNP("sphere_model")
    result = plugin_mcnp(params)

While this example solely demonstrates a simple variable substitution, Jinja has
sophisticated capabilities for using logical control structures, filters,
calling Python methods, and extensible templates; for advanced usage, please
read through the Jinja `template designer documentation
<https://jinja.palletsprojects.com/en/3.0.x/templates/>`_.

Specifying an Executable
~~~~~~~~~~~~~~~~~~~~~~~~

Each plugin has a default executable name for the underlying code. For example,
the :class:`~watts.PluginMCNP` class uses the executable ``mcnp6`` by default.
You can explicitly specify the path to an executable at the time a plugin is
created::

    mcnp = watts.PluginMCNP(template, executable='mcnp5')

The ``executable`` argument can be given as an absolute path, in which case it
will be used as is. Alternatively, when the ``executable`` argument is given as
a relative path, WATTS will look for an environment variable indicating the
directory where the executable can be found and prepend that to the executable
if it exists. For example, the :class:`~watts.PluginMCNP` class will look for a
:envvar:`MCNP_DIR` environment variable. If no environment variable is found,
the directory containing the executable must be present on your :envvar:`PATH`
environment variable.

You can also view and change the executable using the
:class:`~watts.PluginGeneric.executable` attribute:

.. code-block:: pycon

    >>> plugin_mcnp.executable
    PosixPath('mcnp6')
    >>> plugin_mcnp.executable = 'mcnp5'

.. _input_files:

Specifying Input Files
~~~~~~~~~~~~~~~~~~~~~~

The above example with MCNP uses only a single input file. However, some codes
require more than one input file, some of which may be templated. When you're
creating a plugin, the ``extra_inputs`` argument allows you to specify a list of
files that will be copied to the isolated executable environment::

    arc = watts.PluginPyARC('pyarc_template', extra_inputs=['lumped_test5.son'])

If you have extra input files that also contain template variables that need to
get rendered, use the ``extra_template_inputs`` argument instead::

    arc = watts.PluginPyARC('pyarc_template', extra_template_inputs=['extra_template'])

Configuring the Execution Command
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each plugin has a predefined execute command that will be run when the plugin is
called. For example, for the :class:`~watts.PluginSerpent` class, the execute
command can be determined as:

.. code-block:: pycon

    >>> plugin_serpent = watts.PluginSerpent('input')
    >>> plugin_serpent.execute_command
    ['sss2', 'serpent_input']

If you want to specify extra command-line arguments, this can be done with the
``extra_args`` argument, which accepts a list of strings, at the time you are
calling the plugin. If we wanted to run Serpent with 24 threads, for example,
this could be accomplished as::

    result = plugin_serpent(params, extra_args=['-omp', '24'])

The ``extra_args`` are added *after* the main execute command. If you need to
prepend arguments (most commonly to run a code using MPI), you can specify the
``mpi_args`` argument at the time you call the plugin::

    result = plugin_serpent(params, mpi_args=['mpiexec', '-n', '8'])

Standard Output
~~~~~~~~~~~~~~~

When you call a plugin, by default you will *not* see output from the code being
run under the hood. The output is redirected to a file which is available to you
afterward via the :attr:`~watts.Results.stdout` attribute. If you do want to see
output from the execution of a code as it's running, you can use the
``show_stdout`` argument at the time you are creating the plugin::

    plugin_sas = watts.PluginSAS('sas_input', show_stdout=True)

There's also a ``show_stderr`` argument that modifies behavior for anything
written to standard error.

.. _results:

Results
+++++++

When you call a :meth:`~watts.Plugin` instance, an instance of the
:class:`~watts.Results` class specific to the plugin will be returned that
contains information about the results. Every :class:`~watts.Results` object
contains a list of input and output files that were generated:

.. code-block:: pycon

    >>> results = plugin_openmc(params)
    >>> results.inputs
    [PosixPath('geometry.xml'),
     PosixPath('settings.xml'),
     PosicPath('materials.xmll')]

    >>> results.outputs
    [PosixPath('OpenMC_log.txt'),
     PosixPath('statepoint.250.h5')]

:class:`~watts.Results` objects also contain a copy of the
:class:`~watts.Parameters` that were used at the time the plugin was called:

.. code-block:: pycon

    >>> results.parameters
    {'radius': 10.0}

Each plugin actually returns a subclass of :class:`~watts.Results` that extends
the basic functionality by adding methods/attributes that incorporate
post-processing logic. For example, the :class:`~watts.ResultsOpenMC` class
provides a :attr:`~watts.ResultsOpenMC.keff` attribute that provides the
k-effective value at the end of the simulation:

.. code-block:: pycon

    >>> results.keff
    1.0026170700986219+/-0.003342785895893627

For MOOSE, the :class:`~watts.ResultsMOOSE` class provides a
:attr:`~watts.ResultsMOOSE.csv_data` attribute that gathers the results from
every CSV files generated by MOOSE applications (such as SAM or BISON)::

    moose_result = moose_plugin(params)
    for key in moose_result.csv_data:
        print(key, moose_result.csv_data[key])


For PyARC, the :class:`~watts.ResultsPyARC` class
provides a :attr:`~watts.ResultsPyARC.results_data` attribute that gathers the
results stored in `PyARC.user_object`::

    pyarc_result = pyarc_plugin(params)
    for key in pyarc_result.results_data:
        print(key, pyarc_result.results_data[key])

.. _usage_database:

Database
++++++++

When you call a :class:`~watts.Plugin` instance, the :class:`~watts.Results`
object and all accompanying files are automatically added to a database on disk
for later retrieval. Interacting with this database can be done either via the
:class:`~watts.Database` class or through the ``watts`` command-line tool.

The Database class
~~~~~~~~~~~~~~~~~~

The :class:`~watts.Database` class provides a list-like object that contains all
previously generated :class:`~watts.Results` objects:

.. code-block:: pycon

    >>> db = watts.Database()
    >>> db
    [<ResultsOpenMC: 2022-01-01 12:05:02.130384>,
     <ResultsOpenMC: 2022-01-01 12:11:38.037813>,
     <ResultsMOOSE: 2022-01-02 08:45:12.846409>]
    >>> db[1]
    <ResultsOpenMC: 2022-01-01 12:11:38.037813>

By default, the database will be created in a user-specific data directory (on
Linux machines, this is normally within ``~/.local/share``). However, the
location of the database can be specified::

    db = watts.Database('/opt/watts_db/')

Creating a database this way doesn't change the default path used when running
plugins. If you want to change the default database path used in plugins, the
:meth:`~watts.Database.set_default_path` classmethod should be used::

    >>> watts.Database.set_default_path('/opt/watts_db')
    >>> db = watts.Database()
    >>> db.path
    PosixPath('/opt/watts_db')

To remove a result from the database, you can call the
:meth:`~watts.Database.remove` method, passing a :class:`watts.Results` object::

    >>> db = watts.Database()
    >>> db
    [<ResultsOpenMC: 2022-01-01 12:05:02.130384>,
     <ResultsOpenMC: 2022-01-01 12:11:38.037813>,
     <ResultsMOOSE: 2022-01-02 08:45:12.846409>]
    >>> moose_result = db[-1]
    >>> db.remove(moose_result)
    >>> db
    [<ResultsOpenMC: 2022-01-01 12:05:02.130384>,
     <ResultsOpenMC: 2022-01-01 12:11:38.037813>]

Note that removing a database result will delete the data directory associated
with the result but will not affect the input files stored in their original
location on your system. To clear all results from the database, simply use the
:meth:`~watts.Database.clear` method:

.. code-block::

    >>> db.clear()
    >>> db
    []

As with the :meth:`~watts.Database.remove` method, clearing the database will
delete all the corresponding results on disk, including copies of the input and
output files from the workflow stored in the data directory. Original input
files stored outside the database directory will be unaffected.

Directory names
~~~~~~~~~~~~~~~

Within the database, each result is stored in a uniquely named directory. By
default, the directory name is generated using Python's :mod:`uuid` module.
However, you can manually specify the directory name when a plugin is executed
by passing the ``output_dir`` argument::

    >>> result = plugin(params, output_dir='iteration_5')
    >>> result.base_path
    PosixPath('/home/username/.local/share/watts/iteration_5')

Note that if you try to use the same ``output_dir`` twice, an exception will be
raised.

Command-line Tool
~~~~~~~~~~~~~~~~~

The ``watts`` command-line tool provides an easy way to inspect results stored
in the database. This tool has three subcommands:

results
    Displays a list of all results in the database
dir
    Provides the directory for a specific result (referenced by index)
stdout
    Shows the standard output from a specific result (referenced by index)
rm
    Remove a specific result (referenced by index)

The ``results`` subcommand will produce a table such as the following:

.. code-block:: console

    $ watts results
    +-------+--------+--------+--------+----------------------------+
    | Index | Job ID | Plugin | Name   | Time                       |
    +-------+--------+--------+--------+----------------------------+
    | 0     | 0      | MCNP   |        | 2022-06-01 13:21:44.713942 |
    | 1     | 1      | MCNP   |        | 2022-06-01 13:23:12.410774 |
    | 2     | 2      | MCNP   | r=2.0  | 2022-06-02 07:46:05.463723 |
    | 3     | 2      | MCNP   | r=4.0  | 2022-06-02 07:46:10.996932 |
    | 4     | 2      | MCNP   | r=6.0  | 2022-06-02 07:46:17.487411 |
    | 5     | 2      | MCNP   | r=8.0  | 2022-06-02 07:46:24.964455 |
    | 6     | 2      | MCNP   | r=10.0 | 2022-06-02 07:46:33.426781 |
    +-------+--------+--------+--------+----------------------------+

For each result, you're given an index (used in other subcommands), a job ID,
the plugin name, the ``name`` that was used when calling the plugin, and a
timestamp for when the plugin was called. The job ID is the same for each plugin
execution from a single Python invocation. There are several optional flags that
can be used to narrow down the list of results. For example, to only display
results that have job ID 2:

.. code-block:: console

    $ watts results --job-id 2
    +-------+--------+--------+--------+----------------------------+
    | Index | Job ID | Plugin | Name   | Time                       |
    +-------+--------+--------+--------+----------------------------+
    | 2     | 2      | MCNP   | r=2.0  | 2022-06-02 07:46:05.463723 |
    | 3     | 2      | MCNP   | r=4.0  | 2022-06-02 07:46:10.996932 |
    | 4     | 2      | MCNP   | r=6.0  | 2022-06-02 07:46:17.487411 |
    | 5     | 2      | MCNP   | r=8.0  | 2022-06-02 07:46:24.964455 |
    | 6     | 2      | MCNP   | r=10.0 | 2022-06-02 07:46:33.426781 |
    +-------+--------+--------+--------+----------------------------+

The index of a result can be used to get more information. For example, to
determine the directory where input/output files are stored for the result with
index 2, you can run:

.. code-block:: console

    $ watts dir 2
    /home/username/.local/share/watts/3c5674ae37094d74af7a7fc5562555a3

Similarly, a result can be removed by referencing its index:

.. code-block:: console

    $ watts rm 5

As with the :meth:`watts.Database.remove` method, the ``watts rm`` subcommand
will delete the data directory associated with the result.
