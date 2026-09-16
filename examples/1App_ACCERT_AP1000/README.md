# 1App_ACCERT_AP1000

## Purpose

This example provides a demonstration on how to use WATTS to run ACCERT for the
AP1000 two-unit plant, and how to read the overnight capital cost (OCC) that
ACCERT escalates to a target dollar year.

## Code(s)

- ACCERT

## Keywords

- ACCERT execution
- Overnight capital cost extraction
- Cost escalation

## File descriptions

- [__watts_exec.py__](watts_exec.py): WATTS workflow for this example. This is the file to execute to run ACCERT.
- [__ACCERT_input.tmpl__](ACCERT_input.tmpl): Templated input file for ACCERT.

## Notes

The `post_process { occ = true }` block in the input file makes ACCERT write the
OCC summary. Without it, the `total_OCC_escalated` and `total_OCC_per_kW`
results are unavailable and the other OCC results are reconstructed from the
account table.
