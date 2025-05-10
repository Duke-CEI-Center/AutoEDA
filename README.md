# Digital Design Implementation Flow

This repository contains scripts and configurations for running a complete digital design implementation flow using Synopsys Design Compiler for synthesis and Cadence Innovus for physical implementation.

## Prerequisites

- Synopsys Design Compiler
- Cadence Innovus
- Python 3.x
- FreePDK45 technology library

## Repository Structure

The repository is organized as follows:

- `designs/`: Contains design source files and implementation results
  - `des/`: Example design directory containing RTL sources and implementation outputs
    - `rtl/`: RTL sources
    - `synthesis/`: Synthesis results
    - `implementation/`: Physical implementation results

- `libraries/`: Technology library files
  - `FreePDK45/`: FreePDK45 technology node files.

- `config/`: Configuration files for different main stages of the flow
  - `synthesis.csv`: Design Compiler synthesis settings
  - `imp_global.csv`: Global implementation settings
  - `placement.csv`: Placement optimization settings
  - `cts.csv`: Clock tree synthesis settings

- `scripts/`: Flow control scripts
  - `run_synthesis_example.sh`: Script to run synthesis
  - `run_implementation_example.sh`: Script to run physical implementation
  - `_helper/`: Python helper scripts for configuration management
  - `FreePDK45/`: Technology-specific TCL scripts for tool execution
    - `tech.tcl`: Technology setup and constraints
    - `frontend/`: Synthesis scripts
      - `1_setup.tcl`: Design setup and constraints
      - `2_synthesis.tcl`: Synthesis commands and optimization
    - `backend/`: Physical implementation scripts
      - `1_setup.tcl`: Design setup and initialization
      - `2_floorplan.tcl`: Floorplanning commands
      - `3_powerplan.tcl`: Power grid generation
      - `4_place.tcl`: Placement optimization
      - `5_cts.tcl`: Clock tree synthesis
      - `6_add_filler.tcl`: Filler cell insertion
      - `7_route.tcl`: Routing and optimization
      - `8_save_design.tcl`: Final design saving

## Flow Overview

The implementation flow consists of two main stages:
1. **Synthesis** using Synopsys Design Compiler (dc_shell)
2. **Physical Implementation** using Cadence Innovus

Each stage has multiple sub-stages implemented through TCL scripts. The flow is controlled by Python wrapper scripts that parse configurations from CSV files and execute the TCL scripts.

## Running the Flow

All bash/python scripts should be executed from the root directory of the repository.

### Synthesis

To run synthesis, use the `run_synthesis_example.sh` script:

```bash
./scripts/run_synthesis_example.sh
```

The script takes the following arguments:
- `--design`: Design name (default: "des")
- `--version-idx`: Index of synthesis configuration to use (default: 0)
- `--tech`: Technology library (default: "FreePDK45")

### Physical Implementation

To run physical implementation, use the `run_implementation_example.sh` script:

```bash
./scripts/run_implementation_example.sh
```

The script takes the following arguments:
- `-d`: Design name (default: "des")
- `-s`: Synthesis version (e.g., "cpV1_clkP1_drcV1")
- `-t`: Technology library (default: "FreePDK45")
- `-g`: Global implementation version index
- `-p`: Placement version index
- `-c`: CTS version index

## Example Configuration Selection

To run a complete flow with specific configurations:

1. Choose a synthesis configuration from `synthesis.csv` (e.g., "cpV1_clkP1_drcV1")
2. Select global implementation settings from `imp_global.csv` (e.g., "VsnU80")
3. Choose placement settings from `placement.csv` (e.g., "V1")
4. Select CTS settings from `cts.csv` (e.g., "V1")

Then run the implementation script with these selections:

```bash
./scripts/run_implementation_example.sh -d des -s cpV1_clkP1_drcV1 -t FreePDK45 -g 0 -p 0 -c 0
```

## Configuration Parameters Reference

This section outlines the key parameters available in each stage of the digital design implementation flow.

### Synthesis Flow (Design Compiler)

#### Setup Stage (`1_setup.tcl`)

**Purpose**: Initialize environment, set design parameters, and prepare for synthesis.

**Key Parameters**:
| Parameter | Description | TCL Command |
|-----------|-------------|-------------|
| `compile_seqmap_propagate_constants` | Controls optimization of constant registers | `set compile_seqmap_propagate_constants true/false` |
| `power_cg_auto_identify` | Enables automatic clock gate identification | `set power_cg_auto_identify true/false` |
| `hdlin_check_no_latch` | Controls latch checking in RTL | `set hdlin_check_no_latch true/false` |
| `hdlin_vrlg_std` | Verilog standard version | `set hdlin_vrlg_std 2001/2005` |

#### Synthesis Stage (`2_synthesis.tcl`)

**Purpose**: Perform RTL-to-gate-level synthesis with timing, area, and power optimizations.

**Key Parameters**:
| Parameter | Description | TCL Command |
|-----------|-------------|-------------|
| `clk_period` | Target clock period for synthesis (ns) | `create_clock -period $env(clk_period)` |
| `DRC_max_fanout` | Maximum allowable fanout | `set_max_fanout $env(DRC_max_fanout) $TOP_NAME` |
| `DRC_max_transition` | Maximum allowable transition time (ns) | `set_max_transition $env(DRC_max_transition) $TOP_NAME` |
| `DRC_max_capacitance` | Maximum allowable capacitance (pF) | `set_max_capacitance $env(DRC_max_capacitance) $TOP_NAME` |
| `compile_cmd` | Compilation command ('compile' or 'compile_ultra') | Various compile commands |
| `map_effort` | Mapping effort level | `compile -map_effort $env(map_effort)` |
| `power_effort` | Power optimization effort level | `compile -power_effort $env(power_effort)` |
| `area_effort` | Area optimization effort level | `compile -area_effort $env(area_effort)` |
| `set_dyn_opt` | Dynamic optimization setting | Part of optimization strategy |
| `set_lea_opt` | Leakage optimization setting | Part of optimization strategy |

### Physical Implementation Flow (Innovus)

#### Modular Physical Implementation Approach

The physical implementation flow can be broken down into distinct stages that can be called iteratively:
1. **Setup**: Initialize the design environment and import netlists
2. **Floorplan**: Define the chip boundaries and I/O pin locations
3. **Power Planning**: Create power distribution network
4. **Placement**: Place standard cells
5. **Clock Tree Synthesis (CTS)**: Build the clock distribution network
6. **Filler Cell Insertion**: Add filler cells
7. **Routing**: Connect the cells with wires
8. **Save Design**: Save final design and generate output files

#### Setup Stage (`1_setup.tcl`)

**Purpose**: Initialize environment, import design, set up libraries and analysis views.

**Key Parameters**:
| Parameter | Description | TCL Command |
|-----------|-------------|-------------|
| `design_flow_effort` | Flow effort level ('express'/'standard') | `setDesignMode -flowEffort $env(design_flow_effort)` |
| `design_power_effort` | Power optimization effort level | `setDesignMode -powerEffort $env(design_power_effort)` |

#### Floorplan Stage (`2_floorplan.tcl`)

**Purpose**: Create the floorplan, define chip boundaries, and place I/O pins.

**Key Parameters**:
| Parameter | Description | TCL Command |
|-----------|-------------|-------------|
| `ASPECT_RATIO` | Die aspect ratio | `floorPlan -site FreePDK45_38x28_10R_NP_162NW_34O -r ${ASPECT_RATIO} ${TARGET_UTIL}` |
| `target_util` | Target utilization | `floorPlan -site FreePDK45_38x28_10R_NP_162NW_34O -r ${ASPECT_RATIO} ${TARGET_UTIL}` |

#### Power Planning Stage (`3_powerplan.tcl`)

**Purpose**: Create power distribution network.

**Key Parameters**:
| Parameter | Description | TCL Command |
|-----------|-------------|-------------|
| Stripe width | Width of power stripes | `addStripe -nets {VDD VSS} -width 1.8` |
| Stripe spacing | Spacing between stripes | `addStripe -nets {VDD VSS} -spacing 1.8` |
| Metal layers | Metal layers for power distribution | `addStripe -layer M4 -direction vertical/horizontal` |

#### Placement Stage (`4_place.tcl`)

**Purpose**: Place standard cells and perform pre-CTS optimization.

**Key Parameters**:
| Parameter | Description | TCL Command |
|-----------|-------------|-------------|
| `place_global_timing_effort` | Global timing-driven placement effort | `setPlaceMode -place_global_timing_effort $env(place_global_timing_effort)` |
| `place_global_cong_effort` | Global congestion-driven placement effort | `setPlaceMode -place_global_cong_effort $env(place_global_cong_effort)` |
| `place_detail_wire_length_opt_effort` | Wire length optimization effort | `setPlaceMode -place_detail_wire_length_opt_effort $env(place_detail_wire_length_opt_effort)` |
| `place_global_max_density` | Maximum density constraint | `setPlaceMode -place_global_max_density $env(place_global_max_density)` |
| `place_activity_power_driven` | Power-driven placement flag | `setPlaceMode -activity_power_driven $env(place_activity_power_driven)` |
| `prects_opt_max_density` | Maximum density for pre-CTS optimization | `setOptMode -maxDensity $env(prects_opt_max_density)` |
| `prects_opt_power_effort` | Power optimization effort | `setOptMode -powerEffort $env(prects_opt_power_effort)` |
| `prects_opt_reclaim_area` | Area reclaim flag | `setOptMode -reclaimArea $env(prects_opt_reclaim_area)` |
| `prects_fix_fanout_load` | Fix fanout load flag | `setOptMode -fixFanoutLoad $env(prects_fix_fanout_load)` |

#### Clock Tree Synthesis Stage (`5_cts.tcl`)

**Purpose**: Build and optimize the clock distribution network.

**Key Parameters**:
| Parameter | Description | TCL Command |
|-----------|-------------|-------------|
| Buffer cells | Clock buffer cell types | `set_ccopt_property buffer_cells $CLKBUF_CELLS` |
| Clock gating cells | Clock gating cell types | `set_ccopt_property clock_gating_cells $CLKGT_CELLS` |
| `cts_cell_density` | Cell density for CTS | `set_ccopt_property cell_density $env(cts_cell_density)` |
| `cts_clock_gate_buffering_location` | Location for clock gate buffers | `set_ccopt_property clock_gate_buffering_location $env(cts_clock_gate_buffering_location)` |
| `cts_clone_clock_gates` | Clock gate cloning flag | `set_ccopt_property clone_clock_gates $env(cts_clone_clock_gates)` |
| `postcts_opt_max_density` | Maximum density for post-CTS optimization | `setOptMode -maxDensity $env(postcts_opt_max_density)` |
| `postcts_opt_power_effort` | Power optimization effort | `setOptMode -powerEffort $env(postcts_opt_power_effort)` |
| `postcts_opt_reclaim_area` | Area reclaim flag | `setOptMode -reclaimArea $env(postcts_opt_reclaim_area)` |
| `postcts_fix_fanout_load` | Fix fanout load flag | `setOptMode -fixFanoutLoad $env(postcts_fix_fanout_load)` |

#### Filler Cell Insertion (`6_add_filler.tcl`)

**Purpose**: Add filler cells to improve power distribution and DRC compliance. *This is currently not implemented.*

**Key Parameters**:
| Parameter | Description | TCL Command |
|-----------|-------------|-------------|
| Filler cell types | Types of cells used for filling | `addFiller -cell $FILL_CELLS -prefix FILLER` |
| Prefix | Prefix for filler cell names | `addFiller -cell $FILL_CELLS -prefix FILLER` |

#### Routing Stage (`7_route.tcl`)

**Purpose**: Perform global and detailed routing with optimization.

**Key Parameters**:
| Parameter | Description | TCL Command |
|-----------|-------------|-------------|
| `routeWithTimingDriven` | Routing timing-driven mode flag | `setNanoRouteMode -routeWithTimingDriven false/true` |
| `routeDesignFixClockNets` | Fix clock nets during routing | `setNanoRouteMode -routeDesignFixClockNets true/false` |
| `SIAware` | Signal integrity awareness | `setDelayCalMode -SIAware True/False` |
| DRC limit | Limit for DRC checking | `verify_drc -limit <value>` |

#### Save Design Stage (`8_save_design.tcl`)

**Purpose**: Save final design and generate output files.

## Configuration Files

The flow uses several CSV configuration files located in the `config/` directory to control tool settings:

### synthesis.csv
Controls Design Compiler synthesis settings:
- Clock period
- DRC constraints (max fanout, transition, capacitance)
- Compilation effort levels (power, area, mapping)
- Optimization settings

### imp_global.csv
Controls global Innovus implementation settings:
- Design flow effort (express/standard)
- Power optimization effort
- Target utilization

### placement.csv
Controls Innovus placement settings:
- Global timing and congestion effort
- Wire length optimization
- Density constraints
- Power-driven placement
- Pre-CTS optimization settings

### cts.csv
Controls clock tree synthesis settings:
- Cell density
- Clock gate buffering location
- Clock gate cloning
- Post-CTS optimization settings

