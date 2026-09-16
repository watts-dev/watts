# 1App_ACCERT_LargeTokamak

## Purpose

This example provides a demonstration on how to use WATTS to run ACCERT for the
large tokamak fusion reference model, and how to read the levelized cost of
electricity (LCOE) that ACCERT computes for its fusion models. The discount rate
is swept to show how the LCOE responds to the financing assumptions.

## Code(s)

- ACCERT

## Keywords

- ACCERT execution
- Fusion cost estimation
- Levelized cost of electricity
- Parametric study

## File descriptions

- [__watts_exec.py__](watts_exec.py): WATTS workflow for this example. This is the file to execute to run ACCERT.
- [__ACCERT_input.tmpl__](ACCERT_input.tmpl): Templated input file for ACCERT.

## Notes

ACCERT computes the LCOE for the `large_tokamak` and `stellarator` reference
models only; `lcoe` and `lcoe_table` raise `FileNotFoundError` for the fission
models. The same input works for a stellarator by changing `ref_model`.

Fusion models have no cost elements, so `cost_element_table` and
`affected_cost_element_table` are unavailable for them. They also do not define
an electric power output that ACCERT recognizes when it escalates costs, so
`total_OCC_per_kW` is unavailable as well.
