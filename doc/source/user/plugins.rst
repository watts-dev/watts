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
specified explicitly ::

    moose_plugin = watts.PluginMOOSE(..., executable="/path/to/sam-opt")

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

The path to the PyARC module can be specified explicitly::

    pyarc_plugin = watts.PluginPyARC(
        'pyarc_template',
        executable="/path/to/PyARC/PyARC.py"
    )

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

The name of the SAS executable is OS-dependent. It defaults to ``sas.x`` but can
be changed if you are running on Windows::

    sas_plugin = watts.PluginSAS('sas_template', executable='sas.exe')

Furthermore, the paths to the SAS utilities that convert the ".dat" files to
".csv" files must be specified with the :attr:`~watts.PluginSAS.conv_channel`
and :attr:`~watts.PluginSAS.conv_primar4` attributes::

    sas_plugin.conv_channel  = "/path/to/CHANNELtoCSV.x"
    sas_plugin.conv_primar4  = "/path/to/PRIMAR4toCSV.x"

By default, the plugin will try to find these utilities based on the location of
the SAS executable. To execute SAS, the :meth:`~watts.PluginSAS` instance is
called directly in the same way as other plugins.

The SAS plugin can sometimes generates multiple ".csv" files. The data from each ".csv"
file are saved into an individual dictionary named after the file, and these
individual dictionaries are saved under `csv_data`. To access a specific data, you
can do::

    sas_result.csv_data['name_of_csv_file']['name_of_specific_data']

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
this can be changed if needed::

    mcnp_plugin = watts.PluginMCNP('mcnp_input', executable='mcnp5')

Natural Element Expansion
~~~~~~~~~~~~~~~~~~~~~~~~~

The :class:`~watts.PluginMCNP` class allows you to specify natural elements in
MCNP material definitions that are automatically expanded based on what
naturally occurring isotopes appear in your ``xsdir`` file. In your templated
MCNP input file, this feature can be utilized by adding a `filter section
<https://jinja.palletsprojects.com/en/3.1.x/templates/#id11>`_:

.. code-block:: jinja

    {% filter expand_element %}
    m1    24000.70c  -0.17
          26000.70c  -0.79
          28000.70c  -0.10
          42000.70c  -0.02
    {% endfilter %}

Natural elements can be represented using the standard ZAID identifiers as above
(e.g., 26000 represents natural iron) or using their atomic symbol:

.. code-block:: jinja

    {% filter expand_element %}
    m1    Cr.70c  -0.17
          Fe.70c  -0.79
          Ni.70c  -0.10
          Mo.70c  -0.02
    {% endfilter %}

The ``expand_element`` custom filter also accepts a single argument specifying
what cross section suffix to apply by default when one is missing:

.. code-block:: jinja

    {% filter expand_element('70c') %}
    m1    Cr  -0.17
          Fe  -0.79
          Ni  -0.10
          Mo  -0.02
    {% endfilter %}

By default, :class:`~watts.PluginMCNP` will look for the ``xsdir`` file found
under the directory specified by the :envvar:`DATAPATH` environment variable to
determine what nuclides are available. However, you can explicitly specify a
different ``xsdir`` file at the time :class:`~watts.PluginMCNP` is
instantiated::

    mcnp_plugin = watts.PluginMCNP('mcnp_input', xsdir='xsdir_jendl5')

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


ABCE Plugin
+++++++++++

The :class:`~watts.PluginABCE` class enables simulations with the Agent Based Capacity
Expansion (ABCE) code using a templated input file. Since :mod:`watts` relies on the `Jinja
<https://jinja.palletsprojects.com>`_ templating engine, any parameter in the ABCE settings
file could be updated with :mod:`watts`. For example:

.. code-block:: jinja

    num_steps: {{ N_STEPS }}  # The number of timesteps

    run_ALEAF: {{ run_ALEAF }}  # Toggles the A-LEAF dispatch model

    natural_gas_price: {{ NATURAL_GAS_PRICE }}  # Sets the price of natural gas in [$/MMBTU]
    conv_nuclear_FOM: {{ NFOM_VALUE }}  # Sets the fixed operating costs of conventional nuclear plants.

As with other plugins, :class:`~watts.PluginABCE` is easily used by::

    abce_plugin = watts.PluginABCE(template_file, show_stdout=True, show_stderr=True)
    abce_result = abce_plugin(params, extra_args=['-f'])

.. note::
    `ABCE` is still under active development.


Dakota Plugin
+++++++++++++

The :class:`~watts.PluginDakota` class handles execution of Dakota. Dakota uses
text-based input files that can be templated as follows:

.. code-block:: jinja

    real = {{ real }}
    work_directory named = {{ workdir }}

Note that the execution of the Dakota plugin is slightly different and involves
more steps than the execution of the other plugins. Dakota is an
optimization and uncertainty quantification tool that needs to be coupled to
other external tools or software.

The execution of Dakota with WATTS is a two-step process. In the
first step, WATTS creates Dakota's input file using the user-provided template
and runs Dakota. In the second step, Dakota drives the execution of the coupled
code (PyARC, SAM, SAS, etc.) via a Python script known as the "Dakota driver".
The Dakota driver also facilitates the exchange of information between Dakota
and the coupled code. Note that this is done through Dakota's `interfacing`
library. The user needs to ensure that this library is available prior to running
Dakota with WATTS.

To run Dakota with WATTS, the user needs to provide a number of files including
the input file for Dakota, the WATTS Python script for executing Dakota,
the input file for the coupled code, the WATTS script for executing the coupled
code (note that this can involve complex workflows with several codes or iterations),
and the Dakota driver Python script, in addition to any file necessary to
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

In the Dakota input file, users need to provide the names of required files to the
`link_files` or the `copy_files` options where these files will be copied by Dakota
to the working directory during each iteration. Users can choose to input the names of
these files manually or they can choose to have WATTS automatically include all
file names in the `extra_template_inputs` and `extra_inputs` options. To do so, simply use
the `auto_link_files` option::

    dakota_plugin = watts.PluginDakota(
        template_file='dakota_watts_opt.in',
        extra_template_inputs=['extra_template_file_name', 'other_necessary_files'],
        auto_link_files='<string_name_for_files>',
        extra_inputs=['file_1', 'file_2'])

And set::

    link_files = {{ <string_name_for_files> }}

in the Dakota input file. Note that the same `<string_name_for_files>` must be used
in the two locations mentioned above.

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

ACCERT Plugin
+++++++++++++

The :class:`~watts.PluginACCERT` class enables simulations with the Algorithm for the
Capital Cost Estimation of Reactor Technologies (ACCERT) code using a templated input
file such as the following:

.. code-block:: jinja

    power(Thermal){ value = {{ thermal_power }}   unit = MW }
    power(Electric){ value = {{ electric_power }}   unit = MW }
    l0COA(2){
        l1COA(21){
            l2COA(217){
                total_cost{value =  {{ cost_217 }}  unit = dollar}
            }
        }
    }

Before running the ACCERT plugin, the directory that the executable 'Main.py'
must be set. This can be done by adding the ``ACCERT_DIR``
variable to the environment::

    export ACCERT_DIR='/path/to/accert/src'

Or the path to the ACCERT module can be specified explicitly::

    accert_plugin = watts.PluginACCERT(
        'accert_template',
        executable="/path/to/accert/src/Main.py"
    )


As with other plugins, :class:`~watts.PluginACCERT` is used by::

    accert_plugin = watts.PluginACCERT('accert_template')
    accert_result = accert_plugin(params)
