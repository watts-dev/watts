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
can be saved to an HDF5 file::

    params.save('parameters.h5')

and later re-created using the :meth:`~watts.Parameters.from_hdf5` method::

    loaded_params = watts.Parameters.from_hdf5('parameters.h5')

By themselves, :class:`~watts.Parameters` are not very useful, but when
combined with plugin classes, they become building blocks for sophisticated
workflows.

Plugins
+++++++

Using a particular code within WATTS requires a "plugin" that controls input file
generation, execution, and post-processing. Two plugin classes,
:class:`~watts.PluginSAM` and :class:`~watts.PluginOpenMC`, have already been
added to WATTS and are available for your use.

SAM Plugin
~~~~~~~~~~

The :class:`~watts.PluginSAM` class enables SAM simulations using a templated
input file. For codes like SAM that use text-based input files, WATTS relies on
the `Jinja <https://jinja.palletsprojects.com>`_ templating engine for handling
templated variables and expressions. The templated input file looks like a
normal SAM input file where some values have been replaced with
**variables**, which are denoted by ``{{`` and ``}}`` pairs and get replaced
with actual values when the template is *rendered*. For example, a templated
input file might look as follows:

.. code-block:: jinja

    [GlobalParams]
        global_init_P = {{ He_Pressure }}
        global_init_V = {{ He_velocity }}
        global_init_T = {{ He_inlet_temp }}
        gravity = '-9.8 0 0'
        scaling_factor_var = '1 1e-3 1e-6'
        Tsolid_sf = 1e-3
    []

If the input file is ``sam_template.inp``, the SAM plugin can be created as::

    sam_plugin = watts.PluginSAM('sam_template.inp')

The SAM executable defaults to ``sam-opt`` (assumed to be present on your
:envvar:`PATH`) but can also be specified explicitly with the
:attr:`~watts.PluginSAM.sam_exec` attribute::

    sam_plugin.sam_exec = "/path/to/sam-opt"

To execute SAM, the :meth:`~watts.PluginSAM.workflow` method is called and
expects to receive an instance of :class:`~watts.Parameters`. For the above
template, the :class:`~watts.Parameters` instance should have ``He_Pressure``,
``He_velocity``, and ``He_inlet_temp`` parameters present. Thus, executing SAM
with this templated input file along with corresponding parameters might look as
follows::

    params = watts.Parameters()
    params['He_Pressure'] = 2.0
    params['He_velocity'] = 1.0
    params['He_inlet_temp'] = 600.0
    results = sam_plugin.workflow(params)

Calling the :meth:`~watts.PluginSAM.workflow` method will render the templated
input file (replace variables with values from the :class:`~watts.Parameters`
instance), execute SAM, and collect the output files.

Beyond simple variable substitution, Jinja has sophisticated capabilities for
using logical control structures, filters, calling Python methods, and
extensible templates; for advanced usage, please read through the Jinja
`template designer documentation
<https://jinja.palletsprojects.com/en/3.0.x/templates/>`_.

OpenMC Plugin
~~~~~~~~~~~~~

The :class:`~watts.PluginOpenMC` class handles OpenMC execution in a similar
manner to the :class:`~watts.PluginSAM` class for SAM. However, for OpenMC,
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
:meth:`~watts.PluginOpenMC.workflow` method is called, the "template" function
is called and passed the user-specified :class:`~watts.Parameters`::

    params = watts.Parameters(radius=6.0)
    results = openmc_plugin.workflow(params)

This will generate the OpenMC input files using the template parameters, run
OpenMC, and collect the results.

Results
+++++++

When you run the :meth:`~watts.Plugin.workflow` method on a plugin, an instance
of the :class:`~watts.Results` class specific to the plugin will be returned
that contains information about the results. Every :class:`~watts.Results`
object contains a list of input and output files that were generated:

.. code-block:: pycon

    >>> results = plugin_openmc.workflow(params)
    >>> results.inputs
    [PosixPath('geometry.xml'),
     PosixPath('settings.xml'),
     PosicPath('materials.xmll')]

    >>> results.outputs
    [PosixPath('OpenMC_log.txt'),
     PosixPath('statepoint.250.h5')]

:class:`~watts.Results` objects also contain a copy of the
:class:`~watts.Parameters` that were used at the time the workflow was run:

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

For SAM, the :class:`~watts.ResultsSAM` class
provides a :attr:`~watts.ResultsSAM.csv_data` attribute that gathers the
results from every CSV files generated by SAM::

    sam_result = sam_plugin.workflow(params)
    for key in sam_result.csv_data:
        print(key, sam_result.csv_data[key])

Database
++++++++

When you call the :meth:`~watts.Plugin.workflow` method on a plugin, the
:class:`~watts.Results` object and all accompanying files are automatically
added to a database on disk for later retrieval. Interacting with this database
can be done via the :class:`~watts.Database` class:

.. code-block:: pycon

    >>> db = watts.Database()
    >>> db.results
    [<watts.plugin_openmc.ResultsOpenMC at 0x15530416bfd0>,
     <watts.plugin_openmc.ResultsOpenMC at 0x15530416bbb0>,
     <watts.plugin_sam.ResultsSAM at 0x1553043c8a30>]

By default, the database will be created in a user-specific data directory (on
Linux machines, this is normally within ``~/.local/share``). However, the
location of the database can be specified::

    db = watts.Database('/opt/watts_db/')

Creating a database this way doesn't change the default path used when running
plugin workflows. If you want to change the default database path used in
workflows, the :meth:`~watts.Database.set_default_path` classmethod should be
used::

    >>> watts.Database.set_default_path('/opt/watts_db')
    >>> db = watts.Database()
    >>> db.path
    PosixPath('/opt/watts_db')

To clear results from the database, simply use the
:meth:`~watts.Database.clear` method:

.. code-block::

    >>> db.clear()
    >>> db.results
    []

Be aware that clearing the database **will** delete all the corresponding
results on disk, including input and output files from the workflow.
