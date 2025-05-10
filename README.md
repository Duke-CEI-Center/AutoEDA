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
1. Synthesis using Design Compiler
2. Physical Implementation using Innovus

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

## Environment Setup

The implementation script requires specific library paths for Innovus. Make sure the following environment variables are set:
- `LD_LIBRARY_PATH` should include Innovus library paths
- Required Cadence tool installations should be in the correct locations
