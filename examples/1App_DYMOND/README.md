# 1App_DYMOND

## Purpose

This example demonstrates how to use WATTS to run DYMOND, a nuclear fuel cycle simulation tool built on AnyLogic. The scenario models a simplified U.S. fuel cycle with legacy LWR fleets transitioning to advanced reactors with fuel recycling.

## Code(s)

- DYMOND

## Keywords

- Fuel Cycle Simulation
- Recycling
- Reprocessing
- Fast Reactors

## File Descriptions

- [__watts_exec.py__](watts_exec.py): WATTS workflow that defines all scenario parameters in Python and runs DYMOND. Parameters include reactor types, deployment schedules, reprocessing plants, storage facilities, and output configuration.
- [__dymond_template.json__](dymond_template.json): Jinja2 template for the DYMOND JSON input file. Supports the full input format including all facility types (reactor, enrichment, fabrication, reprocessing, storage, facility), deployments, events, and output configuration.

## Prerequisites

- DYMOND build directory with launcher scripts (`DYMOND_windows.bat`, `DYMOND_linux.sh`, or `DYMOND_mac`)
- `DYMOND_DIR` environment variable set to the DYMOND build directory
- Recipe files (e.g., `lwr_recipe.json`, `sfr_recipe.json`) and ORIGEN libraries (e.g., `ASFR.f33`) passed as `extra_inputs` or placed in the build directory
- `h5py` Python package

## Template Parameters

The template accepts the following parameter groups (see `watts_exec.py` for a full example):

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_year` | int | Yes | Simulation start year |
| `duration` | int/float | Yes | Simulation duration (in time units) |
| `depletion_path` | dict | Yes | Path to depletion solver (e.g., `{"ORIGEN-S": "path/to/scalerte.exe"}`) |
| `reactors` | list[dict] | Yes | Reactor type definitions |
| `storages` | list[dict] | Yes | Storage type definitions |
| `deployments` | dict | Yes | Fleet deployment schedules |
| `energy_demand` | list[float] | No | Energy demand curve (one value per time step) |
| `enrichments` | list[dict] | No | Enrichment facility definitions |
| `fabrications` | list[dict] | No | Fabrication facility definitions |
| `reprocessing_plants` | list[dict] | No | Reprocessing facility definitions |
| `facilities` | list[dict] | No | Generic facility definitions |
| `events` | list[dict] | No | Timed/periodic/conditional events |
| `output_stocks` | list[dict] | No | Stock report configurations |
| `output_flows` | list[dict] | No | Flow report configurations |
| `output_operations` | dict | No | Operations report configuration |
