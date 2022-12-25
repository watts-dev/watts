# PicardIterations_SAM-OpenMC_VHTR_Workbench

## Purpose

This example demonstrates how to use WATTS on Workbench to perform several iterations where SAM calculations are followed by OpenMC calculation and temperature/power information are exchanged until convergence. This example is slightly different from the non Workbench example under the same name.

## Code(s)
 
- SAM
- OpenMC

## Keywords
 
- Information transfer from SAM to OpenMC
- Picard iterations until convergence

## File descriptions

- [__watts_exec.py__](watts_exec.py): WATTS workflow for this example. This is the file to execute to run the problem described above.
- [__openmc_template__](openmc_template.py): Link to OpenMC templated model.
- [__sam_template__](sam_template): Link to SAM templated model.
- [__watts_comprehensive.son__](watts_comprehensive.son): Workbench input file for this example.