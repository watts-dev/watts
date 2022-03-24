# Opt_SAM-OpenMC_VHTR-pymoo

## Purpose

This example provides a demonstration on how to use WATTS to perform a multi-criteria design optimization through the `pymoo` genetic algorithms running SAM followed by OpenMC.

## Code(s)
 
- SAM
- OpenMC
- [__pymoo__](https://pymoo.org)

## Keywords
 
- Multi-criteria optimization with `pymoo`
- Information transfer from SAM to OpenMC
- Simple VHTR model

## File descriptions

- [__watts_exec.py__](watts_exec.py): Optimization definition with `pymoo`. This is the file to execute to run the problem described above.
- [__openmc_template__](openmc_template.py): Link to OpenMC templated model.
- [__watts_main__](watts_main.py): Link to main watts model that contains the WATTS workflow.