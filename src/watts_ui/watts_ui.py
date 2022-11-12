
import os

###
#etc nstauff$ cp watts.py /Applications/Workbench-5.0.0.app/Contents/rte/
#pywatts nstauff$ mkdir bin
#pywatts nstauff$ ln -s /Applications/Workbench-5.0.0.app/Contents/bin/sonvalidxml bin/sonvalidxml
#pywatts nstauff$ ln -s /Applications/Workbench-5.0.0.app/Contents/wasppy ./
# if needed - change wasppy/xml2obj.py line 89 - if isinstance(src, (str,bytes)):
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

watts_path = os.getcwd()
input_path = os.getcwd() + "/examples/watts_comprehensive.son"

watts = load_obj(input_path, watts_path).watts

if watts.workflow_level1 is not None:
    print ("here - workflow_level1")
if watts.plugins is not None:
    for it, plg in enumerate(watts.plugins.plugin):
        print ("plugin ", str(plg.id), " code ", str(plg.code.value))
