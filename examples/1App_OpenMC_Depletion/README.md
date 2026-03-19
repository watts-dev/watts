# 1App_OpenMC_Depletion

## Purpose

This example demonstrates how to use WATTS to perform an OpenMC depletion
calculation with MPI parallelism. It extends the `1App_OpenMC_VHTR` example
by adding fuel depletion using `openmc.deplete.CECMIntegrator` via
`integrator.integrate()`.

This example also demonstrates the MPI-aware `cd_tmpdir` fix introduced in
this fork, which ensures all MPI ranks share the same temporary working
directory during depletion — resolving HDF5 file access conflicts that arise
when running `integrator.integrate()` under `mpiexec`.

## Code(s)

- OpenMC

## Keywords

- Depletion
- MPI parallelism
- VHTR unit-cell model
- CECMIntegrator
- integrator.integrate()

## Prerequisites

### Cross sections

Set the `OPENMC_CROSS_SECTIONS` environment variable to point to your cross
sections library:

```bash
export OPENMC_CROSS_SECTIONS=/path/to/cross_sections.xml
```

### Depletion chain file

A depletion chain file is required. Update the `chain_file` parameter in
`watts_exec.py` to point to your local chain file:

```python
params['chain_file'] = '/path/to/chain_file.xml'
```

Chain files can be obtained from the OpenMC data repository:
https://openmc.org/depletion-chains


## Running the example

### Serial

```bash
python watts_exec.py
```

### MPI (recommended for depletion)

```bash
mpiexec -np <N> python watts_exec.py
```

where `<N>` is the number of MPI ranks. Each rank will participate in the
OpenMC transport calculation via `integrator.integrate()`. The Python-level
post-processing (reading results, printing k-effective) is performed only on
rank 0.

A typical HPC submission script might look like:

```bash
#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=2
#SBATCH --cpus-per-task=25

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export OPENMC_CROSS_SECTIONS=/path/to/cross_sections.xml

mpiexec -np ${SLURM_NTASKS} python watts_exec.py
```

## File descriptions

- [__watts_exec.py__](watts_exec.py): WATTS workflow for this example. This
  is the file to execute to run the problem.
- [__openmc_template.py__](openmc_template.py): OpenMC model builder for the
  VHTR unit-cell geometry with depletable fuel materials.

## Notes

- The fuel volume set on each material is approximate — for more accurate
  depletion, compute the exact volume of each fuel region in your geometry.
- `integrator.integrate()` and `openmc.run()` handle MPI differently.
  See the WATTS documentation and OpenMC depletion documentation for details.
