
import os
import sys, getopt
# import watts # this needs to be installed in Workbench environment (follow example from setup_openmc or setup_dassh)
###
#etc nstauff$ cp watts.py /Applications/Workbench-5.0.0.app/Contents/rte/
#pywatts nstauff$ mkdir bin
#pywatts nstauff$ ln -s /Applications/Workbench-5.0.0.app/Contents/bin/sonvalidxml bin/sonvalidxml
#pywatts nstauff$ ln -s /Applications/Workbench-5.0.0.app/Contents/wasppy ./
# if needed - change wasppy/xml2obj.py line 89 - if isinstance(src, (str,bytes)):
# chmod 777 watts_ui.py
# execute with command: `python watts_ui.py -i examples/watts_comprehensive.son`
###

def load_obj(input_path, watts_path):
    '''convert son file to xml stream and create python data structure'''
    import subprocess
    sonvalidxml = watts_path + "/bin/sonvalidxml"
    schema = watts_path + "/etc/watts.sch"
    cmd = ' '.join([sonvalidxml, schema, input_path])
    xmlresult = subprocess.check_output(cmd, shell=True)
    ### obtain pieces of input by name for convenience
    from wasppy import xml2obj
    return xml2obj.xml2obj(xmlresult)

# Need to update and get properly from workbench the executable path and the argument
watts_path = "/Users/nstauff/Documents/CODES/WATTS/src/watts_ui/"
opts, args = getopt.getopt(sys.argv[1:],"hi:o:",["ifile=","ofile="])
for opt, arg in opts:
    if opt == "-i":
         input_path = os.getcwd() +"/"+ str(arg)

watts = load_obj(input_path, watts_path).watts

if watts.workflow_level1 is not None:
    print ("here - workflow_level1")
    if watts.workflow_level1.variables is not None:
    	for it, param in enumerate(watts.workflow_level1.variables.param):
    		print (str(param.id), str(param.value.value), str(param.unit.value))
if watts.plugins is not None:
    for it, plg in enumerate(watts.plugins.plugin):
        print ("plugin ", str(plg.id), " code ", str(plg.code.value))
