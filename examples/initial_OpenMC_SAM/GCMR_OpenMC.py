from pathlib import Path
import os, sys, shutil
import math
import subprocess
import pandas as pd
import openmc
import openmc.mgxs as mgxs
import random
from math import sqrt
import numpy as np
import openmc.model
import math
import os
import sys
from pathlib import Path


# OpenMC
temp = 300
cl = 160
pf = 40

# core design params
ax_ref = 20
num_cpu = 60
Lattice_pitch = 2.0
Assembly_pitch = 9 * Lattice_pitch
fuel_rad = 0.90
lbp_rad = 0.25
mod_ext_rad = 0.90
shell_thick = 0.05
cool_hole_rad = 0.60
control_pin_rad = Lattice_pitch/2




def parse_trisos(triso_univ, num_particles, z_min, z_max, triso_locations_file):
    
    triso_locations = Path(__file__).parent / triso_locations_file
    fh = open(triso_locations, 'r')

    if num_particles == 'all':
        lines_slice = slice(None)
    else:
        lines_slice = slice(0, int(num_particles))

    # get all non-empty lines
    lines = [line for line in fh if line != '\n']
    trisos = []
    num_part = 0
    for line in lines[lines_slice]:
        if line.strip():
            vals = [float(v) for v in line.split()[:-1]]
            center = vals[:3]
            radius = vals[-1]
#            print (center)
            if center[-1] <= z_max and center[-1] >= z_min:
              trisos.append(openmc.model.TRISO(radius, triso_univ, center))
              num_part += 1

    print ("Num particules modeled = %i"%num_part)
    return trisos     

def build_openmc_model():
    """ OpenMC Model """
    use_sab = True
    use_sab_YH2 = True
    num_particles = 'all'

    materials = []
    # Fuel: - volumes are calculated with first step
    fuel = openmc.Material(name="fuel", temperature=temp)
    fuel.set_density('g/cm3', 10.744)
    fuel.depleteable = True
    fuel.add_nuclide('U235', 6.8794E-02, 'ao')
    fuel.add_nuclide('U238', 2.7604E-01, 'ao')
    fuel.add_nuclide('O16',  5.1724E-01, 'ao')
    fuel.add_element('C',    1.3793E-01, 'ao')
    materials.append(fuel)

    boro = openmc.Material(name="B4C-LBP", temperature=temp)
    boro.set_density('g/cm3', 2.47)
    boro.add_nuclide('B10',  0.16, 'ao')
    boro.add_nuclide('B11',  0.64, 'ao')
    boro.add_element('C',    0.20, 'ao')
    materials.append(boro)

    boro_ctr = openmc.Material(name="B4C-CTR", temperature=temp)
    boro_ctr.set_density('g/cm3', 2.47)
    boro_ctr.add_nuclide('B10',  0.16, 'ao')
    boro_ctr.add_nuclide('B11',  0.64, 'ao')
    boro_ctr.add_element('C',    0.20, 'ao')
    materials.append(boro_ctr)

    buffer = openmc.Material(name="buffer", temperature=temp)
    buffer.set_density('g/cm3', 1.04)
    buffer.add_element('C', 1.0, 'ao')
    if use_sab:
        buffer.add_s_alpha_beta('c_Graphite')
    materials.append(buffer)

    PyC1 = openmc.Material(name="PyC1", temperature=temp)
    PyC1.set_density('g/cm3', 1.882)
    PyC1.add_element('C', 1.0, 'ao')
    if use_sab:
        PyC1.add_s_alpha_beta('c_Graphite')
    materials.append(PyC1)

    PyC2 = openmc.Material(name="PyC2", temperature=temp)
    PyC2.set_density('g/cm3', 1.882)
    PyC2.add_element('C', 1.0, 'ao')
    if use_sab:
        PyC2.add_s_alpha_beta('c_Graphite')
    materials.append(PyC2)

    sic = openmc.Material(name="SiC", temperature=temp)
    sic.set_density('g/cm3', 3.171)
    sic.add_nuclide('Si28', 0.4611, 'ao')
    sic.add_nuclide('Si29', 0.0234, 'ao')
    sic.add_nuclide('Si30', 0.0154, 'ao')
    sic.add_element('C', 0.5, 'ao')
    materials.append(sic)

    matrix = openmc.Material(name="matrix", temperature=temp)
    matrix.set_density('g/cm3', 1.806)
    matrix.add_element('C', 1.0 - 0.0000003, 'ao')
    matrix.add_nuclide('B10', 0.0000003, 'ao')
    if use_sab:
        matrix.add_s_alpha_beta('c_Graphite')
    materials.append(matrix)

    refl = openmc.Material(name="BeO", temperature=temp)
    refl.set_density('g/cm3', 2.7987)
    refl.add_nuclide('Be9', 0.50, 'ao')
    refl.add_nuclide('O16', 0.50, 'ao')
    if use_sab:
        refl.add_s_alpha_beta('c_Be_in_BeO')
        refl.add_s_alpha_beta('c_O_in_BeO')
    materials.append(refl)

    yh2 = openmc.Material(name="moderator", temperature=temp)
    yh2.set_density('g/cm3', 4.30*0.95)
    yh2.add_nuclide('Y89', 0.3333, 'ao')
    yh2.add_nuclide('H1',  0.6666, 'ao')
    if use_sab and use_sab_YH2:
        yh2.add_s_alpha_beta('c_H_in_YH2')
        yh2.add_s_alpha_beta('c_Y_in_YH2')
    materials.append(yh2)

    coolant = openmc.Material(name="coolant", temperature=temp)
    coolant.set_density('g/cm3', 0.00365)
    coolant.add_nuclide('He4', 1, 'ao')
    materials.append(coolant)

    shell_mod = openmc.Material(name="shell_mod", temperature=temp)
    shell_mod.set_density('g/cm3', 7.54)
    shell_mod.add_element('C',     1.9010E-03,'ao')
    shell_mod.add_nuclide('Si28',  9.2693E-03,'ao')
    shell_mod.add_nuclide('Si29',  4.7251E-04,'ao')
    shell_mod.add_nuclide('Si30',  3.1166E-04,'ao')
    shell_mod.add_nuclide('P31',   4.1322E-04,'ao')
    shell_mod.add_nuclide('S32',   2.4710E-04,'ao')
    shell_mod.add_nuclide('S33',   1.9511E-06,'ao')
    shell_mod.add_nuclide('S34',   1.1056E-05,'ao')
    shell_mod.add_nuclide('S36',   3.0016E-08,'ao')
    shell_mod.add_nuclide('Cr50',  7.9116E-03,'ao')
    shell_mod.add_nuclide('Cr52',  1.5257E-01,'ao')
    shell_mod.add_nuclide('Cr53',  1.7300E-02,'ao')
    shell_mod.add_nuclide('Cr54',  4.3063E-03,'ao')
    shell_mod.add_nuclide('Mn55',  1.0280E-02,'ao')
    shell_mod.add_nuclide('Fe54',  3.9029E-02,'ao')
    shell_mod.add_nuclide('Fe56',  6.1213E-01,'ao')
    shell_mod.add_nuclide('Fe57',  1.4144E-02,'ao')
    shell_mod.add_nuclide('Fe58',  1.3343E-03,'ao')
    shell_mod.add_nuclide('Ni58',  7.7516E-02,'ao')
    shell_mod.add_nuclide('Ni60',  2.9859E-02,'ao')
    shell_mod.add_nuclide('Ni61',  1.2981E-03,'ao')
    shell_mod.add_nuclide('Ni62',  4.1389E-03,'ao')
    shell_mod.add_nuclide('Ni64',  1.0544E-03,'ao')
    shell_mod.add_nuclide('Mo92',  2.1259E-03,'ao')
    shell_mod.add_nuclide('Mo94',  1.3299E-03,'ao')
    shell_mod.add_nuclide('Mo95',  2.3030E-03,'ao')
    shell_mod.add_nuclide('Mo96',  2.4191E-03,'ao')
    shell_mod.add_nuclide('Mo97',  1.3903E-03,'ao')
    shell_mod.add_nuclide('Mo98',  3.5249E-03,'ao')
    shell_mod.add_nuclide('Mo100', 1.4135E-03,'ao')
    materials.append(shell_mod)

    mat_dict = {}
    for k,v in list(locals().items()):
        if v in materials:
            mat_dict[k] = v

    materials_file = openmc.Materials()
    for mat in materials:
        materials_file.append(mat)
        materials_file.export_to_xml()

    # Create spheres for trisoparticules and cells associated


    # Create TRISO universe
    spheres = [openmc.Sphere(r=r*1e-4)
            for r in [212.5, 312.5, 352.5, 387.5, 427.5]]
    triso_cells = [openmc.Cell(fill=fuel, region=-spheres[0]),
                openmc.Cell(fill=buffer, region=+spheres[0] & -spheres[1]),
                openmc.Cell(fill=PyC1, region=+spheres[1] & -spheres[2]),
                openmc.Cell(fill=sic, region=+spheres[2] & -spheres[3]),
                openmc.Cell(fill=PyC2, region=+spheres[3] & -spheres[4]),
                openmc.Cell(fill=matrix, region=+spheres[4])]
    triso_univ = openmc.Universe(cells=triso_cells)

    spheres_lbp = [openmc.Sphere(r=r*1e-4)
            for r in [100, 118, 141]]
    triso_lbp_cells = [openmc.Cell(fill=boro, region=-spheres_lbp[0]),
                openmc.Cell(fill=buffer, region=+spheres_lbp[0] & -spheres_lbp[1]),
                openmc.Cell(fill=PyC1, region=+spheres_lbp[1] & -spheres_lbp[2]),
                openmc.Cell(fill=matrix, region=+spheres_lbp[2])]
    triso_lbp_univ = openmc.Universe(cells=triso_lbp_cells)


    Z_min = 0
    Z_cl = ax_ref
    Z_cl_out = ax_ref-shell_thick
    Z_up = ax_ref+cl
    Z_up_out = ax_ref+cl + shell_thick
    Z_max = cl+2*ax_ref

    triso_fuel_locations_file = "TRISO_GEN/Part_fuel/PART_U900_PF40_R90.inp"
    trisos_fuel = parse_trisos(triso_univ, num_particles, Z_cl, Z_up, triso_fuel_locations_file)

    triso_lbp_locations_file = "TRISO_GEN/Part_bp/PART_U950_PF20_R25.inp"
    trisos_lbp = parse_trisos(triso_lbp_univ, num_particles, Z_cl, Z_up, triso_lbp_locations_file)

    # Create cylinder for fuel and coolant

    min_x = openmc.XPlane(x0=-Assembly_pitch/2)
    max_x = openmc.XPlane(x0= Assembly_pitch/2)
    min_y = openmc.YPlane(y0=-Assembly_pitch/2)
    max_y = openmc.YPlane(y0= Assembly_pitch/2)

    fuel_radius = openmc.ZCylinder(x0=0.0, y0=0.0, r=fuel_rad)
    mod_rad_0 = openmc.ZCylinder(x0=0.0, y0=0.0, r=mod_ext_rad - shell_thick)                                        
    mod_rad_1 = openmc.ZCylinder(x0=0.0, y0=0.0, r=mod_ext_rad)                                                  
    cool_radius = openmc.ZCylinder(x0=0.0, y0=0.0, r=cool_hole_rad)                                             
    ctr_radius = openmc.ZCylinder(x0=0.0, y0=0.0, r=control_pin_rad)                                             
    lbp_radius = openmc.ZCylinder(x0=0.0, y0=0.0, r=lbp_rad)                                  

    pin_pitch = Lattice_pitch

    min_z=openmc.ZPlane(z0=Z_min, boundary_type='vacuum')
    max_z=openmc.ZPlane(z0=Z_max, boundary_type='vacuum')
    sz_cl=openmc.ZPlane(z0=Z_cl)
    sz_cl_out=openmc.ZPlane(z0=Z_cl_out)
    sz_up=openmc.ZPlane(z0=Z_up)
    sz_up_out=openmc.ZPlane(z0=Z_up_out)
    cpin_low =openmc.ZPlane(z0=Z_up)

    Hex_Pitch = openmc.model.hexagonal_prism(orientation='x',edge_length=Assembly_pitch/math.sqrt(3),origin=(0.0, 0.0),
                                                        boundary_type = 'reflective')   # THIS SHOULD BE REFLECTIVE BONDARY


    # Our last step is to actually create a lattice containing TRISO particles which can be done with the nifty 
    # openmc.model.create_triso_lattice() function. This function requires that we give it a list of TRISO particles, 
    # the lower-left coordinates of the lattice, the pitch of each lattice cell, the overall shape of the lattice
    # (number of cells in each direction), and a background material.
    box1 = openmc.Cell(region= +min_x & -max_x & +min_y & -max_y & +min_z & -max_z)
    lower_left, upper_right = box1.region.bounding_box
    shape = (20, 20, 100)
    # print (shape)
    pitch = (upper_right - lower_left)/shape
    lattice_fuel = openmc.model.create_triso_lattice(trisos_fuel, lower_left, pitch, shape, mat_dict['matrix'])
    box1.fill = lattice_fuel
    univ_triso_fuel = openmc.Universe(cells=[box1])

    box2 = openmc.Cell(region= +min_x & -max_x & +min_y & -max_y & +min_z & -max_z)
    lower_left, upper_right = box2.region.bounding_box
    lattice_lbp = openmc.model.create_triso_lattice(trisos_lbp, lower_left, pitch, shape, mat_dict['matrix'])
    box2.fill = lattice_lbp
    univ_triso_lbp = openmc.Universe(cells=[box2])


    #  HERE WE NEED TO FILL  THE FUEL WITH THESE TRISOPARTICULES
    fuel_cell_1 = openmc.Cell(name='Fuel Pin', fill=univ_triso_fuel , region=-fuel_radius & +sz_cl & -sz_up)
    fuel_cell_2 = openmc.Cell(name='matrix', fill=matrix , region=+fuel_radius  & +sz_cl & -sz_up)
    fuel_cell_3 = openmc.Cell(name='reflL', fill=refl , region=-sz_cl)
    fuel_cell_4 = openmc.Cell(name='reflO', fill=refl , region=+sz_up)
    fuel_universe= openmc.Universe(cells=(fuel_cell_1,fuel_cell_2,fuel_cell_3,fuel_cell_4))

    lbp_cell_1 = openmc.Cell(name='LBP Pin', fill=univ_triso_lbp , region=-lbp_radius & +sz_cl & -sz_up)
    lbp_cell_2 = openmc.Cell(name='matrix', fill=matrix , region=+lbp_radius  & +sz_cl & -sz_up)
    lbp_cell_3 = openmc.Cell(name='reflL', fill=refl , region=-sz_cl)
    lbp_cell_4 = openmc.Cell(name='reflO', fill=refl , region=+sz_up)
    lbp_universe= openmc.Universe(cells=(lbp_cell_1,lbp_cell_2,lbp_cell_3,lbp_cell_4))

    mod_cell_1 = openmc.Cell(name='YH2', fill=yh2, region=-mod_rad_0  & +sz_cl & -sz_up )
    mod_cell_2 = openmc.Cell(name='steel', fill=shell_mod , region=+mod_rad_0 & -mod_rad_1  & +sz_cl & -sz_up)
    mod_cell_3 = openmc.Cell(name='matrix', fill=matrix , region=+mod_rad_1  & +sz_cl & -sz_up)
    mod_cell_5 = openmc.Cell(name='Plug_L', fill=shell_mod , region=-mod_rad_1  & +sz_cl_out & -sz_cl)
    mod_cell_6 = openmc.Cell(name='Plug_LR', fill=refl , region=+mod_rad_1  & +sz_cl_out & -sz_cl)
    mod_cell_7 = openmc.Cell(name='Plug_U', fill=shell_mod , region=-mod_rad_1  & +sz_up & -sz_up_out)
    mod_cell_8 = openmc.Cell(name='Plug_UR', fill=refl , region=+mod_rad_1  & +sz_up & -sz_up_out)
    mod_cell_9 = openmc.Cell(name='LowRef', fill=refl , region=-sz_cl_out)
    mod_cell_10 = openmc.Cell(name='UpRef', fill=refl , region=+sz_up)
    mod_universe= openmc.Universe(cells=(mod_cell_1,mod_cell_2,mod_cell_3,mod_cell_5,mod_cell_6,mod_cell_7,mod_cell_8,mod_cell_9,mod_cell_10))

    coolant_cell_1 = openmc.Cell(name='coolant', fill=coolant , region=-cool_radius)
    coolant_cell_2 = openmc.Cell(name='matrix', fill=matrix , region=+cool_radius  & +sz_cl & -sz_up)
    coolant_cell_3 = openmc.Cell(name='reflL', fill=refl , region=+cool_radius  &  -sz_cl)
    coolant_cell_4 = openmc.Cell(name='reflO', fill=refl , region=+cool_radius  &  +sz_up)
    coolant_universe= openmc.Universe(cells=(coolant_cell_1,coolant_cell_2,coolant_cell_3,coolant_cell_4))

    ctr_cell_1a = openmc.Cell(name='coolant', fill=coolant , region=-ctr_radius & -cpin_low)
    ctr_cell_1b = openmc.Cell(name='abs', fill=boro_ctr , region=-ctr_radius & +cpin_low)
    ctr_cell_2 = openmc.Cell(name='matrix', fill=matrix , region=+ctr_radius  & +sz_cl & -sz_up)
    ctr_cell_3 = openmc.Cell(name='reflL', fill=refl , region=+ctr_radius  &  -sz_cl)
    ctr_cell_4 = openmc.Cell(name='reflO', fill=refl , region=+ctr_radius  &  +sz_up)
    ctr_universe= openmc.Universe(cells=(ctr_cell_1a,ctr_cell_1b,ctr_cell_2,ctr_cell_3,ctr_cell_4))

    Graph_cell_1= openmc.Cell(name='Graph cell', fill=matrix)
    Graph_universe= openmc.Universe(cells=(Graph_cell_1,))

    # Fill the hexagone with fuel and coolant cells

    assembly_description=[[]]*6
    assembly_description[5]=([ctr_universe])
    assembly_description[4] =([fuel_universe])*6
    assembly_description[3] =([fuel_universe]+[coolant_universe])*6
    assembly_description[2] =([coolant_universe] + [fuel_universe] + [lbp_universe] + [coolant_universe] + [fuel_universe] + [mod_universe])*3
    assembly_description[1] =([fuel_universe]+[fuel_universe]+[coolant_universe]+[fuel_universe])*6
    assembly_description[0] =([fuel_universe]+[coolant_universe]+[fuel_universe]+[fuel_universe]+[coolant_universe])*6
    #print (assembly_description)

    lat_core = openmc.HexLattice()
    lat_core.center=(0,0)
    lat_core.pitch=[pin_pitch]
    lat_core.outer=Graph_universe
    lat_core.universes=assembly_description
    # print(lat_core)
    rotated_lat_core = openmc.Cell(fill=lat_core)
    rotated_universe_lat_core = openmc.Universe(cells=(rotated_lat_core,))
    new_cell_lat_core=openmc.Cell()
    new_cell_lat_core.fill=rotated_universe_lat_core
    new_cell_lat_core.rotation=(0.,0.,90.)
    new_universe_lat_core = openmc.Universe(cells=(new_cell_lat_core,))

    main_cell = openmc.Cell(name="MainCell",fill=new_universe_lat_core, region=Hex_Pitch &  +min_z & -max_z )
    TALLY_REGIONS=[main_cell]    

    # OpenMC expects that there is a root universe assigned number zero. Here we
    # assign our three cells to this root universe.
    root_universe = openmc.Universe(universe_id=0, name='root universe', cells=(main_cell,))

    # Finally we must create a geometry and assign the root universe
    geometry = openmc.Geometry()
    geometry.root_universe = root_universe
    geometry.export_to_xml()

    # Now let's define our simulation parameters. These will go into our
    # settings.xml via the SettingsFile object.
    batches = 300
    inactive = 30
    particles = 100000


    # Instantiate a SettingsFile
    settings_file = openmc.Settings()
    settings_file.run_mode = 'eigenvalue'
    settings_file.cross_sections = '/software/openmc/data/v0.12pre-3/lanl_endfb80/cross_sections.xml'
    settings_file.batches = batches
    settings_file.inactive = inactive
    settings_file.particles = particles
    settings_file.material_cell_offsets = False
    settings_file.temperature = {'method' : 'interpolation'}

    source = openmc.Source()
    ll = [-Assembly_pitch/4, -Assembly_pitch/4, Z_min]
    ur = [Assembly_pitch/4, Assembly_pitch/4, Z_max]
    source.space = openmc.stats.Box(ll, ur)
    source.strength = 1.0
    settings_file.source = source

    #lower_left, upper_right = main_cell.region.bounding_box

    settings_file.export_to_xml()

    # Create a plots.xml file
    radius=Assembly_pitch/math.sqrt(3)
    p1 = openmc.Plot()
    p1.origin = (0, 0, (Z_max-Z_min)/2)
    p1.width = (radius*2, radius*2)
    p1.pixels = (2000, 2000)
    p1.color = 'mat'
    p1.basis = 'xy'
    p1.color_by = 'material'
    p1.col_spec = {
        fuel.id: (255, 0, 0),
        buffer.id: (255, 100, 0),
        PyC1.id: (0, 200, 100),
        PyC2.id: (200, 200, 0),
        sic.id: (200, 200, 200),
        matrix.id: (100, 100, 100),
        yh2.id: (20, 200, 50),
        boro_ctr.id: (200, 20, 50),
        boro.id: (120,150,120),
        shell_mod.id: (150,150,150),
        coolant.id: (180,110,150),
        refl.id: (80,210,50)
    }
    p2 = openmc.Plot()
    p2.origin = (0, 0, (Z_max-Z_min)/2)
    p2.width = (radius*2, Z_max)
    p2.pixels = (200, 2000)
    p2.color = 'mat'
    p2.basis ='yz'
    p2.color_by = 'material'
    p2.col_spec = {
        fuel.id: (255, 0, 0),
        buffer.id: (255, 100, 0),
        PyC1.id: (0, 200, 100),
        PyC2.id: (200, 200, 0),
        sic.id: (200, 200, 200),
        matrix.id: (100, 100, 100),
        yh2.id: (20, 200, 50),
        boro_ctr.id: (200, 20, 50),
        boro.id: (120,150,120),
        shell_mod.id: (150,150,150),
        coolant.id: (180,110,150),
        refl.id: (80,210,50)
    }
    p3 = openmc.Plot()
    p3.origin = (0, 0, (Z_max-1))
    p3.width = (radius*2, radius*2)
    p3.pixels = (2000, 2000)
    p3.color = 'mat'
    p3.basis = 'xy'
    p3.color_by = 'material'
    p3.col_spec = {
        fuel.id: (255, 0, 0),
        buffer.id: (255, 100, 0),
        PyC1.id: (0, 200, 100),
        PyC2.id: (200, 200, 0),
        sic.id: (200, 200, 200),
        matrix.id: (100, 100, 100),
        yh2.id: (20, 200, 50),
        boro_ctr.id: (200, 20, 50),
        boro.id: (120,150,120),
        shell_mod.id: (150,150,150),
        coolant.id: (180,110,150),
        refl.id: (80,210,50)
    }
    plots = openmc.Plots()
    plots.append(p1)
    plots.append(p2)
    plots.append(p3)
    plots.export_to_xml()

    # Run OpenMC in plotting mode and convert resulting image
    openmc.plot_geometry()

    # Run OpenMC
    openmc.run(threads=num_cpu)



build_openmc_model()
