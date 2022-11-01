.. devguide_plugins:

Developing Plugins
------------------

As discussed in the user's guide, WATTS has a variety of plugins for different
codes (primarily focused on application codes in nuclear science and
engineering) that are already available. If you wish to use WATTS with a code
that does not already have a plugin available, extending WATTS to handle another
code can be done quite easily.

There are two ways to incorporate new codes into WATTS. First, if the code uses
a text-based input, the :class:`~watts.PluginTemplate` class can be used to
specify the executable, how it should be invoked from a command-line, and a
template for the input file. For example, if you have a code called ``goblin``
that should be executed from a command line as:

.. code-block:: sh

    goblin input=filein.gbl

a plugin can be set up as::

    goblin = watts.PluginTemplate(
        executable='goblin',
        execute_command=['{self.executable}', 'input={self.input_name}'],
        template_file='filein.gbl'
    )

where ``filein.gbl`` is a template input for the ``goblin`` code. Executing the
code is done by passing it a set of parameters::

    params = watts.Parameters()
    ...

    result = goblin(params)

Plugin Customization
++++++++++++++++++++

If the :class:`~watts.PluginTemplate` class doesn't quite meet your needs, you
will need to write your own plugin class that is a subclass of either
:class:`~watts.Plugin` or :class:`~watts.PluginTemplate`. Subclassing
:class:`~watts.PluginTemplate` is appropriate if the code you're working with
uses text-based input files. If text-based input files are not used, you will
need to subclass the more general :class:`~watts.Plugin` class.

In either case, your plugin class will need to provide one or more of the
following:

- A ``prerun(params)`` method that is responsible for rendering inputs based on
  the parameters that were passed and any other tasks that need to be taken care
  of prior to execution.
- A ``run(**kwargs)`` method that is responsible for executing the code using
  the rendered inputs. Keyword arguments are passed through when calling the
  plugin.
- A ``postrun(params, name)`` method that is responsible for collecting a list
  of input and output files and returning a :class:`~watts.Results` object.

If you are subclassing :class:`watts.PluginGeneric`, note that default
implementations of ``prerun``, ``run``, and ``postrun`` are already provided.
The executable and command-line arguments can also be customized through the
``executable`` and ``execute_command`` properties. Finally, the unit system to
be used for performing unit conversions is specified as an argument that is
passed through the ``__init__`` methods.


Results Customization
+++++++++++++++++++++

The basic :class:`~watts.Results` class stores a list of input and output files
associated with the execution of a plugin, the :class:`~watts.Parameters` that
were used to generate input files, and a timestamp. When writing your own
plugin, if you don't need to provide further customization of the results, you
should simply subclass :class:`~watts.Results` with a name matching the plugin.
For example, if you have::

    class PluginGoblin(PluginGeneric):
        ...

A minimal corresponding results class would be::

    class ResultsGoblin(Results):
        """Results from a Goblin simulation"""

However, you may wish to provide extra methods and properties that allow users
of your plugin to easily interrogate results (for example, pulling out key
numerical results from output files).
