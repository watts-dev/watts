# 1App_SAS_SodiumLoop

## Purpose

This example provides a demonstration on how to use WATTS to run Dakota by coupling it with PyArc.

## Code(s)

- Dakota
- Dakota's Interfacing library
- PyArc

## Keywords

- Optimization

## File descriptions

- [__watts_dakota_exec.py__](watts_dakota_exec.py): This is the main file to execute to run the problem described above.
- [__watts_pyarc_exec.py__](watts_pyarc_exec.py): This is the file to run PyArc.
- [__dakota_watts_opt.in__](dakota_watts_opt.in): Templated Dakota input.
- [__pyarc_template__](pyarc_template): Templated PyArc input.
- [__dakota_driver.py__](dakota_driver.py): Python script that Dakota uses drive the execution of the coupled code (PyArc).
- [__pyarc_input.isotxs](pyarc_input.isotxs): PyArc input data.
- [__lumped.son](lumped.son): PyArc input data.
