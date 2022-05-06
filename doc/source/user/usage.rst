.. _usage:

Basic Usage
-----------

WATTS consists of a set of Python classes that can manage simulation
workflows for multiple codes where information is exchanged at a coarse level.
For each code, input files rely on placeholder values that are filled in
based on a set of user-defined parameters.

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
file generation, execution, and post-processing. Three plugin classes,
:class:`~watts.PluginMOOSE`, :class:`~watts.PluginOpenMC`, and
:class:`~watts.PluginPyARC`, have already been added to WATTS and are available
for your use.

MOOSE Plugin
~~~~~~~~~~~~

The :class:`~watts.PluginMOOSE` class enables MOOSE simulations using a
templated input file. This is demonstrated here for a SAM application, but other
examples based on BISON are also available. For MOOSE codes such as SAM or BISON
that use text-based input files, WATTS relies on the `Jinja
<https://jinja.palletsprojects.com>`_ templating engine for handling templated
variables and expressions. The templated input file looks like a normal MOOSE
input file where some values have been replaced with **variables**, which are
denoted by ``{{`` and ``}}`` pairs and get replaced with actual values when the
template is *rendered*. For example, a templated input file might look as
follows:

.. code-block:: jinja

    [GlobalParams]
        global_init_P = {{ He_Pressure }}
        global_init_V = {{ He_velocity }}
        global_init_T = {{ He_inlet_temp }}
        gravity = '-9.8 0 0'
        scaling_factor_var = '1 1e-3 1e-6'
        Tsolid_sf = 1e-3
    []

If the templated input file is ``sam_template.inp``, the SAM code will rely on
the general MOOSE plugin that can be created as::

    moose_plugin = watts.PluginMOOSE('sam_template.inp')

The MOOSE plugin provides the option to specify non-templated input files (in
`extra_inputs` option) that will be copied together with the templated input
file (mesh or cross-section files).

The SAM executable defaults to ``sam-opt`` (assumed to be present on your
:envvar:`PATH`) but can also be specified explicitly with the
:attr:`~watts.PluginMOOSE.moose_exec` attribute::

    moose_plugin.moose_exec = "/path/to/sam-opt"

To execute SAM, the :class:`~watts.PluginMOOSE` instance is called as a function
and expects to receive an instance of :class:`~watts.Parameters`. For the above
template, the :class:`~watts.Parameters` instance should have ``He_Pressure``,
``He_velocity``, and ``He_inlet_temp`` parameters present. Thus, executing SAM
with this templated input file along with corresponding parameters might look as
follows::

    params = watts.Parameters()
    params['He_Pressure'] = 2.0
    params['He_velocity'] = 1.0
    params['He_inlet_temp'] = 600.0
    results = moose_plugin(params)

Calling the :class:`~watts.PluginMOOSE` instance will render the templated input
file (replace variables with values from the :class:`~watts.Parameters`
instance), execute SAM, and collect the output files.

If applicable, WATTS also allows users to use multiple input files for executing
MOOSE codes. This can be done by simply specifying the names of the extra input
files as a string to the "extra_template_inputs" argument when calling the
:class:`~watts.PluginMOOSE` class::

    moose_plugin = watts.PluginMOOSE('moose_template', show_stdout=True, extra_template_inputs=['extra_input_file_names'])

Beyond simple variable substitution, Jinja has sophisticated capabilities for
using logical control structures, filters, calling Python methods, and
extensible templates; for advanced usage, please read through the Jinja
`template designer documentation
<https://jinja.palletsprojects.com/en/3.0.x/templates/>`_.

OpenMC Plugin
~~~~~~~~~~~~~

The :class:`~watts.PluginOpenMC` class handles OpenMC execution in a similar
manner to the :class:`~watts.PluginMOOSE` class for MOOSE. However, for OpenMC,
inputs are generated programmatically through the OpenMC Python API. Instead of
writing a text template, for the OpenMC plugin you need to write a function that
accepts an instance of :class:`~watts.Parameters` and generates the necessary
XML files. For example::

    def godiva_model(params):
        model = openmc.Model()

        pu_metal = openmc.Material()
        pu_metal.set_density('sum')
        pu_metal.add_nuclide('Pu239', 3.7047e-02)
        pu_metal.add_nuclide('Pu240', 1.7512e-03)
        pu_metal.add_nuclide('Pu241', 1.1674e-04)
        pu_metal.add_element('Ga', 1.3752e-03)
        model.materials.append(pu_metal)

        sph = openmc.Sphere(r=params['radius'], boundary_type='vacuum')
        cell = openmc.Cell(fill=pu_metal, region=-sph)
        model.geometry = openmc.Geometry([cell])

        model.settings.batches = 50
        model.settings.inactive = 10
        model.settings.particles = 1000

        model.export_to_xml()

With this function, the :class:`~watts.PluginOpenMC` class can be
instantiated::

    openmc_plugin = watts.PluginOpenMC(godiva_model)

Note how the function object itself is passed to the plugin. When the
:meth:`~watts.PluginOpenMC` instance is called, the "template" function is
called and passed the user-specified :class:`~watts.Parameters`::

    params = watts.Parameters(radius=6.0)
    results = openmc_plugin(params)

This will generate the OpenMC input files using the template parameters, run
OpenMC, and collect the results. Note that any extra keyword arguments passed to
the plugin are forwarded to the :func:`openmc.run` function. For example::

    results = openmc_plugin(params, mpi_args=["mpiexec", "-n", "16"])

By default, the OpenMC plugin will only call the :func:`openmc.run` function,
but you can customize the execution by passing an arbitrary function as the
``function`` keyword argument. For example, if you wanted to additionally call
:func:`openmc.plot_geometry` each time the plugin is called, this could be
accomplished as follows::

    import openmc

    def run_function():
        openmc.plot_geometry()
        openmc.run()

    results = openmc_plugin(params, function=run_function)

PyARC Plugin
~~~~~~~~~~~~~

The :class:`~watts.PluginPyARC` class handles PyARC execution in a similar
manner to the :class:`~watts.PluginMOOSE` class for MOOSE. PyARC use text-based
input files which can be templated as follows:

.. code-block:: jinja

    surfaces{
        hexagon ( hex ){ orientation=y   normal = z  pitch = {{ assembly_pitch }} }
        plane ( z0 ) { z = 0.0  }
        plane ( z10 ) { z = {{ assembly_length }} }
    }

If the templated input file is `pyarc_template`, then the PyARC plugin can be
instantiated with following command line::

    pyarc_plugin = watts.PluginPyARC('pyarc_template', show_stdout=True, extra_inputs=['lumped_test5.son'])

The path to PyARC directory must be specified explicitly with the
:attr:`~watts.PluginPyARC.pyarc_exec` attribute::

    pyarc_plugin.pyarc_exec  = "/path/to/PyARC"

To execute PyARC, the :meth:`~watts.PluginPyARC` instance is called directly the
same way as other plugins.

If applicable, WATTS also allows users to use multiple input files for executing
PyARC. This can be done by simply specifying the names of the extra input
files as a string to the "extra_template_inputs" argument when calling the
:class:`~watts.PluginPyARC` class::

    pyarc_plugin = watts.PluginPyARC('pyarc_template', show_stdout=True, extra_template_inputs=['extra_input_file_names'])

SAS4A/SASSY-1 Plugin
~~~~~~~~~~~~~~~~~~~~

The :class:`~watts.PluginSAS` class handles SAS4A/SASSY-1 execution in a similar
manner to the :class:`~watts.PluginMOOSE` class for MOOSE. SAS4A/SASSY-1 uses text-based
input files which can be templated as follows:

.. code-block:: jinja

    47    1        {{ flow_per_pin }}
    3     1 {{ total_reactor_power }}
    7     1                {{ tmax }}

If the templated input file is `sas_template`, then the SAS4A/SASSY-1 plugin can be
instantiated with the following command line::

    sas_plugin = watts.PluginSAS('sas_template', show_stdout=True)

The SAS executable is OS-dependent. It defaults to ``sas.x`` (assumed to be
present on your :envvar:`PATH`) for Linux and macOS, and ``sas.exe`` for
Windows. However, the executable can also be specified explicitly with the
:attr:`~watts.PluginSAS.sas_exec` attribute::

    sas_plugin.sas_exec = "/path/to/sas-exec"

Furthermore, the paths to the SAS utilities that convert the ".dat" files to
".csv" files must be specified with the :attr:`~watts.PluginSAS.conv_channel`
and :attr:`~watts.PluginSAS.conv_primar4` attributes::

    sas_plugin.conv_channel  = "/path/to/CHANNELtoCSV.x"
    sas_plugin.conv_primar4  = "/path/to/PRIMAR4toCSV.x"

Similar to the SAS executable, the utilities are also OS dependent. To execute
SAS, the :meth:`~watts.PluginSAS` instance is called directly in the same way as
other plugins.

RELAP5-3D Plugin
~~~~~~~~~~~~~~~~~~~~

The :class:`~watts.PluginRELAP5` class handles execution of RELAP5-3D. Note that the
plugin is designed for the execution of RELAP5-3D v4.3.4 and thus may not be compatible
with other version of RELAP5-3D. RELAP5-3D uses text-based input files that can be
templated as follows:

.. code-block:: jinja

*                 Time         Power
20250001          -1.0         0.0
20250002           0.0      {{ heater_power_1 }}
20250003         1.0e3      {{ heater_power_2 }}

If the templated input file is `relap5_template`, then the RELAP5-3D plugin can be
instantiated with the following command line::

    relap5_plugin = watts.PluginRELAP5('relap5_template', show_stdout=True)

RELAP5-3D requires the executable, license key, and the input file to be in the same
directory to run. Thus, before running the RELAP5-3D plugin, user needs to specify the
directory that the executable and the license key are in (must be in the same directory).
This can be done by adding the ``RELAP5_DIR`` variable to the environment or by
explicitly specifying the path in the Python script as::

    relap5_plugin.relap5_dir = "\path\to\executable\and\license"

The RELAP5 executable is OS-dependent. It defaults to ``relap5.x`` (assumed to be
present on your :envvar:`PATH`) for Linux and macOS, and ``relap5.exe`` for
Windows.

The plugin also supports extra input options to RELAP5-3D. User simply needs to add the
extra options as a string to the ``extra_option`` argument when instantiating the plugin as follows::

    relap5_plugin = watts.PluginRELAP5('relap5_template',
                                        extra_options = ['-w', 'tpfh2o', '-e', 'tpfn2', '-tpfdir', 'location\of\fluid\property\files'])

Note that the fluid property files can be specified as extra input options, as shown above. Another
approach is simply put them in the same directory as the executable and license key before running the plugin.

For the postprocessing of RELAP5-3D results, the plugin converts the default "plotfl" plot file generated
by RELAP5-3D into a ".CSV" file. Card-104 must be specified as "ascii" in the RELAP5-3D input file as::

    104          ascii

to ensure that the "plotfl" is in ASCII format instead of the default binary format. As the conversion
process could be computationally expensive, user can turn it off by omitting Card-104 in the RELAP5-3D input
file and adding ``plotfl_to_csv=False`` when instantiating the plugin as follows::

    relap5_plugin = watts.PluginRELAP5('relap5_template', plotfl_to_csv=False)

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
    <watts.parameters.Parameters at 0x0x15549e5b8d60>

    >>> results.parameters['radius']
    6.0

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
