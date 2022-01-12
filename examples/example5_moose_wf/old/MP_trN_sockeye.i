# NEAMS Micro-Reactor Application Driver
# Two-phase model
# TODO's
#  - Potassium properties, check with Sockeye
#  
# Notes for user experience:
#  - Similarly named variables in HeatPipe2Phase and HeatPipeBlackbox
#  - Explain that widths, materials are from inside out
#  - Flag which variables are used only for analytic limits
#  - Variable "length" (singular) but "widths" plural

# Total heat removed/added to heat pipe
#Q_core = 2.0e6 # W
#number_of_hp = ${fparse 30*37}
#Q_hp = ${fparse Q_core/number_of_hp}
#Q_hp = 1800.

# Wick characteristics
R_pore = 15.0e-6
D_h_pore = ${fparse 2.0 * R_pore}
permeability = 2e-9
porosity =  0.70

# Envelope ("env")
# SS316. Incropera & DeWitt, 3rd ed, Table A.1 @ 900K (627C)
# Density (kg/m3)
rho_env = 8238.
# Thermal conductivity (W/m-K)
k_env = 23.05
# Specific heat capacity (J/kg-K)
cp_env = 589.

# Potassium thermophysical properties determined using Sockeye's FluidPropertiesInterrogator.
# Using T = 800 K, p_sat = 6379 Pa
# Estimated saturated conditions by iteratively providing  
# FluidPropertiesInterrogator with values of saturated density @ p_sat = 6379 Pa
# and checking that the resulting phase temperature was near 800K.
# Potassium vapor
# Density (kg/m3)
rho_vapor = 0.039
# Effective "super" conductivity (W/m-K)
# NOT from FluidPropertiesInterrogator
k_vapor = 1.30e6
# Specific heat capacity (J/kg-K)
cp_vapor = 1078.

# Potassium liquid
# Density (kg/m3)
rho_liquid = 720
# Thermal conductivity (W/m-K)
k_liquid = 37.03
# Specific heat capacity (J/kg-K)
cp_liquid = 786.
# Melting point, Table 3.1, lists 62C, rounding up
T_melting = 340.

# Wick, homogenize envelope and fluid
# Density (kg/m3)
rho_wick = ${fparse porosity * rho_liquid + (1.0 - porosity) * rho_env}
# Thermal conductivity (W/m-K)
k_wick = ${fparse porosity * k_liquid + (1.0 - porosity) * k_env}
# Specific heat capacity (J/kg-K)
# From Table 1.1, no temperature data given
cp_wick = ${fparse porosity * cp_liquid + (1.0 - porosity) * cp_env}

# Elevations and lengths
length_evap = 180.0e-2
length_adia =  30.0e-2
length_cond =  90.0e-2

# Mesh density
# The dimensions are nicely divisible by 3 cm mesh.
nelem_evap = 180
nelem_adia =  30
nelem_cond =  90

# Envelope thickness
t_env = 0.08e-2
# Liquid annulus thickness
t_ann = 0.07e-2
# Wick thickness
t_wick = 0.1e-2

# Radial geometry
# Envelope outer
R_hp_o = 1.05e-2
D_hp_o = ${fparse 2.0 * R_hp_o}
# Inner Envelope/outer annulus
R_hp_i = ${fparse R_hp_o - t_env}
D_hp_i = ${fparse 2.0 * R_hp_i}
# Inner annulus/wick outer
R_wick_o = ${fparse R_hp_i - t_ann}
D_wick_o = ${fparse 2.0 * R_wick_o}
# Inner wick/vapor core outer
R_wick_i = ${fparse R_wick_o - t_wick}
D_wick_i = ${fparse 2.0 * R_wick_i}

# BCs for condenser:
# Option A: From SPR report (INL/EXT-17-43212 R1) Appendix E Table 16
# This was based on an INL study on energy conversion system optons.
#T_ext_cond = 725.
#htc_ext_cond = 326.
# Option B: Convective BC that approximately sets the condenser wall temperature
# to T_ext_cond. This is consistent with the N. Stauff ANS Summary 2021.
T_ext_cond = 800.
#htc_ext_cond = 326.
htc_ext_cond = 1.0e6

# Evaporator parameters
#S_evap = ${fparse pi * D_hp_o * length_evap}
#q_evap = ${fparse Q_hp / S_evap}

[FluidProperties]
  [./fp_2phase]
    type = PotassiumTwoPhaseFluidProperties
    emit_on_nan = none
  [../]
[]

[Components]
  [./hp]
    type = HeatPipeConduction

    # Common to both HeatPipe2Phase and HeatPipeConduction
    position = '0 0 0'
    orientation = '0 0 1'
    length = '${length_evap} ${length_adia} ${length_cond}'
    n_elems = '${nelem_evap} ${nelem_adia} ${nelem_cond}'
    gravity_vector = '0 0 -9.8'
    D_wick_i = ${D_wick_i}
    D_wick_o = ${D_wick_o}
    D_clad_i = ${D_hp_i}
    R_pore = ${R_pore}
    porosity = ${porosity}
    permeability = ${permeability}

    # HeatPipeConduction only
    # Dimensions (for heat transfer & analytic limits)
    axial_region_names = 'evap adia cond'
    L_evap = ${length_evap}
    L_adia = ${length_adia}
    L_cond = ${length_cond}
    D_clad_o = ${D_hp_o}
    D_h_pore = ${D_h_pore}
    # Radial Mesh
    n_elems_clad = 4
    n_elems_wick = 8
    n_elems_core = 10
    # Thermal conductivity
    k_clad = ${k_env}
    k_wick = ${k_wick}
    k_core = ${k_vapor}
    k_eff = ${k_wick}
    # Density
    rho_clad = ${rho_env}
    rho_wick = ${rho_wick}
    rho_core = ${rho_vapor}
    # Specific heat
    cp_clad = ${cp_env}
    cp_wick = ${cp_wick}
    cp_core = ${cp_vapor}
    #
    fp_2phase = fp_2phase
    evaporator_at_start_end = true
    # Initial temperature of block
    #initial_T = ${T_ext_cond} # no initial condition for restarted calculations!!
    # Melting temperature (hard limit on minimum coolant temperature)
    T_operating = ${T_melting}
  [../]

  [condenser_boundary]
    type = HSBoundaryAmbientConvection
    boundary = 'hp:cond:outer'
    hs = hp
    T_ambient = ${T_ext_cond}
    htc_ambient = ${htc_ext_cond} #large value to approach an effective DirichletBC
    # JWT: ? bc_scale_pp = 1.0, so this seems to be a way of actually turning off
    # the heat rate limiting feature
    scale_pp = bc_scale_pp
  []
  [evaporator_boundary]
    type = HSBoundaryHeatFlux
    boundary = 'hp:evap:outer'
    hs = hp
    q = flux_vf
  []
[]

[AuxKernels]
  [./hp_var]
    type = FunctionAux
    function = hp_ax1_vf
    variable = hp_temp_aux
  [../]
[]

[Functions]
  [hp_ax1_vf]
    type = VectorPostprocessorFunction
    argument_column = z
    component  = z
    value_column = T_solid
    vectorpostprocessor_name = hp_ax1
  []
  [flux_vf]
    type = VectorPostprocessorFunction
    argument_column = z
    component  = z
    value_column = master_flux
    vectorpostprocessor_name = flux_vpp
  []
  # JWT: ? Not sure if this is used
  # JWT:? Is "heat_flux" from the code? It's not from the input file.
  #[scaled_heat_flux_fcn]
  #  type = ParsedFunction
  #  vars = 'heat_flux scale_fcn'
  #  vals = 'evaporator_boundary:integral scale_fcn'
  #  value = 'heat_flux * scale_fcn'
  #[]
  [scale_fcn]
    type = ParsedFunction
    vars = 'catastrophic_pp recoverable_pp operational_pp'
    vals = 'catastrophic_pp recoverable_pp operational_pp'
    value = 'catastrophic_pp*recoverable_pp*operational_pp'
  []
[]

[AuxVariables]
  [T_wall_var]
    # initial_condition = ${T_ext_cond} # no initial condition for restarted calculations!!
  []
  [operational_aux]
    # initial_condition = 1# no initial condition for restarted calculations!!
  []
  [master_flux]
    #initial_condition = ${q_evap} # no initial condition for restarted calculations!!
  []
  [hp_temp_aux]
    #initial_condition = ${T_ext_cond} # no initial condition for restarted calculations!!
  []
[]

[Postprocessors]
  [./Integral_BC_Total]
    type = SumPostprocessor
    values = 'condenser_boundary:integral evaporator_boundary:integral'
    execute_on = 'INITIAL TIMESTEP_END'
  [../]
  [./ZeroPP]
    type = EmptyPostprocessor
  [../]
  [./Integral_BC_Cond]
    type = DifferencePostprocessor
    value1 = ZeroPP
    value2 = condenser_boundary:integral
    execute_on = 'INITIAL TIMESTEP_END'
  [../]
  [./Integral_BC_RelErr]
    type = RelativeDifferencePostprocessor
    value1 = evaporator_boundary:integral
    value2 = Integral_BC_Cond
    execute_on = 'INITIAL TIMESTEP_END'
  [../]
  [bc_scale_pp]
    type = FunctionValuePostprocessor
    function = 1.0
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [operational_pp]
    type = ElementAverageValue
    variable = operational_aux
    execute_on = 'initial timestep_begin TIMESTEP_END'
  []
  # JWT:? Not sure if this gets used
  #[scaled_heat_flux]
  #  type = FunctionValuePostprocessor
  #  function = scaled_heat_flux_fcn
  #  execute_on = 'initial timestep_end'
  #[]
  # JWT: ? If we want to actually use the limits (i.e. bc_scale_pp is not just 1.0),
  # then we probably need to set limit_condenser_side = true.
  [catastrophic_pp]
    type = HeatRemovalRateLimitScale
    heat_addition_pps = 'evaporator_boundary:integral'
    limit_condenser_side = false
    catastrophic_heat_removal_limit_pps = 'hp:boiling_limit hp:capillary_limit '
                                          'hp:entrainment_limit'
    recoverable_heat_removal_limit_pps = ''
    T_operating = ${T_melting}
    T = T_inner_avg
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [recoverable_pp]
    type = HeatRemovalRateLimitScale
    heat_addition_pps = 'evaporator_boundary:integral'
    limit_condenser_side = false
    catastrophic_heat_removal_limit_pps = ''
    recoverable_heat_removal_limit_pps = 'hp:sonic_limit hp:viscous_limit'
    T_operating = ${T_melting}
    T = T_inner_avg
    execute_on = 'INITIAL linear nonlinear TIMESTEP_END'
  []
  [T_evap_inner]
    type = NodalExtremeValue
    boundary = hp:evap:inner
    variable = T_solid
    execute_on = 'INITIAL TIMESTEP_END'
    value_type = max
  []
  [T_cond_inner]
    type = NodalExtremeValue
    boundary = hp:cond:inner
    variable = T_solid
    execute_on = 'INITIAL TIMESTEP_END'
    value_type = min
  []
  [T_evap_outer]
    type = NodalExtremeValue
    boundary = hp:evap:outer
    variable = T_solid
    execute_on = 'INITIAL TIMESTEP_END'
    value_type = max
  []
  [T_cond_outer]
    type = NodalExtremeValue
    boundary = hp:cond:outer
    variable = T_solid
    execute_on = 'INITIAL TIMESTEP_END'
    value_type = min
  []
  [T_wall_var_avg]
    type = ElementAverageValue
    variable = T_wall_var
    execute_on = 'Initial timestep_end'
  []
  [T_inner_avg]
    type = SideAverageValue
    variable = T_solid
    boundary = hp:inner
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [T_inner_max]
    type = NodalExtremeValue
    variable = T_solid
    boundary = hp:inner
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [T_inner_min]
    type = NodalExtremeValue
    variable = T_solid
    boundary = hp:inner
    execute_on = 'INITIAL TIMESTEP_END'
    value_type = min
  []
  [./DT_outer]
    type = DifferencePostprocessor
    value1 = T_evap_outer
    value2 = T_cond_outer
    execute_on = 'INITIAL TIMESTEP_END'
  [../]
  [./DT_inner]
    type = DifferencePostprocessor
    value1 = T_evap_inner
    value2 = T_cond_inner
    execute_on = 'INITIAL TIMESTEP_END'
  [../]
  [scale_pp]
    type = FunctionValuePostprocessor
    function = scale_fcn
  []
[]

[VectorPostprocessors]
  [hp_ax1]
    type = SideValueSampler
    variable = T_solid
    boundary = 'hp:evap:outer'
    sort_by = z
    execute_on = 'timestep_begin TIMESTEP_END'
  []
  [./env_vpp]
    type = NodalValueSampler
    variable = T_solid
    block = 'hp:clad'
    sort_by = z
    execute_on = 'INITIAL TIMESTEP_END'
  [../]
  [./core_vpp]
    type = NodalValueSampler
    variable = T_solid
    block = 'hp:core'
    sort_by = z
    execute_on = 'INITIAL TIMESTEP_END'
  [../]
  [flux_vpp]
    type = SideValueSampler
    variable = master_flux
    boundary = 'hp:evap:inner'
    sort_by = z
    execute_on = 'timestep_begin TIMESTEP_END'
  []
[]

[Preconditioning]
  [./pc]
    type = SMP
    full = true
  [../]
[]

[Executioner]
  type = Transient

  solve_type = NEWTON
  petsc_options_iname = '-pc_type'
  petsc_options_value = 'lu'
  scheme = bdf2
  line_search = none

  # ensure nl_abs_tol >> nl_rel_tol
  nl_abs_tol = 1e-4
  nl_rel_tol = 1e-6
  nl_max_its = 15

  l_tol = 1e-3
  l_max_its = 10

  # Topher uses these, Lander does not
  # WARNING: If you uncomment these lines, Sockeye will claim to be converged to a 
  # garbage solution where the evaporator and condenser BC integrals are off by an
  # order of magnitude!
  #automatic_scaling = true
  #compute_scaling_once = false

  start_time = 0 # negative start time so we can start running from t = 0
  end_time = 2e3
  dtmin = 1e-6
  dt = 10
[]

[Outputs]
  [./console]
    type = Console
    max_rows = 5
    execute_postprocessors_on = 'INITIAL FINAL FAILED'
  [../]
  [./csv]
    type = CSV
    execute_on = 'INITIAL TIMESTEP_END FINAL FAILED'
    execute_vector_postprocessors_on = 'INITIAL FINAL FAILED'
  [../]
  [exodus]
    type = Exodus
    output_material_properties = true
    show_material_properties = 'T_solid'
  []
[]

#[Debug]
  # show_var_residual_norms = true
#[]
