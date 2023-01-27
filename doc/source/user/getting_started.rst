.. _getting_started:

Getting Started
---------------

What is :mod:`watts`?
+++++++++++++++++++++

WATTS (Workflow and Template Toolkit for Simulation) consists of a set of Python
classes that can manage simulation workflows for one or multiple codes. It
provides the following capabilities:

- An isolated execution environment when running a code;
- The ability to use placeholder values in input files that are filled in
  programmatically;
- Seamless :ref:`unit conversions <units>` when working with multiple codes;
- A managed database that simulation inputs and outputs are automatically saved
  to; and
- Python classes that provide extra post-processing and analysis capabilities
  for each code.

Basic Execution
+++++++++++++++

There are four major types of classes within :mod:`watts`. The
:class:`~watts.Plugin` class (and its subclasses) provide the main interface to
codes. As an example, let's say we have the following input file for MCNP that
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

When a plugin is called, any input files are copied to a temporary directory to
create an isolated execution environment. Once the code is finished executing,
all input and output files are moved to a database, and you are provided a
:class:`~watts.Results` object that provides an interface to the simulation
artifacts and methods for common post-processing tasks. In the example above,
calling the :class:`~watts.PluginMCNP` instance returns a
:class:`~watts.ResultsMCNP` object, which we can use to get a list of the output
files or determine the resulting :math:`k_\text{eff}` value:

.. code-block:: pycon

    >>> result.outputs
    [PosixPath('MCNP_log.txt'),
     PosixPath('srctp')
     PosixPath('outp')
     PosixPath('runtpe')]
    >>> result.keff
    1.0007+/-0.00053

Templates and Parameters
++++++++++++++++++++++++

The input file shown above is just a normal MCNP input file. However, you can
also put placeholders in an input file and have :mod:`watts` fill them in using
the :class:`~watts.Parameters` class. Let's say we change the input file as
follows:

.. code-block:: jinja

    Bare sphere of plutonium
    1    1    0.04 -1  imp:n=1
    2    0          1  imp:n=0

    1    so   {{ radius }}

    m1   94239.70c 0.04
    kcode 10000 1.0 50 {{ cycles }}
    ksrc 0 0 0

We've added two placeholders, ``{{ radius }}`` and ``{{ cycles }}``, that will
be filled in. Before creating and calling our plugin, we now need to specify
these parameters::

    params = watts.Parameters()
    params['radius'] = 6.0
    params['cycles'] = 200

As before, we create an instance of :class:`~watts.PluginMCNP` but instead of
calling it with no arguments, we pass it the :class:`~watts.Parameters`
instance::

    plugin_mcnp = watts.PluginMCNP("sphere_model")
    result = plugin_mcnp(params)

If we wanted to run this model with a series of different radii, it's now as
simple as changing the corresponding parameter and calling the plugin::

    for r in [2.0, 4.0, 6.0, 8.0, 10.0]:
        params['radius'] = r
        result = plugin_mcnp(params, name=f'r={r}')

Note that the ``name`` argument provides a means of identifying a result both
while the code is executing as well as afterwards. During execution, the
``name`` will be shown in the output:

.. code-block:: text

    [watts] Calling MCNP (r=2.0)...
    [watts] Calling MCNP (r=4.0)...
    [watts] Calling MCNP (r=6.0)...
    [watts] Calling MCNP (r=8.0)...
    [watts] Calling MCNP (r=10.0)...

Results Database
++++++++++++++++

Results are automatically added to a database and persist between invocations of
Python. The ``watts`` command-line tool allows you to quickly get a list of
results:

.. code-block:: console

    $ watts results
    +-------+--------+--------+--------+----------------------------+
    | Index | Job ID | Plugin | Name   | Time                       |
    +-------+--------+--------+--------+----------------------------+
    | 0     | 1      | MCNP   |        | 2022-06-01 13:21:44.713942 |
    | 1     | 2      | MCNP   |        | 2022-06-01 13:23:12.410774 |
    | 2     | 3      | MCNP   | r=2.0  | 2022-06-02 07:46:05.463723 |
    | 3     | 3      | MCNP   | r=4.0  | 2022-06-02 07:46:10.996932 |
    | 4     | 3      | MCNP   | r=6.0  | 2022-06-02 07:46:17.487411 |
    | 5     | 3      | MCNP   | r=8.0  | 2022-06-02 07:46:24.964455 |
    | 6     | 3      | MCNP   | r=10.0 | 2022-06-02 07:46:33.426781 |
    +-------+--------+--------+--------+----------------------------+

Each result listed can be referenced by its index, which is used in other
subcommands. For example, to determine the directory where input/output files
are stored for the result with index 2, you can run:

.. code-block:: console

    $ watts dir 2
    /home/username/.local/share/watts/3c5674ae37094d74af7a7fc5562555a3

The API also allows programmatic access to the database through the
:class:`~watts.Database` class, which provides a list-like object that contains
all previously generated :class:`~watts.Results` objects. For example, we may
want to look at the last five results to see how :math:`k_\text{eff}` varies
with the radius.

.. code-block:: pycon

    >>> database = watts.Database()
    >>> database
    [<ResultsMCNP: 2022-06-01 13:21:44.713942>,
     <ResultsMCNP: 2022-06-01 13:23:12.410774>,
     <ResultsMCNP: 2022-06-02 07:46:05.463723>,
     <ResultsMCNP: 2022-06-02 07:46:10.996932>,
     <ResultsMCNP: 2022-06-02 07:46:17.487411>,
     <ResultsMCNP: 2022-06-02 07:46:24.964455>,
     <ResultsMCNP: 2022-06-02 07:46:33.426781>]

This enables us to easily look at the :math:`k_\text{eff}` value for the last
five MCNP simulations:

.. code-block:: pycon

    >>> [result.keff for result in database[-5:]]
    [0.3523+/-0.00021,
     0.68017+/-0.00042,
     0.97663+/-0.00063,
     1.24086+/-0.00075,
     1.47152+/-0.00081]

Your First ``watts`` Program
++++++++++++++++++++++++++++

To show how the various classes fit together, the example below creates a plugin
for a "code" (in this case, just the Linux ``cat`` command) and executes the
code on a templated input file that is rendered using parameters that are
defined in a :class:`~watts.Parameters` instance. This example assumes we have a
file called triangle.txt containing the following text:

.. code-block:: jinja

    width={{ width }}
    height={{ height }}
    area={{ 0.5 * height * width }}

The ``watts`` script is as follows::

    import watts

    # Create a plugin for the 'cat' code
    plugin = watts.PluginGeneric(
        executable='cat',
        execute_command=['{self.executable}', '{self.input_name}'],
        template_file='triangle.txt',
        unit_system='cgs'
    )

    # Define some parameters that will be used to render the input file
    params = watts.Parameters()
    params['width'] = watts.Quantity(1.0, 'm')
    params['height'] = watts.Quantity(1.0, 'inch')

    # Execute the plugin
    result = plugin(params)

    # Show the resulting input file
    print(result.stdout)

Running this example will produce the following output:

.. code-block:: text

    width=100.0
    height=2.54
    area=127.0

When the plugin is executed, the ``cat`` command is called on the rendered input
file, which is just the triangle.txt file where the parameters have been filled
in. Note that the physical quantities were :ref:`converted <units>` to
centimeters since we indicated that this plugin uses CGS units.
