ChildExactlyOne = [ watts ]
watts{
    Description = "[optional] for watts calculations"
    MinOccurs = 0
    MaxOccurs = 1
    InputTmpl = "watts"
    workflow_level1{
        Description = "[required] Workflow definition - first level"
        InputTmpl="sonobject"
        MinOccurs=1
        MaxOccurs=1

        % ChildAtLeastOne = [plugin workflow_level2] % we need at least to do a plugin calc or define a sub-workflow

        iteration{
            Description = "[optional] definition of iterations workflow"
            InputTmpl="sonobject"
            MinOccurs=0
            MaxOccurs=1
            plugin{
                Description = "[required] ID of the second plugin"
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
                InputTmpl="flagtypes"
                ValType=Real
            }
            convergence_params{
                Description = "[required] Parameter to compare for convergence"
                MinOccurs=1
                MaxOccurs=1
                ValType=String
            }
            to_sub_params{
                Description = "[required] Parameter(s) to send from plugin_1 to  plugin_2"
                InputTmpl="sonarray"
                MinOccurs=0
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            to_main_params{
                Description = "[required] Parameter(s) to send from plugin_2 to  plugin_1"
                InputTmpl="sonarray"
                MinOccurs=0
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }

        }
        parametric{
            Description = "[optional] definition of parametric workflow"
            InputTmpl="sonobject"
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
                InputTmpl="sonarray"
                MinOccurs=1
                MaxOccurs=1
                value{
                    MinOccurs=1
                    MaxOccurs=NoLimit
                }
            }
        }
        optimization{
            Description = "[optional] definition of optimization workflow"
            InputTmpl="sonobject"
            MinOccurs=0
            MaxOccurs=1
            objective_functions{
                Description = "[required] the parameter to optimize"
                MinOccurs=1
                MaxOccurs=1
                ValType=String
            }
            method{
                Description = "[required] optimization parameter"
                MinOccurs=1
                MaxOccurs=1
                ValType=String
            }
            tolerance{
                Description = "[required] convergence criteria"
                MinOccurs=1
                MaxOccurs=1
                ValType=Real
            }
        }
        plugin{
            Description = "[optional] plugin specification"
            InputTmpl="flagtypes"
            MinOccurs=0
            MaxOccurs=NoLimit
            ValType=String
            ExistsIn = ["../../plugins/plugin/id"]
        }
        variables{
            Description = "[optional] Variables definition"
            InputTmpl="sonobject"
            MinOccurs=0
            MaxOccurs=1
            ChildUniqueness = [ "param/id"]
            param{
                Description = "[optional] Parameter definition"
                InputTmpl="param"
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
                range{
                    Description = "[optional] range of the value (for optimization)"
                    InputTmpl="sonarray"
                    MinOccurs=0
                    MaxOccurs=1
                    value{
                        MinOccurs=2
                        MaxOccurs=2
                        ValType=Real
                    }
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
        workflow_level2{
            Description = "[optional] Workflow definition - second level"
            InputTmpl="sonobject"
            MinOccurs=0
            MaxOccurs=NoLimit
        }
        postprocessors{
            Description = "[optional] postprocessor "
            InputTmpl="sonobject"
            MinOccurs=0
            MaxOccurs=NoLimit
            ChildUniqueness = ["id"]
            value{
                Description = "[required] operation of the postprocessor"
                MinOccurs=1
                MaxOccurs=1
                ValType=String
            }
            id{
                Description = "[required] ID of postprocessor"
                MinOccurs=1
                MaxOccurs=1
                ValType=String
            }
        }
    }
    plugins{
        Description = "[required] Plugins definition"
        InputTmpl="sonobject"
        MinOccurs=1
        MaxOccurs=1
        ChildUniqueness = [ "plugin/id"]

        plugin{
            Description = "[required] Plugins definition"
            InputTmpl="sonobject"
            MinOccurs=1
            MaxOccurs=NoLimit
            id{
                MinOccurs=0
                MaxOccurs=1
                ValType=String
            }
            code{
                Description = "Code name"
                MaxOccurs=1
                MinOccurs=1
                ValType=String
                InputTmpl="flagtypes"
                InputDefault= codename
                ValEnums=[PyARC OpenMC SERPENT ABCE MCNP MOOSE SAS Dakota Serpent RELAP5]
            }
            template{
                Description = "Template name"
                MaxOccurs=1
                MinOccurs=1
                ValType=String
                InputTmpl="flagtypes"
                InputDefault= "path-to-template"
            }
            exec_dir{
                MinOccurs=0
                MaxOccurs=1
                ValType=String
            }
            exec_name{
                MinOccurs=0
                MaxOccurs=1
                ValType=String
            }
            executable{
                MinOccurs=0
                MaxOccurs=1
                ValType=String
            }
            extra_inputs{
                Description = "[optional] List of extra (non-templated) input files that are needed"
                InputTmpl="sonarray"
                MinOccurs=0
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            extra_template_inputs{
                Description = "[optional] List of extra templated input files that are needed"
                InputTmpl="sonarray"
                MinOccurs=0
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            scores{
                Description = "[optional] List of scores for OpenMC tallies"
                InputTmpl="sonarray"
                MinOccurs=0
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            score_names{
                Description = "[optional] List of representative names for scores"
                InputTmpl="sonarray"
                MinOccurs=0
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            output{
                Description = "[optional] List of output files"
                InputTmpl="sonarray"
                MinOccurs=0
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            show_stderr{
                MinOccurs=0
                MaxOccurs=1
                ValType=String
            }
            show_stdout{
                MinOccurs=0
                MaxOccurs=1
                ValType=String
            }
            plotfl_to_csv{
                MinOccurs=0
                MaxOccurs=1
                ValType=String
            }
            extra_args{
                Description = "[optional] List of extra arguments"
                InputTmpl="sonarray"
                MinOccurs=0
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                }
            }
            conv_channel{
                MinOccurs=0
                MaxOccurs=1
                ValType=String
            }
            conv_primar4{
                MinOccurs=0
                MaxOccurs=1
                ValType=String
            }
            auto_link_files{
                MinOccurs=0
                MaxOccurs=1
                ValType=String
            }
        }
    }
}
