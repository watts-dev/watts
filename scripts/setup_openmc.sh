#!/bin/bash
########################################################################
# Date: 2022-09-08
# Author: kkiesling (kkiesling [at] anl [dot] gov)
# Comment: Install OpenMC and its dependencies into the Workbench conda
# environment so that that are available in workbench.
########################################################################

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# ----------------------------------------------------------------------
# Initialize conda
script_path=$(cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P)
# source $script_path/setup_conda_wb.sh


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
printf "${GREEN}Found Workbench:${NC} ${workbench_path}\n"
printf "${GREEN}Activated Conda: ${NC} ${conda_path}\n"


# ----------------------------------------------------------------------
# Clone original workbench environment (if not already cloned) and
# generate .yml copy (base_original.yml) if it is not already saved locally
printf "${GREEN}Cloning original workbench environment to:${NC} ${CONDA_DEFAULT_ENV}_base\n"
# "no" == do not overwrite environment if it already exists
yes no | conda create --name ${CONDA_DEFAULT_ENV}_clone --clone ${CONDA_DEFAULT_ENV}
if [ ! -f ${script_path}/${CONDA_DEFAULT_ENV}_original.yml ]; then
    conda env export -n $CONDA_DEFAULT_ENV -f ${script_path}/${CONDA_DEFAULT_ENV}_original.yml
    printf "${GREEN}Original workbench environment saved to:${NC} ${script_path}/${CONDA_DEFAULT_ENV}_original.yml\n"
fi

# ----------------------------------------------------------------------
# Install OpenMC into the conda environment
printf "${GREEN}Installing OpenMC into Workbench conda environment${NC}\n"
yes | conda install -c conda-forge openmc

printf "${GREEN}OpenMC successfully installed in Workbench environment.${NC}\n"
printf "To complete the setup, add ${BLUE}OPENMC_CROSS_SECTIONS${NC} variable to Arc Workbench configuration.\n"
