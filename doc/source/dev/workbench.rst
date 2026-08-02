.. devguide_workbench:

Adding Application to Workbench
-------------------------------

If you wish to use WATTS on the NEAMS Workbench with a code
that is not already available, adding the code can be done quite easily.

First, you have to develop a plugin for the code and add it to WATTS following
the steps described previously. Once the plugin is available, you can then add it
to `watts_ui.py`.

In the `run_direct()` function, you will need to add an `elif` statement as follows,

.. code-block::

    elif plugin['code'].upper() == '<name_of_new_code>':
        app_plugin = watts.name_of_new_plugin(
            template_file=plugin['template'],
            executable=exec,
            extra_inputs=plugin['extra_inputs'],
            extra_template_inputs=plugin['extra_template_inputs'],
            show_stdout=plugin['show_stdout'],
            show_stderr=plugin['show_stderr'])

Note tha additional steps might be necessary here depending on the code that
is being added.

If the plugin is developed to be similar to the other plugins on WATTS,
no other changes are necessary to `watts_ui.py`. Otherwise, the developer
is responsible for making sure that `watt_ui.py` can read the results
produced by the plugin. Within `run_direct()`, the results from the plugin
should be extracted and saved to `watts_params` as individual entries. This
is required for the coupling and data-transfer between different codes.

Next, the `watts.sch` file needs to be updated. The name of the new code needs
to be added to the `code` block as follows::

    watts{
        plugins{
            plugin{
                code{
                    Description = "[Required] All - Name of application"
                    ...
                    ValEnums=[PyARC RELAP5 ... <name_of_new_code>]
                }
            }
        }
    }

Note that the name used for the new code used here must match that used in
`watts_ui.py`.

Adding new plugin options
+++++++++++++++++++++++++

Any additional options needed by the plugin can be added under the `plugin`
block as follows::

     watts{
        plugins{
            plugin{
               additional_plugin_option{
                    Description = "[optional] New_code - Description of the new option"
                    MinOccurs=0
                    MaxOccurs=1
                    ValType=String
                    InputTmpl="plugin.additional_plugin_option"
                }
            }
        }
    }

Note that `MinOccurs` and `MaxOccurs` represent the minimum and maximum occurences of
this option, `ValType` is the input type of the new option, and `InputTmpl` is the
template file for the new option located in the `etc/templates` directory. Template
file is optional but highly recommended as it provides a template or example to other users.

If new plugin options are added, the `create_plugins()` function in `watts_ui.py` must
be updated. The function essentially creates a nested Python dictionary that contains one
or more individual dictionaries where each individual dictionary stores the information
of each plugin. The function utilizes a series of `if` statements to decide what information
should be stored for each plugin.

If the input of the new option is a string, the new option can be added as follows ::

    if plg.new_option_name is not None:
            nested_plugins['new_option_name'] = str(
                plg.new_option_name.value).strip('\"')

If the input is a list ::

    if plg.new_option_name is not None:
        nested_plugins['new_option_name'] = convert_to_list(plg.new_option_name)

If the input is a bool ::

    nested_plugins['new_option_name'] = False

    if plg.new_option_name is not None and str(plg.new_option_name.value).capitalize() == 'True':
        nested_plugins['new_option_name'] = True

Similar approach can be used for plugin options of different input types.
