ChildExactlyOne = [ watts ]
watts{
    Description = "[optional] for watts calculations"
    MinOccurs = 0
    MaxOccurs = 1
    InputTmpl = "watts"
    workflow_level1{
        Description = "[required] Workflow definition - first level"
        InputTmpl="workflow_level1"
        MinOccurs=1
        MaxOccurs=1

        % ChildAtLeastOne = [plugin workflow_level2] % we need at least to do a plugin calc or define a sub-workflow
        plugin{
            Description = "[Required] name of plugin"
            InputTmpl="plugin_id"
            MinOccurs=0
            MaxOccurs=NoLimit
            ValType=String
            ExistsIn = ["../../plugins/plugin/id"]
            ChildUniqueness = [ "id"]
        }
        variables{
            Description = "[optional] Variables definition"
            InputTmpl="variables"
            MinOccurs=0
            MaxOccurs=1
            ChildUniqueness = [ "param/id"]
            param{
                Description = "[optional] Parameter definition"
                InputVariants=[ "value" "func" "list" "bool" ]
                MinOccurs=1
                MaxOccurs=NoLimit
                id{
                    MinOccurs=1
                    MaxOccurs=1
                    ValType=String
                }
                value{
                    Description = "[optional] reference value"
                    InputTmpl="flagtypes"
                    MinOccurs=0
                    MaxOccurs=1
                }
                unit{
                    Description = "[optional] reference value"
                    ValType=String
                    InputTmpl="flagtypes"
                    InputDefault= codename
                    MinOccurs=0
                    MaxOccurs=1
                }
                bool{
                    Description = "[optional] boolean"
                    InputTmpl="flagtypes"
                    MinOccurs=0
                    MaxOccurs=1
                }
                list{
                    Description = "[optional] list of real or string"
                    InputTmpl="sonarray"
                    MinOccurs=0
                    MaxOccurs=1
                    value{
                        MinOccurs=1
                        MaxOccurs=NoLimit
                    }
                }
                func{
                    Description = "[optional] operation"
                    InputTmpl="sonarray"
                    MinOccurs=0
                    MaxOccurs=1
                    value{
                        MinOccurs=1
                        MaxOccurs=NoLimit
                        ValType=String
                    }
                }
            }
        }
        iteration{
            Description = "[optional] definition of iterations workflow"
            InputTmpl="iteration"
            MinOccurs=0
            MaxOccurs=1
            plugin{
                Description = "[required] ID of the second plugin"
                InputTmpl="sonobject"
                MinOccurs=1
                MaxOccurs=1
                ValType=String
            }
            nmax{
                Description = "[required] Maximum number of iterations"
                MinOccurs=1
                MaxOccurs=1
                ValType=Real
            }
            convergence_criteria{
                Description = "[required] Convergence criteria"
                MinOccurs=1
                MaxOccurs=1
                ValType=Real
            }
            convergence_params{
                Description = "[required] Parameter to compare for convergence"
                MinOccurs=1
                MaxOccurs=1
                ValType=String
            }
            to_sub_params{
                Description = "[required] Parameter(s) to send from plugin_1 to plugin_2"
                MinOccurs=1
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            to_main_params{
                Description = "[required] Parameter(s) to send from plugin_2 to plugin_1"
                MinOccurs=1
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
        }
        parametric{
            Description = "[optional] definition of parametric workflow"
            InputTmpl="parametric"
            MinOccurs=0
            MaxOccurs=1
            changing_params{
                Description = "[required] the parameter to perform parametric study"
                MinOccurs=1
                MaxOccurs=1
                ValType=String
            }
            changing_values{
                Description = "[required] values for parametric study"
                MinOccurs=1
                MaxOccurs=1
                value{
                    MinOccurs=1
                    MaxOccurs=NoLimit
                }
            }
        }
        % optimization{
        %     Description = "[optional] definition of optimization workflow"
        %     InputTmpl="sonobject"
        %     MinOccurs=0
        %     MaxOccurs=1
        %     objective_functions{
        %         Description = "[required] the parameter to optimize"
        %         MinOccurs=1
        %         MaxOccurs=1
        %         ValType=String
        %     }
        %     method{
        %         Description = "[required] optimization parameter"
        %         MinOccurs=1
        %         MaxOccurs=1
        %         ValType=String
        %     }
        %     tolerance{
        %         Description = "[required] convergence criteria"
        %         MinOccurs=1
        %         MaxOccurs=1
        %         ValType=Real
        %     }
        % }
        % workflow_level2{
        %     Description = "[optional] Workflow definition - second level"
        %     InputTmpl="sonobject"
        %     MinOccurs=0
        %     MaxOccurs=NoLimit
        % }
        % postprocessors{
        %     Description = "[optional] postprocessor "
        %     InputTmpl="sonobject"
        %     MinOccurs=0
        %     MaxOccurs=NoLimit
        %     ChildUniqueness = ["id"]
        %     value{
        %         Description = "[required] operation of the postprocessor"
        %         MinOccurs=1
        %         MaxOccurs=1
        %         ValType=String
        %     }
        %     id{
        %         Description = "[required] ID of postprocessor"
        %         MinOccurs=1
        %         MaxOccurs=1
        %         ValType=String
        %     }
        % }
    }
    plugins{
        Description = "[required] Plugins definition"
        InputTmpl="plugins"
        MinOccurs=1
        MaxOccurs=1
        ChildUniqueness = ["plugin/id"]

        plugin{
            Description = "[required] Plugins definition"
            InputTmpl="plugin"
            MinOccurs=1
            MaxOccurs=NoLimit
            id{
                MinOccurs=0
                MaxOccurs=1
                ValType=String
            }
            code{
                Description = "[Required] All - Name of application"
                MaxOccurs=1
                MinOccurs=1
                ValType=String
                InputTmpl="flagtypes"
                InputDefault= codename
                ValEnums=[PyARC OpenMC SERPENT ABCE MCNP MOOSE SAS Dakota Serpent RELAP5]
            }
            template{
                Description = "[Required] All - Name of template file"
                MaxOccurs=1
                MinOccurs=1
                ValType=String
                InputDefault= "path-to-template"
            }
            exec_dir{
                Description = "[optional] All - Path to executable directory"
                MinOccurs=0
                MaxOccurs=1
                ValType=String
                InputTmpl="plugin.exec_dir"
            }
            exec_name{
                Description = "[optional] All - Name of executable"
                MinOccurs=0
                MaxOccurs=1
                ValType=String
                InputTmpl="plugin.exec_name"
            }
            executable{
                Description = "[optional] All - Path to executable"
                MinOccurs=0
                MaxOccurs=1
                ValType=String
                InputTmpl="plugin.executable"
            }
            extra_inputs{
                Description = "[optional] All - List of extra (non-templated) input files that are needed"
                InputTmpl="plugin.extra_inputs"
                MinOccurs=0
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            extra_template_inputs{
                Description = "[optional] All - List of extra templated input files that are needed"
                MinOccurs=0
                MaxOccurs=1
                InputTmpl="plugin.extra_template_inputs"
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            extra_args{
                Description = "[optional] All - List of extra arguments"
                InputTmpl="plugin.extra_args"
                MinOccurs=0
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            transfer_params{
                Description = "[optional] All - List of parameters to transfer between runs"
                InputTmpl="plugin.transfer_params"
                MinOccurs=0
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            scores{
                Description = "[optional] OpenMC - List of scores for OpenMC tallies"
                MinOccurs=0
                MaxOccurs=1
                InputTmpl="plugin.scores"
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            score_names{
                Description = "[optional] OpenMC - List of representative names for scores"
                MinOccurs=0
                MaxOccurs=1
                InputTmpl="plugin.score_names"
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            show_stderr{
                Description = "[optional] All - Bool to print stderr"
                MinOccurs=0
                MaxOccurs=1
                ValType=String
            }
            show_stdout{
                Description = "[optional] All - Bool to print stdout"
                MinOccurs=0
                MaxOccurs=1
                ValType=String
            }
            plotfl_to_csv{
                Description = "[optional] RELAP5 - Bool to convert PLOTFL to CSV"
                MinOccurs=0
                MaxOccurs=1
                ValType=String
                InputTmpl="plugin.plotfl_to_csv"
            }
            conv_channel{
                Description = "[optional] SAS - Path to CHANNELtoCSV.x"
                MinOccurs=0
                MaxOccurs=1
                ValType=String
                InputTmpl="plugin.conv_channel"
            }
            conv_primar4{
                Description = "[optional] SAS - Path to PRIMAR4toCSV.x"
                MinOccurs=0
                MaxOccurs=1
                ValType=String
                InputTmpl="plugin.conv_primar4"
            }
            auto_link_files{
                Description = "[optional] Dakota - List of auto link files"
                MinOccurs=0
                MaxOccurs=1
                ValType=String
                InputTmpl="plugin.auto_link_files"
            }
        }
    }
}
