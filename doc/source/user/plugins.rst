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

A-LEAF Plugin
+++++++++++++
The :class:`~watts.PluginALEAF` class enables simulations with the Argonne 
Low-carbon Electricity Analysis Framework (A-LEAF) code using a text based 
input file for fuel price modification. The A-LEAF code using an excel based
input file, and the A-LEAF plugin will only modify the fuel price under the
``Fuel`` section of the input file. Since A-LEAF code is still under
active development, the plugin will be updated as the code is updated.

The A-LEAF fuel price input file can be templated as follows:

.. code-block:: jinja

    Scenario	FUEL	Type	Unit	2022	2023	2024	2025	2026	2027	2028	2029	2030	2031	2032	2033	2034	2035	2036	2037	2038	2039	2040	2041	2042	2043	2044	2045	2046	2047	2048	2049	2050	2051	2052	2053	2054	2055	2056	2057	2058	2059	2060
    Reference	Coal	Real	2021 $/MMBtu	1.64	1.61	1.65	1.57	1.52	1.50	1.49	1.50	1.50	1.50	1.50	1.50	1.51	1.52	1.53	1.54	1.56	1.56	1.58	1.59	1.60	1.60	1.62	1.63	1.64	1.65	1.65	1.66	1.66	1.75	1.85	1.96	2.07	2.19	2.31	2.44	2.58	2.73	2.89
    Reference	NG	Real	2021 $/MMBtu	3.84	3.49	3.17	3.00	2.98	3.08	3.25	3.36	3.46	3.54	3.58	3.65	3.64	3.64	3.65	3.67	3.68	3.69	3.72	3.73	3.70	3.71	3.65	3.61	3.60	3.60	3.62	3.60	3.59	3.80	4.01	4.24	4.48	4.74	5.01	5.29	5.59	5.91	6.25
    Reference	Petroleum	Real	2021 $/MMBtu	12.18	10.50	11.39	11.61	11.89	12.20	12.46	12.58	12.82	13.08	13.27	13.42	13.54	13.67	13.86	14.03	14.20	14.26	14.55	14.70	14.75	15.00	15.28	15.36	15.58	15.65	15.62	15.65	15.59	16.48	17.42	18.41	19.46	20.57	21.74	22.98	24.29	25.68	27.14
    Reference	Nuclear	Real	2021 $/MMBtu	0.72	0.72	0.72	0.72	0.72	0.73	0.73	0.73	0.73	0.73	0.73	0.74	0.74	0.74	0.74	0.74	0.74	0.75	0.75	0.75	0.75	0.76	0.76	0.76	0.76	0.76	0.77	0.77	0.77	0.81	0.86	0.91	0.96	1.02	1.07	1.14	1.20	1.27	1.34
    Reference	Biomass	Real	2020 $/MMBTU	5.00	5.11	5.22	5.34	5.45	5.57	5.70	5.82	5.95	6.08	6.22	6.35	6.49	6.63	6.78	6.93	7.08	7.24	7.40	7.56	7.73	7.90	8.07	8.25	8.43	8.61	8.80	9.00	9.20	9.72	10.27	10.86	11.48	12.13	12.82	13.56	14.33	15.15	16.01
    Reference	OGS	Real	2020 $/MMBTU	3.84	3.49	3.17	3.00	2.98	3.08	3.25	3.36	3.46	3.54	3.58	3.65	3.64	3.64	3.65	3.67	3.68	3.69	3.72	3.73	3.70	3.71	3.65	3.61	3.60	3.60	3.62	3.60	3.59	3.80	4.01	4.24	4.48	4.74	5.01	5.29	5.59	5.91	6.25
    Base	Coal	Real	2020 $/MMBTU	1.57	1.54	1.57	1.50	1.45	1.43	1.43	1.43	1.43	1.44	1.43	1.43	1.44	1.45	1.46	1.47	1.49	1.49	1.51	1.52	1.52	1.53	1.54	1.56	1.56	1.57	1.57	1.58	1.58	1.67	1.77	1.87	1.98	2.09	2.21	2.33	2.47	2.61	2.76
    Base	NG	Real	2020 $/MMBTU	3.67	3.34	3.03	2.87	2.84	2.94	3.10	3.21	3.30	3.38	3.42	3.48	3.48	3.47	3.48	3.50	3.52	3.52	3.55	3.56	3.54	3.54	3.48	3.45	3.44	3.43	3.46	3.44	3.43	3.62	3.83	4.05	4.28	4.52	4.78	5.05	5.34	5.65	5.97
    Base	Petroleum	Real	2020 $/MMBTU	11.63	10.03	10.88	11.09	11.35	11.65	11.90	12.01	12.24	12.49	12.68	12.82	12.93	13.05	13.24	13.40	13.56	13.61	13.90	14.04	14.09	14.32	14.60	14.67	14.88	14.95	14.92	14.94	14.89	15.74	16.63	17.58	18.58	19.64	20.76	21.95	23.20	24.52	25.92
    Base	Nuclear	Real	2020 $/MMBTU	{{fuel_2022}}	{{fuel_2023}}   {{fuel_2024}}	{{fuel_2025}}	{{fuel_2026}}	{{fuel_2027}}	{{fuel_2028}}	{{fuel_2029}}	{{fuel_2030}}	{{fuel_2031}}	{{fuel_2032}}	{{fuel_2033}}	{{fuel_2034}}	{{fuel_2035}}	{{fuel_2036}}	{{fuel_2037}}	{{fuel_2038}}	{{fuel_2039}}	{{fuel_2040}}	{{fuel_2041}}	{{fuel_2042}}	{{fuel_2043}}	{{fuel_2044}}	{{fuel_2045}}	{{fuel_2046}}	{{fuel_2047}}	{{fuel_2048}}	{{fuel_2049}}	{{fuel_2050}}	{{fuel_2051}}	{{fuel_2052}}	{{fuel_2053}}	{{fuel_2054}}	{{fuel_2055}}	{{fuel_2056}}	{{fuel_2057}}	{{fuel_2058}}	{{fuel_2059}}	{{fuel_2060}}
    Base	Biomass	Real	2020 $/MMBTU	5.00	5.11	5.22	5.34	5.45	5.57	5.70	5.82	5.95	6.08	6.22	6.35	6.49	6.63	6.78	6.93	7.08	7.24	7.40	7.56	7.73	7.90	8.07	8.25	8.43	8.61	8.80	9.00	9.20	9.72	10.27	10.86	11.48	12.13	12.82	13.56	14.33	15.15	16.01
    Base	OGS	Real	2020 $/MMBTU	3.67	3.34	3.03	2.87	2.84	2.94	3.10	3.21	3.30	3.38	3.42	3.48	3.48	3.47	3.48	3.50	3.52	3.52	3.55	3.56	3.54	3.54	3.48	3.45	3.44	3.43	3.46	3.44	3.43	3.62	3.83	4.05	4.28	4.52	4.78	5.05	5.34	5.65	5.97
    Low	Coal	Real	2020 $/MMBTU	1.41	1.38	1.42	1.35	1.31	1.29	1.28	1.29	1.29	1.29	1.29	1.29	1.30	1.30	1.32	1.33	1.34	1.34	1.36	1.37	1.37	1.38	1.39	1.40	1.41	1.42	1.41	1.42	1.43	1.51	1.59	1.68	1.78	1.88	1.99	2.10	2.22	2.35	2.48
    Low	NG	Real	2020 $/MMBTU	3.30	3.00	2.73	2.58	2.56	2.64	2.79	2.89	2.97	3.05	3.07	3.13	3.13	3.13	3.14	3.15	3.17	3.17	3.20	3.20	3.18	3.19	3.13	3.11	3.10	3.09	3.11	3.09	3.09	3.26	3.45	3.64	3.85	4.07	4.30	4.55	4.81	5.08	5.37
    Low	Petroleum	Real	2020 $/MMBTU	10.46	9.03	9.79	9.98	10.22	10.48	10.71	10.81	11.02	11.24	11.41	11.53	11.64	11.75	11.91	12.06	12.21	12.25	12.51	12.63	12.68	12.89	13.14	13.21	13.39	13.45	13.43	13.45	13.40	14.16	14.97	15.82	16.73	17.68	18.69	19.75	20.88	22.07	23.33
    Low	Nuclear	Real	2020 $/MMBTU	0.62	0.62	0.62	0.62	0.62	0.62	0.62	0.63	0.63	0.63	0.63	0.63	0.63	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	0.41	1.03	1.09	1.15
    Low	Biomass	Real	2020 $/MMBTU	4.50	4.60	4.70	4.80	4.91	5.02	5.13	5.24	5.36	5.47	5.59	5.72	5.84	5.97	6.10	6.24	6.37	6.51	6.66	6.80	6.95	7.11	7.26	7.42	7.59	7.75	7.92	8.10	8.28	8.75	9.25	9.77	10.33	10.92	11.54	12.20	12.90	13.63	14.41
    Low	OGS	Real	2020 $/MMBTU	3.30	3.00	2.73	2.58	2.56	2.64	2.79	2.89	2.97	3.05	3.07	3.13	3.13	3.13	3.14	3.15	3.17	3.17	3.20	3.20	3.18	3.19	3.13	3.11	3.10	3.09	3.11	3.09	3.09	3.26	3.45	3.64	3.85	4.07	4.30	4.55	4.81	5.08	5.37
        
Before running the A-LEAF plugin, you need to specify the directory that the
executable and the license key are in (they must be in the same directory). This
can be done by adding the ``A-LEAF_DIR`` variable to the environment or by
explicitly specifying the path in the Python script as::

    aleaf_plugin = watts.PluginALEAF(
        'aleaf_template',
        executable="/path/to/A-LEAF"
    )

The A-LEAF plugin can be instantiated with the following command line::

    aleaf_plugin = watts.PluginALEAF('aleaf_template')

As with other plugins, :class:`~watts.PluginALEAF` can be used by calling the
:meth:`~watts.PluginALEAF` instance directly the same way as other plugins.
    aleaf_plugin = watts.PluginALEAF('aleaf_template')
    aleaf_result = aleaf_plugin(params)

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

Note: Users are advised to use Dakota v6.18 or latest, as earlier versions may potentially
lead to complications or issues with WATTS.


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

GCMat Plugin
++++++++++++

The :class:`~watts.PluginGCMat` class enables simulations with Argonne's global
critical materials agent-based model (GCMat). This code simulates dynamic
economic markets that are composed of agents who have complex decision-making
behaviors, and interact with and influence each other, possibly indirectly
through market signals.

The GCMat plugin requires a template input file that can be templated as follows:

.. code-block:: jinja

    region    final demand agent	final demand product	reference product	unit	2010	2011	2012	2013	2014	2015	2016	2017	2018	2019	2020	2021	2022	2023	2024	2025	2026	2027	2028	2029	2030
    final demand U	U	U	tonnes	111847.841748839	112977.61792812	114118.805988	115271.5212	116435.88	117612	118800	120000	121200	122412	123636.12	124872.4812	126121.206012	127382.41807212	128656.242252841	{{final_demand_2025}}	{{final_demand_2026}}	{{final_demand_2027}}	{{final_demand_2028}}	{{final_demand_2029}}	{{final_demand_2030}}

    China    final demand U	U		shares of total	0.107142857142857	0.106698999696878	0.112674964564139	0.114434523188336	0.116194081812533	0.1278	0.1299	0.132	0.1341	0.1362	0.1383	0.1404	0.1425	0.1446	0.1467	{{china_2025}}	{{china_2026}}	{{china_2027}}	{{china_2028}}	{{china_2029}}	{{china_2030}}

    US    final demand U	U		shares of total	0.206589879692216	0.201409879668034	0.199574650237538	0.196450274218913	0.194620873740305	0.193447312012611	0.190358597294858	0.187635077997256	0.185744587021863	0.183688235605066	0.180393178767648	0.177208294866757	0.174389224194135	0.171923735369984	0.169723351626385	{{us_2025}}	{{us_2026}}	{{us_2027}}	{{us_2028}}	{{us_2029}}	{{us_2030}}

    Europe    final demand U	U		shares of total	0.16491345183516	0.160710857760063	0.154355276635327	0.149054613139685	0.145906896593099	0.143775880528747	0.141896860630669	0.140266791187998	0.138026220404039	0.135574967728323	0.132758006582095	0.130102830325263	0.127653579579804	0.125407763844851	0.123338987757727	{{eu_2025}}	{{eu_2026}}	{{eu_2027}}	{{eu_2028}}	{{eu_2029}}	{{eu_2030}}

    ROW    final demand U	U		shares of total	0.521353811330767	0.531180262874025	0.533394108562996	0.539080588452066	0.543278147354063	0.535073807414382	0.536243130077473	0.536734120790743	0.541204905572035	0.541712831061545	0.548846808065192	0.554835894215335	0.556026422605261	0.556024685007383	0.556929270113103	{{row_2025}}	{{row_2026}}	{{row_2027}}	{{row_2028}}	{{row_2029}}	{{row_2030}}


The GCMat plugin can be instantiated with the following command line::

    gcmat_plugin = watts.PluginGCMat('gcmat_template')

Before running the GCMat plugin, the directory that contains the executable
'run_repast.sh' must be set. This can be done by setting the ``GCMAT_DIR``
environment variable::

    export GCMAT_DIR='/path/to/gcmat/output'

As with other plugins, :class:`~watts.PluginGCMat` is used by::

    gcmat_plugin = watts.PluginGCMat('gcmat_template')
    gcmat_result = gcmat_plugin(params)
