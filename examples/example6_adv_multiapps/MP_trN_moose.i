sockeye_subapp_cli_args = 'nelem_evap=${sockeye_nelem_evap};nelem_adia=${sockeye_nelem_adia};nelem_cond=${sockeye_nelem_cond}'

num_sides = 24 # number of sides of heat pipe as a result of mesh polygonization
alpha = ${fparse 2 * pi / num_sides}
perimeter_correction = ${fparse 0.5 * alpha / sin(0.5 * alpha)} # polygonization correction factor for perimeter
area_correction = 1.0 # trivial value for non-corrected mesh
normal_factor = ${fparse perimeter_correction / area_correction}

[Problem]
   register_objects_from = 'SockeyeApp'
   library_path = ${raw ${env SOCKEYE_DIR}lib}
   restart_file_base = ${raw ${env SS_PATH}/MOOSE_out_bison0_cp/LATEST}
   force_restart = true
[]

[Mesh]
  file = ${raw ${env SS_PATH}/MOOSE_out_bison0_cp/LATEST}
[]

[Variables]
  [temp]
  []
[]

[Kernels]
  [heat_conduction]
    type = HeatConduction
    variable = temp
  []
  [heat_ie]
    type = HeatConductionTimeDerivative
    variable = temp
  []
  [heat_source_fuel]
    type = CoupledForce
    variable = temp
    block = fuel
    v = power_density
  []
[]

[AuxVariables]
  [power_density]
    block = fuel
    family = L2_LAGRANGE
    order = FIRST
  []
  [Tfuel]
    block = fuel
  []
  [hp_temp_aux]
    block = 'hp_airgap_g hp_airgap_r'
  []
  [flux_uo] #auxvariable to hold heat pipe surface flux from UserObject
    order = CONSTANT
    family = MONOMIAL
  []
[]

[AuxKernels]
  [assign_tfuel]
    type = NormalizationAux
    variable = Tfuel
    source_variable = temp
    execute_on = 'initial timestep_end'
  []
  [flux_uo]
    type = SpatialUserObjectAux
    variable = flux_uo
    user_object = flux_uo
  []
[]


[BCs]
  [outside_bc]
    type = ConvectiveFluxFunction # (Robin BC)
    variable = temp
    boundary = 'top_Bison bottom'
    coefficient = ${outside_htc} # W/K/m^2
    T_infinity = ${infinit_temperature} # K air temperature at the top of the core 800
  []
  [hp_temp]
    type = MatchedValueBC
    boundary = 'hp_graphite_in hp_reflector_in'
    variable = temp
    v = hp_temp_aux
  []
[]


[Materials]
  [fuel_matrix_thermal]
    type = HeatConductionMaterial
    block = 'fuel'
    temp = temp
    thermal_conductivity = 35.8 # W/m/K at 300k
    specific_heat = 716.4 # at 300k
  []
  [monolith_matrix_thermal]
    type = HeatConductionMaterial
    block = 'monolith'
    temp = temp
    thermal_conductivity = 54 # W/m/K at 300k
    specific_heat = 903 # at 300k
  []
  [moderator_thermal]
    type = HeatConductionMaterial
    block = 'moderator'
    temp = temp
    thermal_conductivity = 20 # W/m/K
    specific_heat = 500 # random value
  []
  [SS_envelop_pipes_thermal]
    type = HeatConductionMaterial
    block = 'SS_envelop'
    thermal_conductivity = 13.8 # W/m/K at 300k
    specific_heat = 482.9 # at 300k
  []
  [airgap_thermal]
    type = HeatConductionMaterial
    block = 'hp_airgap_g hp_airgap_r moderator_airgap_in_1 moderator_airgap_out_1 moderator_airgap_in_2 moderator_airgap_out_2 moderator_airgap_in_3 moderator_airgap_out_3'
    temp = temp
    thermal_conductivity = 0.15 # W/m/K
    specific_heat = 5197 # random value
  []
  [axial_reflector_thermal]
    type = HeatConductionMaterial
    block = 'upper_reflector downer_reflector'
    temp = temp
    thermal_conductivity = 199 # W/m/K
    specific_heat = 1867 # random value
  []
  [fuel_density]
    type = Density
    block = fuel
    density = 2276.5
  []
  [moderator_density]
    type = Density
    block = moderator
    density = 4.3e3
  []
  [monolith_density]
    type = Density
    block = 'monolith'
    density = 1806
  []
  [SS_Envelop_density]
    type = Density
    block = 'SS_envelop'
    density = 7950
  []
  [airgap_density]
    type = Density
    block = 'hp_airgap_g hp_airgap_r moderator_airgap_in_1 moderator_airgap_out_1 moderator_airgap_in_2 moderator_airgap_out_2 moderator_airgap_in_3 moderator_airgap_out_3'
    density = 180
  []
  [axial_reflector_density]
    type = Density
    block = 'upper_reflector downer_reflector'
    density = 1848
  []
[]

[MultiApps]
  [sockeye]
    type = TransientMultiApp
    positions = '0.0 0 0.2' #bottom of the heat pipe
    input_files = 'MP_trN_sockeye.i'
    execute_on = 'timestep_begin' # execute on timestep begin because hard to have a good initial guess on heat flux
    max_procs_per_app = 1
    sub_cycling = true
    cli_args = ${sockeye_subapp_cli_args}
  []
[]

[Transfers]
  [from_sockeye_temp]
    type = MultiAppNearestNodeTransfer
   	direction = from_multiapp
   	multi_app = sockeye
   	source_variable = hp_temp_aux
   	variable = hp_temp_aux
    execute_on = 'timestep_begin'
  []
  [to_sockeye_flux]
    type = MultiAppNearestNodeTransfer
    direction = to_multiapp
    multi_app = sockeye
    source_variable = flux_uo
    variable = master_flux
    execute_on = 'timestep_begin'
  []
[]

[UserObjects]
  [flux_uo]
    type = LayeredSideFluxAverage
    direction = z
    num_layers = 25
    variable = temp
    diffusivity = ${fparse 0.15/normal_factor}
    execute_on = linear
    boundary = 'hp_graphite_in hp_reflector_in'
  []
[]

[Executioner]
  type = Transient

  petsc_options_iname = '-pc_type -pc_factor_mat_solver_package -ksp_gmres_restart'
  petsc_options_value = 'lu       superlu_dist                  51'
  line_search = 'none'

  nl_abs_tol = 1e-7
  nl_rel_tol = 1e-7

  end_time = 10
  dt = 1
[]

[Postprocessors]
  [hp_heat_integral]
    type = SideFluxIntegral
    variable = temp
    boundary = 'hp_graphite_in hp_reflector_in'
  	diffusivity = ${fparse 0.15/normal_factor}
  	execute_on = 'initial timestep_end'
  []
  [topbottom_heat_integral]
    type = SideFluxIntegral
    variable = temp
    boundary = 'top_Bison bottom'
    diffusivity = 199 #TC of reflector
	execute_on = 'initial timestep_end'
  []
  [total_heat_integral]
    type = LinearCombinationPostprocessor
    pp_names = 'hp_heat_integral topbottom_heat_integral'
	pp_coefs = '1 1'
  []
  [fuel_temp_avg]
    type = ElementAverageValue
    variable = temp
    block = fuel
  []
  [fuel_temp_max]
    type = ElementExtremeValue
    variable = temp
    block = fuel
  []
  [fuel_temp_min]
    type = ElementExtremeValue
    variable = temp
    block = fuel
    value_type = min
  []
  [mod_temp_avg]
    type = ElementAverageValue
    variable = temp
    block = moderator
  []
  [mod_temp_max]
    type = ElementExtremeValue
    variable = temp
    block = moderator
  []
  [mod_temp_min]
    type = ElementExtremeValue
    variable = temp
    block = moderator
    value_type = min
  []
  [monolith_temp_avg]
    type = ElementAverageValue
    variable = temp
    block = monolith
  []
  [monolith_temp_max]
    type = ElementExtremeValue
    variable = temp
    block = monolith
  []
  [monolith_temp_min]
    type = ElementExtremeValue
    variable = temp
    block = monolith
    value_type = min
  []
  [heatpipe_surface_temp_avg]
    type = SideAverageValue
    variable = temp
    boundary = 'hp_graphite_in hp_reflector_in'
  []
  [power_density]
    type = ElementIntegralVariablePostprocessor
    block = fuel
    variable = power_density
    execute_on = 'initial timestep_end'
  []
[]

[Outputs]
  interval = 1
  [exodus]
    type = Exodus
  []
  [csv]
    type = CSV
  []
  perf_graph = true
  color = true
  checkpoint = true
[]
