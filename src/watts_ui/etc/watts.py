#!/usr/bin/python
"""watts runtime environment"""

# standard imports
import os
import sys

# super import
import workbench

class wattsRuntimeEnvironment(workbench.WorkbenchRuntimeEnvironment):
    """watts-specific runtime environment"""
    def __init__(self):
        """constructor"""

        # call super class constructor
        super(wattsRuntimeEnvironment, self).__init__()

    def update_and_print_grammar(self, grammar_path):
        if self.executable == None:            
            import argparse
            # if the -grammar flag appears earlier in the arg list than the -e, it won't have been set
            # so, we must parse the argv for that case
            parser_for_grammar = argparse.ArgumentParser()
            parser_for_grammar.add_argument("-e", type=str)    
            known, unknown = parser_for_grammar.parse_known_args(sys.argv)        
            self.executable = known.e  
            
        if self.executable == None:            
            sys.stderr.write("***Error: The -grammar option requires -e argument!\n")
            sys.exit(1)
        
        watts_bin_dir = os.path.dirname(self.executable)
        watts_dir = watts_bin_dir

        watts_grammar_path = watts_dir+"/etc/watts.wbg"
        
        watts_grammar_mtime = os.path.getmtime(watts_grammar_path)
        try:
            workbench_grammar_mtime = os.path.getmtime(grammar_path)
        except OSError:
            # indicate grammar file is 'way old' 
            # which will indicate it needs to be updated
            workbench_grammar_mtime = 0

        # Update Workbench's grammar status file        
        if watts_grammar_mtime > workbench_grammar_mtime:
            watts_grammar_name = os.path.basename(grammar_path).replace(".wbg","")
            with open(grammar_path,"w") as workbench_grammar_file:
                workbench_grammar_file.write("name='{0}' redirect='{1}'".format(watts_grammar_name, watts_grammar_path))
            print (grammar_path)       
                 
            
        return
    def app_name(self):
        """returns the app's self-designated name"""
        return "watts"

    def app_options(self):
        """list of app-specific options"""
        opts = []

        # TODO add application unique arguments
        return opts

    def prerun(self, options):
        """actions to perform before the run starts"""
        # override values
        options.working_directory = os.path.dirname(options.input)

        # build argument list
        options.input = options.input.replace(options.working_directory + "/", "")

        # call default implementation
        super(wattsRuntimeEnvironment, self).prerun(options)

        #  override the working directory removal - dont do it
        self.cleanup = False

    def run_args(self, options):
        """returns a list of arguments to pass to the given executable"""
        # build argument list
        args = ["-i", options.input]

        # TODO add application unique arguments
        return args

if __name__ == "__main__":
    # execute runtime, ignoring first argument (the python script itself)
    wattsRuntimeEnvironment().execute(sys.argv[1:])
