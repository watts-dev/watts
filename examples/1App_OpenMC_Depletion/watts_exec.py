# SPDX-FileCopyrightText: 2022-2025 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to perform an OpenMC depletion
calculation using integrator.integrate() with MPI parallelism. The VHTR
unit-cell model from the 1App_OpenMC_VHTR example is reused here with
depletable fuel materials.

When running with MPI, all ranks share the same temporary working directory
via the MPI-aware cd_tmpdir fix, ensuring coordinated HDF5 file I/O during
depletion.

Run in serial:
    python watts_exec.py

Run with MPI (recommended for depletion):
    mpiexec -np <N> python watts_exec.py
"""

from math import cos, pi

import openmc
import openmc.deplete
import watts
from astropy.units import Quantity

from openmc_template import build_openmc_model


params = watts.Parameters()

# Core design params
params['ax_ref'] = 20                                               # cm
params['num_cool_pins'] = 1*6 + 2*6 + 6*2/2
params['num_fuel_pins'] = 6 + 6 + 6 + 3*6 + 2*6/2 + 6/3
params['Height_FC'] = 2.0                                           # m
params['Lattice_pitch'] = 2.0
params['FuelPin_rad'] = 0.90                                        # cm
params['cool_hole_rad'] = 0.60                                      # cm
params['Coolant_channel_diam'] = (params['cool_hole_rad'] * 2)/100 # m
params['Graphite_thickness'] = (params['Lattice_pitch'] - params['FuelPin_rad'] - params['cool_hole_rad'])  # cm
params['Assembly_pitch'] = 7.5 * 2 * params['Lattice_pitch'] / (cos(pi/6) * 2)
params['lbp_rad'] = 0.25                                            # cm
params['mod_ext_rad'] = 0.90                                        # cm
params['shell_thick'] = 0.05                                        # FeCrAl
params['liner_thick'] = 0.007                                       # Cr
params['control_pin_rad'] = Quantity(9.9, "mm")

# Control use of S(a,b) tables
params['use_sab'] = True
params['use_sab_BeO'] = True
params['use_sab_YH2'] = False

# OpenMC transport params
params['cl'] = params['Height_FC'] * 100 - 2 * params['ax_ref']    # cm
params['pf'] = 40                                                   # percent
params['batches'] = 100
params['inactive'] = 30
params['particles'] = 1000

# Temperature params
params['temp'] = Quantity(725, "Celsius")
for i in range(1, 6):
    params[f'temp_F{i}'] = Quantity(725, "Celsius")

# Depletion params — time steps in days
params['time_steps'] = [10, 20]              # days
params['power'] = 1e6                                               # W (1 MWt)

# Path to depletion chain file — adjust to match your local installation
# See: https://openmc.org/depletion-chains for available chain files
params['chain_file'] = '/home/garcsamu/OpenMC/TEMA/data/chain_casl_pwr.xml'

params.show_summary(show_metadata=False, sort_by='time')


def run_depletion(params):
    """Run OpenMC depletion using CECMIntegrator.

    All MPI ranks participate in transport via integrator.integrate().
    Post-processing of results is performed only on rank 0.

    Parameters
    ----------
    params
        WATTS parameters dictionary
    """
    # Load geometry and settings written by build_openmc_model
    geometry = openmc.Geometry.from_xml()
    settings = openmc.Settings.from_xml()

    # Set up depletion operator using the coupled transport approach
    operator = openmc.deplete.CoupledOperator(
        openmc.Model(geometry=geometry, settings=settings),
        chain_file=params['chain_file']
    )

    # Set up time steps and power list for CECMIntegrator
    power_list = [params['power']] * len(params['time_steps'])
    integrator = openmc.deplete.CECMIntegrator(
        operator, params['time_steps'], power_list, timestep_units='d'
    )

    print("Starting depletion...")
    integrator.integrate()
    print("Depletion complete.")

    # Post-process results — only rank 0 reads output files
    try:
        from mpi4py import MPI
        rank = MPI.COMM_WORLD.Get_rank()
    except ImportError:
        rank = 0

    if rank == 0:
        results = openmc.deplete.Results('depletion_results.h5')
        time, keff = results.get_keff()
        time_days = [t / 86400 for t in time]

        # Store final k-effective in params
        params['keff_final'] = float(keff[-1][0])
        params['time_days'] = time_days


# Create OpenMC plugin and run depletion
openmc_plugin = watts.PluginOpenMC(build_openmc_model, show_stderr=True, show_stdout=True)
openmc_plugin(params, function=lambda: run_depletion(params))

params.show_summary(show_metadata=False, sort_by='time')
