# Official Template for Floorplan TCL Code

create_floorplan -design des -top_module des3 -technology FreePDK45 -impl_version cpV1 -syn_version cpV1_clkP1_drcV1 -grid_index 0 -process_index 0

set_fp -name des_fp
set_fp -die_area 10000 10000
set_fp -core_area 8000 8000
set_fp -utilization 0.8
set_fp -core_utilization 0.9

set_fp -power_ring -left 100 -right 100 -top 100 -bottom 100
set_fp -power_ring -width 10
set_fp -power_ring -space 10

set_fp -core_ring -left 50 -right 50 -top 50 -bottom 50
set_fp -core_ring -width 5
set_fp -core_ring -space 5

set_fp -core_boundary -left 10 -right 10 -top 10 -bottom 10

set_fp -power_mesh -width 5
set_fp -power_mesh -space 5

set_fp -core_mesh -width 2
set_fp -core_mesh -space 2

set_fp -power_strip -width 5
set_fp -power_strip -space 5

set_fp -core_strip -width 2
set_fp -core_strip -space 2

set_fp -power_via -size 2
set_fp -core_via -size 1

set_fp -power_pin -width 5
set_fp -core_pin -width 2

set_fp -power_ring -left 100 -right 100 -top 100 -bottom 100
set_fp -power_ring -width 10
set_fp -power_ring -space 10

set_fp -core_ring -left 50 -right 50 -top 50 -bottom 50
set_fp -core_ring -width 5
set_fp -core_ring -space 5

set_fp -core_boundary -left 10 -right 10 -top 10 -bottom 10

set_fp -power_mesh -width 5
set_fp -power_mesh -space 5

set_fp -core_mesh -width 2
set_fp -core_mesh -space 2

set_fp -power_strip -width 5
set_fp -power_strip -space 5

set_fp -core_strip -width 2
set_fp -core_strip -space 2

set_fp -power_via -size 2
set_fp -core_via -size 1

set_fp -power_pin -width 5
set_fp -core_pin -width 2

set_fp -power_ring -left 100 -right 100 -top 100 -bottom 100
set_fp -power_ring -width 10
set_fp -power_ring -space 10

set_fp -core_ring -left 50 -right 50 -top 50 -bottom 50
set_fp -core_ring -width 5
set_fp -core_ring -space 5

set_fp -core_boundary -left 10 -right 10 -top 10 -bottom 10

set_fp -power_mesh -width 5
set_fp -power_mesh -space 5

set_fp -core_mesh -width 2
set_fp -core_mesh -space 2

set_fp -power_strip -width 5
set_fp -power_strip -space 5

set_fp -core_strip -width 2
set_fp -core_strip -space 2

set_fp -power_via -size 2
set_fp -core_via -size 1

set_fp -power_pin -width 5
set_fp -core_pin -width 2

set_fp -power_ring -left 100 -right 100 -top 100 -bottom 100
set_fp -power_ring -width 10
set_fp -power_ring -space 10

set_fp -core_ring -left 50 -right 50 -top 50 -bottom 50
set_fp -core_ring -width 5
set_fp -core_ring -space 5

set_fp -core_boundary -left 10 -right 10 -top 10 -bottom 10

set_fp -power_mesh -width 5
set_fp -power_mesh -space 5

set_fp -core_mesh -width 2
set_fp -core_mesh -space 2

set_fp -power_strip -width 5
set_fp -power_strip -space 5

set_fp -core_strip -width 2
set_fp -core_strip -space 2

set_fp -power_via -size 2
set_fp -core_via -size 1

set_fp -power_pin -width 5
set_fp -core_pin -width 2

commit_floorplan