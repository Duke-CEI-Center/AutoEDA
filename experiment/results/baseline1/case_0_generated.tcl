# Set design name
set design des

# Set top module
set top_module des3

# Set technology
set tech FreePDK45

# Set implementation version
set impl_version cpV1

# Set synthesis version
set syn_version cpV1_clkP1_drcV1

# Set grid index
set grid_index 0

# Set process index
set process_index 0

# Create floorplan
create_floorplan -design $design -top_module $top_module -technology $tech -impl_version $impl_version -syn_version $syn_version -grid_index $grid_index -process_index $process_index

# Assign input/output ports
add_io -port_name input_port -port_type input
add_io -port_name output_port -port_type output

# Save floorplan
save_floorplan -design $design -top_module $top_module -technology $tech -impl_version $impl_version -syn_version $syn_version -grid_index $grid_index -process_index $process_index -file "floorplan.fp"