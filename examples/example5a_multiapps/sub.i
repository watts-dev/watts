[Problem]
  solve = false
[]

[Mesh]
  [gen]
    type = GeneratedMeshGenerator
    dim = 2
  []
[]

[Functions]
  [swell_func]
    type = ParsedFunction
    value = '(temp/2000.0)^2.0'
    vars = 'temp'
    vals = 'temp_pp'
  []
[]

[Postprocessors]
  [temp_pp]
    type = Receiver
    default = 1000.0
  []
  [swell_strain]
    type = FunctionValuePostprocessor
    function = swell_func
    execute_on = 'initial timestep_end'
  []
[]

[Executioner]
   type = Transient
   end_time = 10
   dt = 1
[]
