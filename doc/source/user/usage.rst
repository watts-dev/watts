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

Most native Python datatypes (:class:`int`, :class:`float`, :class:`bool`,
:class:`str`, :class:`list`, :class:`set`, :class:`tuple`, :class:`dict`) are
supported along with :class:`NumPy arrays <numpy.ndarray>` as well. Parameters
can be saved to a pickle file::

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
You can both view and/or change the executable using the
:class:`~watts.TemplatePlugin.executable` attribute:

.. code-block:: pycon

    >>> plugin_mcnp.executable
    PosixPath('mcnp6')
    >>> plugin_mcnp.executable = 'mcnp5'

If the ``executable`` you specify is not an absolute path, the directory
containing it must be present on your :envvar:`PATH` environment variable.

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

Database
++++++++

When you call a :class:`~watts.Plugin` instance, the :class:`~watts.Results`
object and all accompanying files are automatically added to a database on disk
for later retrieval. Interacting with this database can be done via the
:class:`~watts.Database` class:

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

To clear results from the database, simply use the
:meth:`~watts.Database.clear` method:

.. code-block::

    >>> db.clear()
    >>> db
    []

Be aware that clearing the database **will** delete all the corresponding
results on disk, including input and output files from the workflow.
