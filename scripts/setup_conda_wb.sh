#!/bin/bash
########################################################################
# Date: 2022-12-22
# Authors: zooi (zooi [at] anl [dot] gov)
# Comment: Finds the workbench conda environment and initializes it.
# Requires `workbench_path` to be set in workbench.sh
########################################################################

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# ----------------------------------------------------------------------
# Gather workbench_path from workbench.sh
source workbench.sh

# check that workbench_path was retrieved
if [ -z $workbench_path ]; then
    printf "${RED}ERROR: Could not find workbench_path; please confirm 'workbench_path' entry in workbench.sh file${NC}\n"
    exit 1
fi

# Check that retrieved path to Workbench application exists
if [ ! -d $workbench_path ]; then
    printf "${RED}ERROR: Path to Workbench application does not exist; please confirm 'workbench_path' entry in workbench.sh file${NC}\n"
    printf "    ${workbench_path}\n"
    exit 1
fi

# # ----------------------------------------------------------------------
# Find conda in Workbench
conda_path="${workbench_path}/rte/conda"
if [ ! -f "${conda_path}/bin/conda" ]; then
    printf "${RED}ERROR: Path to conda executable within Workbench application does not exist; please confirm 'workbench_path' entry in workbench.sh file${NC}\n"
    printf "    ${conda_path}/bin/conda\n"
    exit 1
fi

# ----------------------------------------------------------------------
# Activate Workbench conda environment
# >>> conda init >>>
#!! Contents within this block are managed by 'conda init' !!
__conda_setup="$(CONDA_REPORT_ERRORS=false "${conda_path}/bin/conda" shell.bash hook 2> /dev/null)"
if [ $? -eq 0 ]; then
   \eval "$__conda_setup"
else
   if [ -f "${conda_path}/etc/profile.d/conda.sh" ]; then
       . "${conda_path}/etc/profile.d/conda.sh"
       CONDA_CHANGEPS1=false conda activate base
   else
       PATH="${conda_path}/conda/bin:${PATH}"
   fi
fi
unset __conda_setup
# <<< conda init <<<

# ----------------------------------------------------------------------
# Check Python version available in Workbench (v3.x required)
pyv=$(python -V 2>&1 | sed 's/.* \([0-9]\).\([0-9]\).*/\1\2/')
if [ $pyv -lt 36 ]; then
    printf "${RED}ERROR: Workbench with Python >= 3.6 enabled is required.${NC}\n"
    printf "    Python version: `python --version`\n"
    exit 1
fi

# ----------------------------------------------------------------------
printf "${GREEN}Found Workbench:${NC} ${workbench_path}\n"
printf "${GREEN}Activated Conda: ${NC} ${conda_path}\n"

yes | python -m pip install watts

printf "${GREEN}WATTS successfully set up in Workbench.\n"