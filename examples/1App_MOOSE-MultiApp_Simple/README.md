# 1App_MOOSE-MultiApp_Simple

## Purpose

This example provides a demonstration on how to use WATTS to perform a simple simulation leveraging MOOSE's MultiApps system.

## Code(s)
 
- MOOSE MultiApps

## Keywords
 
- Simple MultiApps

## File descriptions

- [__watts_exec.py__](watts_exec.py): Optimization definition with `SciPy`. This is the file to execute to run the problem described above.
- [__main.tmpl__](main.tmpl): Main MOOSE input file for the main application. This input is templated.
- [__main_in.e__](main_in.e): Mesh file for the MOOSE simulation.
- [__sub.i__](sub.i): Input file for the sub-application.
