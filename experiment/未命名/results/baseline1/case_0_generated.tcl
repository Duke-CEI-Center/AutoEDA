# Set design and technology
set_design des
set_technology FreePDK45

# Set implementation and synthesis versions
set_implementation_version cpV1
set_synthesis_version cpV1_clkP1_drcV1

# Set grid and process index
set_grid_index 0
set_process_index 0

# Create floorplan
create_floorplan -name des_fp

# Set top module
set_top_module des3

# Add input/output ports
add_ports -direction input -ports {port1 port2}
add_ports -direction output -ports {port3 port4}

# Save floorplan
save_floorplan -overwrite

# Exit
exit