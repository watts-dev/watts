.. _plugins:

Available Plugins
-----------------

MOOSE Plugin
++++++++++++

The :class:`~watts.PluginMOOSE` class enables MOOSE simulations using a
templated input file. This is demonstrated here for a SAM application, but the
plugin would apply equally well to other MOOSE applications such as BISON. For a
MOOSE-based application, a templated input file might look as follows:

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

If you need to specify additional input files / templates, see
:ref:`input_files`.

The MOOSE plugin defaults to using the executable ``moose-opt`` but can also be
specified explicitly with the :attr:`~watts.PluginMOOSE.executable` attribute::

    moose_plugin.executable = "/path/to/sam-opt"

OpenMC Plugin
+++++++++++++

The :class:`~watts.PluginOpenMC` class operates slightly differently than other
plugins since OpenMC doesn't primarily rely on text-based inputs. For OpenMC,
inputs are generated programmatically through the OpenMC Python API. Instead of
writing a text template, for this plugin you need to write a function that
accepts an instance of :class:`~watts.Parameters` and generates the necessary
XML files. For example::

    def jezebel_model(params):
        model = openmc.Model()

        pu_metal = openmc.Material()
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
++++++++++++

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

    pyarc_plugin = watts.PluginPyARC('pyarc_template')

The path to PyARC directory must be specified explicitly with the
:attr:`~watts.PluginPyARC.executable` attribute::

    pyarc_plugin.executable = "/path/to/PyARC"

To execute PyARC, the :meth:`~watts.PluginPyARC` instance is called directly the
same way as other plugins. Extra input files and templates can be specified as
described in :ref:`input_files`.

SAS4A/SASSY-1 Plugin
++++++++++++++++++++

The :class:`~watts.PluginSAS` class handles SAS4A/SASSY-1 execution in a similar
manner to the :class:`~watts.PluginMOOSE` class for MOOSE. SAS4A/SASSY-1 uses
text-based input files which can be templated as follows:

.. code-block:: jinja

    47    1        {{ flow_per_pin }}
    3     1 {{ total_reactor_power }}
    7     1                {{ tmax }}

If the templated input file is `sas_template`, then the SAS4A/SASSY-1 plugin can
be instantiated with the following command line::

    sas_plugin = watts.PluginSAS('sas_template')

The SAS executable is OS-dependent. It defaults to ``sas.x`` (assumed to be
present on your :envvar:`PATH`) for Linux and macOS, and ``sas.exe`` for
Windows. You can also explicitly specify the
:attr:`~watts.PluginSAS.executable`::

    sas_plugin.executable = "/path/to/sas-exec"

Furthermore, the paths to the SAS utilities that convert the ".dat" files to
".csv" files must be specified with the :attr:`~watts.PluginSAS.conv_channel`
and :attr:`~watts.PluginSAS.conv_primar4` attributes::

    sas_plugin.conv_channel  = "/path/to/CHANNELtoCSV.x"
    sas_plugin.conv_primar4  = "/path/to/PRIMAR4toCSV.x"

Similar to the SAS executable, the utilities are also OS-dependent. To execute
SAS, the :meth:`~watts.PluginSAS` instance is called directly in the same way as
other plugins.

RELAP5-3D Plugin
++++++++++++++++

The :class:`~watts.PluginRELAP5` class handles execution of RELAP5-3D. Note that
the plugin is designed for the execution of RELAP5-3D v4.3.4 and thus may not be
compatible with other version of RELAP5-3D. RELAP5-3D uses text-based input
files that can be templated as follows:

.. code-block:: jinja

    *                 Time         Power
    20250001          -1.0         0.0
    20250002           0.0      {{ heater_power_1 }}
    20250003         1.0e3      {{ heater_power_2 }}

If the templated input file is `relap5_template`, then the RELAP5-3D plugin can be
instantiated with the following command line::

    relap5_plugin = watts.PluginRELAP5('relap5_template')

RELAP5-3D requires the executable, license key, and the input file to be in the
same directory to run. Thus, before running the RELAP5-3D plugin, you need to
specify the directory that the executable and the license key are in (they must
be in the same directory). This can be done by adding the ``RELAP5_DIR``
variable to the environment or by explicitly specifying the path in the Python
script as::

    relap5_plugin.relap5_dir = "/path/to/relap5_dir/"

The RELAP5 executable is OS-dependent. It defaults to ``relap5.x`` (assumed to
be present on your :envvar:`PATH`) for Linux and macOS, and ``relap5.exe`` for
Windows.

As with other plugins, extra input files and templates can be specified as
described in :ref:`input_files`. Note that the fluid property files can be
specified via ``extra_args``. Another approach is to simply put them in the same
directory as the executable and license key before running the plugin.

For the postprocessing of RELAP5-3D results, the plugin converts the default
"plotfl" plot file generated by RELAP5-3D into a ".CSV" file. Card-104 must be
specified as "ascii" in the RELAP5-3D input file as::

    104          ascii

to ensure that the "plotfl" is in ASCII format instead of the default binary
format. As the conversion process could be computationally expensive, user can
turn it off by omitting Card-104 in the RELAP5-3D input file and adding
``plotfl_to_csv=False`` when instantiating the plugin as follows::

    relap5_plugin = watts.PluginRELAP5('relap5_template', plotfl_to_csv=False)

MCNP Plugin
+++++++++++

The :class:`~watts.PluginMCNP` class handles execution of MCNP. As with other
plugins, MCNP input files can be templated as described in
:ref:`usage_templates`. By default, this plugin will try to call ``mcnp6`` but
this can be changed with the :attr:`~watts.PluginMCNP.executable` attribute if
needed::

    mcnp_plugin = watts.PluginMCNP('mcnp_input')
    mcnp_plugin.executable = "mcnp5"

Serpent Plugin
++++++++++++++

The :class:`~watts.PluginSerpent` class handles execution of Serpent 2. As with
other plugins, Serpent input files can be templated as described in
:ref:`usage_templates`. By default, this plugin will try to call ``sss2``. After
running Serpent::

    serpent_plugin = watts.PluginSerpent('serpent_input')
    result = serpent_plugin()

the Serpent output files will be available to you through the
:attr:`~watts.Results.outputs` attribute:

.. code-block:: pycon

    >>> result.outputs
    [PosixPath('serpent_input_det0.m'),
     PosixPath('serpent_log.txt'),
     PosixPath('serpent_input.seed'),
     PosixPath('serpent_input.out'),
     PosixPath('serpent_input_res.m')]

At this point, we recommend using the `serpentTools
<https://serpent-tools.readthedocs.io>`_ package for interacting with the output
files. For example::

    results_reader = serpentTools.ResultsReader(str(result.outputs[-1]))

Dakota Plugin
+++++++++++++

The :class:`~watts.PluginDakota` class handles execution of Dakota. Dakota uses
text-based input files that can be templated as follows:

.. code-block:: jinja

    real = {{ real }}
    work_directory named = {{ workdir }}

Note that the execution of the Dakota plugin is slightly different and involves
more steps than the execution of the other plugins. Dakota is essentially an
optimization and uncertainty quantification tool that needs to be coupled to
other external tools or software.

The execution of Dakota with WATTS is essentially a two-step process. In the
first step, WATTS creates Dakota's input file using the user-provided template
and runs Dakota. In the second step, Dakota drives the execution of the coupled
code (PyARC, SAM, SAS, etc.) via a Python script known as the "Dakota driver".
The Dakota driver also facilitates the exchange of information between Dakota
and the coupled code. Note that this is done through Dakota's `interfacing`
library. The user needs to ensure that this library is available prior to running
Dakota with WATTS.

To run Dakota with WATTS, the user needs to provide a number of files including
the the input file for Dakota, the WATTS Python script for executing Dakota,
the input file for the coupled code, the WATTS script for executing the coupled
code, and the Dakota driver Python script, in addition to any file necessary to
run the coupled code. Note that all of these files could be templated automatically
by WATTS using the `template_file` and `extra_template_inputs` options, provided
they are text-based.

If the templated Dakota input file is `dakota_watts_opt.in`, then the Dakota
plugin can be instantiated with the following command line::

    dakota_plugin = watts.PluginDakota('dakota_watts_opt.in')

If the coupled code has a text-based input file, users can also template
this file (or other necessary files) with the `extra_template_inputs` options::

    dakota_plugin = watts.PluginDakota(
        template_file='dakota_watts_opt.in',
        extra_template_inputs=['extra_template_file_name', 'other_necessary_files'])

During the execution of WATTS, the working directory is switched to a temporary
location. Non-templated files needed by the coupled code (license file, data file,
etc.) can be copied to the temporary location with the `extra_inputs` option::

    dakota_plugin = watts.PluginDakota(
        template_file='dakota_watts_opt.in',
        extra_template_inputs=['extra_template_file_name', 'other_necessary_files'],
        extra_inputs=['file_1', 'file_2'])

As mentioned earlier, Dakota drives the execution of the coupled code through a
Python script known as the Dakota driver. A template for the Dakota driver is
provided in the example. Just like the other files mentioned earlier, the Dakota
driver can also be templated using the approach described above.

Furthermore, the path to the 'dakota.sh' shell script
needs to be provided either by setting the :envvar:`DAKOTA_DIR` environment
variable to the directory containing `dakota.sh` or by adding it through the
input file as::

    dakota_plugin.dakota_exec = "path/to/dakota.sh"

Once the execution is complete, WATTS saves the results from all iterations as
individual objects and the final results as a separate object known as `finaldata1`
in the :class:`~watts.Parameters` class.

The setup of WATTS-Dakota coupling is more involved than other codes. Users are
strongly encouraged to visit the example case `Optimization_PyARC_DAKOTA` for
detailed explanation on how to prepare the input files.
