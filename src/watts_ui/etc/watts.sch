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

        ChildAtLeastOne = [plugin workflow_level2] % we need at least to do a plugin calc or define a sub-workflow
        
        iterations{
            Description = "[optional] definition of iterations workflow"
            InputTmpl="sonobject"
            MinOccurs=0
            MaxOccurs=1
        }
        parametric{
            Description = "[optional] definition of parametric workflow"
            InputTmpl="sonobject"
            MinOccurs=0
            MaxOccurs=1
        }
        optimization{
            Description = "[optional] definition of optimization workflow"
            InputTmpl="sonobject"
            MinOccurs=0
            MaxOccurs=1
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
                    Description = "[required] reference value"
                    ValType=Real
                    InputTmpl="flagtypes"
                    MinOccurs=1
                    MaxOccurs=1
                }
                unit{
                    Description = "[required] reference value"
                    ValType=String
                    InputTmpl="flagtypes"
                    InputDefault= codename
                    ValEnums=[ K m s ]
                    MinOccurs=0
                    MaxOccurs=1
                }
                range{
                    Description = "[required] range of the value (for optimization)"
                    InputTmpl="sonarray"
                    MinOccurs=0
                    MaxOccurs=1
                    value{
                        MinOccurs=2
                        MaxOccurs=2
                        ValType=Real
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
                MinOccurs=1
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
                ValEnums=[ PyARC OpenMC SERPENT ABCE MCNP ]
            }
            template{
                Description = "Template name"
                MaxOccurs=1
                MinOccurs=1
                ValType=String
                InputTmpl="flagtypes"
                InputDefault= "path-to-template"
            }
            extra_inputs{
                InputTmpl="sonarray"
                MinOccurs=0
                MaxOccurs=1
                value{
                    MinOccurs=0
                    MaxOccurs=NoLimit
                    ValType=String
                }
            }
        }
    }
}
