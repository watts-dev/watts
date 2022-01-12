[Mesh]
  [loader]
    type = FileMeshGenerator
    file = MP_ss_griffin_exodus.e
    use_for_exodus_restart = true
  []
  [id]
    type = SubdomainElementIDs
    input = loader
    subdomains = 'fuel moderator heat_pipes monolith SS_envelop_HP SS_envelop_Mod axial_reflector'
    material_ids = '1 2 3 4 5 6 7'
    equivalence_ids = '1 2 3 4 5 6 7'
  []
  uniform_refine = 0
[]


[AuxVariables]
  [./Tf]
    initial_condition = 300
    order = CONSTANT
    family = MONOMIAL
  [../]
[]

[Executioner]
  type = Transient

  petsc_options_iname = '-pc_type -pc_hypre_type -ksp_gmres_restart '
  petsc_options_value = 'hypre boomeramg 100'
  line_search = none

  nl_rel_tol = 1e-8
  nl_abs_tol = 1e-9
  l_tol = 1e-2

  picard_rel_tol = 1e-9
  picard_abs_tol = 1e-9
  picard_max_its = 10

  end_time = 2e3 #2e2
  dt = 10
[]

[TransportSystems]
  particle = neutron
  equation_type = transient
  restart_transport_system = true

  G = 11
  VacuumBoundary = '400 500'
  ReflectingBoundary = '301 302 303'

  [diff]
    scheme = CFEM-Diffusion
    family = LAGRANGE
    order = FIRST
    fission_source_as_material = true
    n_delay_groups = 6
  []
[]

[Materials]
  [fuel]
    type = CoupledFeedbackMatIDNeutronicsMaterial
    block = 'fuel moderator heat_pipes monolith SS_envelop_HP SS_envelop_Mod axial_reflector'
    library_file = ../../ISOXML/unitcell_nogap_hom_xml_G11_df_MP.xml
    library_name = unitcell_nogap_hom_xml_G11_df
    isotopes = 'pseudo'
    densities = '1.0'
    plus = 1
    is_meter = true
    grid_names = 'Tfuel'
    grid_variables = 'Tf'
  []
[]

[PowerDensity]
  power = 1.8e3
  power_density_variable = power_density
  integrated_power_postprocessor = integrated_power
[]


[MultiApps]
  [bison]
    type = TransientMultiApp
    positions = '0 0 0'
    input_files  = MP_trN_moose.i
    execute_on = 'timestep_end'
#    no_backup_and_restore = true # to restart from the latest solve of the multiapp (for pseudo-transient)
  []
[]

[Transfers]
  [to_sub_power_density]
    type = MultiAppProjectionTransfer
    direction = to_multiapp
    multi_app = bison
    variable = power_density
    source_variable = power_density
    execute_on = 'initial timestep_end'
    displaced_source_mesh = false
    displaced_target_mesh = false
    use_displaced_mesh = false
  []
  [from_sub_temp]
    type = MultiAppInterpolationTransfer
    direction = from_multiapp
    multi_app = bison
    variable = Tf
    source_variable = Tfuel
    execute_on = 'initial timestep_end'
    displaced_source_mesh = false
    displaced_target_mesh = false
    use_displaced_mesh = false
    num_points = 1 # interpolate with one point (~closest point)
    power = 0 # interpolate with constant function
  []
[]

[Postprocessors]
  [scaled_power_avg]
    type = ElementAverageValue
    block = fuel
    variable = power_density
    execute_on = 'initial timestep_end'
  []
  [fuel_temp_avg]
    type = ElementAverageValue
    variable = Tf
    block = fuel
    execute_on = 'initial timestep_end'
  []
  [fuel_temp_max]
    type = ElementExtremeValue
    value_type = max
    variable = Tf
    block = fuel
    execute_on = 'initial timestep_end'
  []
  [fuel_temp_min]
    type = ElementExtremeValue
    value_type = min
    variable = Tf
    block = fuel
    execute_on = 'initial timestep_end'
  []
[]

[Debug]
  check_boundary_coverage = false
  print_block_volume = false
  show_actions = false
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
[]
