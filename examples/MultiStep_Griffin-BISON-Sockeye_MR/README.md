# MultiStep_Griffin-BISON-Sockeye_MR

## Purpose

This example provides a demonstration on how to use WATTS to model multi-step Workflows for multiphysics simulation involving various MOOSE applications coupled by MOOSE's MultiApps system.

## Code(s)
 
- MOOSE MultiApp
- Sockeye
- BISON
- Griffin

## Keywords
 
- Multi-steps
- MultiApp
- Micro-reactor
- Steady-state
- Transient

## File descriptions

- [__watts_exec.py__](watts_exec.py): Workflow definition. This is the file to execute to run the problem described above.
- [__unitcell_nogap_hom_xml_G11_df_MP.xml__](unitcell_nogap_hom_xml_G11_df_MP.xml): ISOXML file containing multigroup XS for Griffin
- [__3D_unit_cell_FY21_level-1_bison.e__](3D_unit_cell_FY21_level-1_bison.e): Mesh file with heat pipe holes for BISON/MOOSE subapplication.
- [__3D_unit_cell_FY21_supersimple.e__](3D_unit_cell_FY21_supersimple.e): Another mesh file??

### Steady State
- [__MP_ss_griffin.tmpl__](MP_ss_griffin.tmpl): Griffin input at steady-state - this is main template for steady-state.
- [__MP_ss_moose.i__](MP_ss_moose.i): MOOSE input for thermal heat conduction at steady-state. This is sub-app to Griffin.
- [__MP_ss_sockeye.i__](MP_ss_sockeye.i): Sockeye input for heat conduction through heatpipes at steady-state. This is sub-app to MOOSE.

### Null Transient
- [__MP_trN_griffin.tmpl__](MP_trN_griffin.tmpl): Griffin input during null transient.
- [__MP_trN_moose.i__](MP_trN_moose.i): MOOSE input for thermal heat conduction during null transient.
- [__MP_trN_sockeye.i__](MP_trN_sockeye.i): Sockeye input for heat conduction through heatpipes during null transient.

### Transinet
- [__MP_tr_griffin.tmpl__](MP_tr_griffin.tmpl): Griffin input during transient.
- [__MP_tr_moose.i__](MP_tr_moose.i): MOOSE input for thermal heat conduction during transient.
- [__MP_tr_sockeye.i__](MP_tr_sockeye.i): Sockeye input for heat conduction through heatpipes during transient.
