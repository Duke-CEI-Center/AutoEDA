#!/usr/bin/env python3

from typing import Optional
import subprocess
import pathlib
import datetime
import os
import logging
import sys
import argparse                    
from fastapi import FastAPI
from pydantic import BaseModel

# Setup logging and paths
ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_ROOT = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs")))
LOG_ROOT.mkdir(exist_ok=True)
LOG_DIR = LOG_ROOT / "placement"            
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_ROOT / "pl_api.log"), 
        logging.StreamHandler(sys.stdout),
    ],
)

class PlReq(BaseModel):
    design: str
    tech: str = "FreePDK45"
    impl_ver: str
    restore_enc: str
    force: bool = False
    top_module: Optional[str] = None

    # User input parameters (previously from CSV)
    # Global parameters (from imp_global.csv)
    design_flow_effort: str = "standard"  # express, standard
    design_power_effort: str = "none"     # none, medium, high
    target_util: float = 0.7              # target utilization

    # Placement parameters (from placement.csv)
    place_global_timing_effort: str = "medium"   # low, medium, high
    place_global_cong_effort: str = "medium"     # low, medium, high
    place_detail_wire_length_opt_effort: str = "medium"  # low, medium, high
    place_global_max_density: float = 0.9        # max density
    place_activity_power_driven: bool = False    # power driven placement
    prects_opt_max_density: float = 0.8          # pre-CTS optimization density
    prects_opt_power_effort: str = "low"         # none, low, medium, high
    prects_opt_reclaim_area: bool = False        # reclaim area during optimization
    prects_fix_fanout_load: bool = False         # fix fanout load violations

class PlResp(BaseModel):
    status: str
    log_path: str
    report: str
    tcl_path: str = ""

def parse_top_from_config(cfg: pathlib.Path) -> str:
    """Parse TOP_NAME from config.tcl file"""
    if not cfg.exists():
        return ""
    for line in cfg.read_text().splitlines():
        if line.strip().startswith("set TOP_NAME"):
            return line.split('"')[1]
    return ""

def generate_complete_placement_tcl(req: PlReq, result_dir: pathlib.Path, restore_enc: pathlib.Path, top_name: str) -> pathlib.Path:
    """Generate a complete placement TCL script with all necessary configurations"""
    
    # Read design config
    design_config_path = ROOT / "designs" / req.design / "config.tcl"
    design_config_content = ""
    if design_config_path.exists():
        design_config_content = design_config_path.read_text()
    
    # Read tech config
    tech_tcl_path = ROOT / "scripts" / req.tech / "tech.tcl"
    tech_content = ""
    if tech_tcl_path.exists():
        tech_content = tech_tcl_path.read_text()
    
    # Read placement script
    placement_script_path = ROOT / "scripts" / req.tech / "backend" / "4_place.tcl"
    placement_content = ""
    if placement_script_path.exists():
        placement_content = placement_script_path.read_text()
    
    # Get synthesis results directory
    syn_ver = req.impl_ver.split("__", 1)[0]
    syn_res_dir = ROOT / "designs" / req.design / req.tech / "synthesis" / syn_ver / "results"
    
    # Define template variables for replacement
    template_variables = {
        "${TOP_NAME}": top_name,
        "$TOP_NAME": top_name,
        "${env(TOP_NAME)}": top_name,
        "$env(TOP_NAME)": top_name,
        "${BASE_DIR}": str(ROOT),
        "$BASE_DIR": str(ROOT),
        "${env(BASE_DIR)}": str(ROOT),
        "$env(BASE_DIR)": str(ROOT),
        "${NETLIST_DIR}": str(syn_res_dir),
        "$NETLIST_DIR": str(syn_res_dir),
        "${env(NETLIST_DIR)}": str(syn_res_dir),
        "$env(NETLIST_DIR)": str(syn_res_dir),
        "${design_flow_effort}": req.design_flow_effort,
        "$design_flow_effort": req.design_flow_effort,
        "${env(design_flow_effort)}": req.design_flow_effort,
        "$env(design_flow_effort)": req.design_flow_effort,
        "${design_power_effort}": req.design_power_effort,
        "$design_power_effort": req.design_power_effort,
        "${env(design_power_effort)}": req.design_power_effort,
        "$env(design_power_effort)": req.design_power_effort,
        "${target_util}": str(req.target_util),
        "$target_util": str(req.target_util),
        "${env(target_util)}": str(req.target_util),
        "$env(target_util)": str(req.target_util),
        "${place_global_timing_effort}": req.place_global_timing_effort,
        "$place_global_timing_effort": req.place_global_timing_effort,
        "${env(place_global_timing_effort)}": req.place_global_timing_effort,
        "$env(place_global_timing_effort)": req.place_global_timing_effort,
        "${place_global_cong_effort}": req.place_global_cong_effort,
        "$place_global_cong_effort": req.place_global_cong_effort,
        "${env(place_global_cong_effort)}": req.place_global_cong_effort,
        "$env(place_global_cong_effort)": req.place_global_cong_effort,
        "${place_detail_wire_length_opt_effort}": req.place_detail_wire_length_opt_effort,
        "$place_detail_wire_length_opt_effort": req.place_detail_wire_length_opt_effort,
        "${env(place_detail_wire_length_opt_effort)}": req.place_detail_wire_length_opt_effort,
        "$env(place_detail_wire_length_opt_effort)": req.place_detail_wire_length_opt_effort,
        "${place_global_max_density}": str(req.place_global_max_density),
        "$place_global_max_density": str(req.place_global_max_density),
        "${env(place_global_max_density)}": str(req.place_global_max_density),
        "$env(place_global_max_density)": str(req.place_global_max_density),
        "${place_activity_power_driven}": str(req.place_activity_power_driven).lower(),
        "$place_activity_power_driven": str(req.place_activity_power_driven).lower(),
        "${env(place_activity_power_driven)}": str(req.place_activity_power_driven).lower(),
        "$env(place_activity_power_driven)": str(req.place_activity_power_driven).lower(),
        "${prects_opt_max_density}": str(req.prects_opt_max_density),
        "$prects_opt_max_density": str(req.prects_opt_max_density),
        "${env(prects_opt_max_density)}": str(req.prects_opt_max_density),
        "$env(prects_opt_max_density)": str(req.prects_opt_max_density),
        "${prects_opt_power_effort}": req.prects_opt_power_effort,
        "$prects_opt_power_effort": req.prects_opt_power_effort,
        "${env(prects_opt_power_effort)}": req.prects_opt_power_effort,
        "$env(prects_opt_power_effort)": req.prects_opt_power_effort,
        "${prects_opt_reclaim_area}": str(req.prects_opt_reclaim_area).lower(),
        "$prects_opt_reclaim_area": str(req.prects_opt_reclaim_area).lower(),
        "${env(prects_opt_reclaim_area)}": str(req.prects_opt_reclaim_area).lower(),
        "$env(prects_opt_reclaim_area)": str(req.prects_opt_reclaim_area).lower(),
        "${prects_fix_fanout_load}": str(req.prects_fix_fanout_load).lower(),
        "$prects_fix_fanout_load": str(req.prects_fix_fanout_load).lower(),
        "${env(prects_fix_fanout_load)}": str(req.prects_fix_fanout_load).lower(),
        "$env(prects_fix_fanout_load)": str(req.prects_fix_fanout_load).lower(),
    }
    
    # Apply template variable replacements
    for placeholder, value in template_variables.items():
        tech_content = tech_content.replace(placeholder, value)
    
    for placeholder, value in template_variables.items():
        design_config_content = design_config_content.replace(placeholder, value)
    
    for placeholder, value in template_variables.items():
        placement_content = placement_content.replace(placeholder, value)
    
    # Build environment variables from request parameters
    env_vars = {
        "BASE_DIR": str(ROOT),
        "NETLIST_DIR": str(syn_res_dir),
        "TOP_NAME": top_name,
        "FILE_FORMAT": "verilog",
        "version": "custom",
        "design_flow_effort": req.design_flow_effort,
        "design_power_effort": req.design_power_effort,
        "target_util": str(req.target_util),
        "place_global_timing_effort": req.place_global_timing_effort,
        "place_global_cong_effort": req.place_global_cong_effort,
        "place_detail_wire_length_opt_effort": req.place_detail_wire_length_opt_effort,
        "place_global_max_density": str(req.place_global_max_density),
        "place_activity_power_driven": str(req.place_activity_power_driven).lower(),
        "prects_opt_max_density": str(req.prects_opt_max_density),
        "prects_opt_power_effort": req.prects_opt_power_effort,
        "prects_opt_reclaim_area": str(req.prects_opt_reclaim_area).lower(),
        "prects_fix_fanout_load": str(req.prects_fix_fanout_load).lower(),
    }
    
    # Generate complete TCL content
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    tcl_content = f"""#===============================================================================
# Complete Placement TCL Script
# Generated by MCP EDA Server
# Design: {req.design}
# Tech: {req.tech}
# Implementation Version: {req.impl_ver}
# Generated at: {timestamp}
#===============================================================================

#-------------------------------------------------------------------------------
# Environment Variables Configuration
#-------------------------------------------------------------------------------
"""
    
    # Add environment variables
    for var, value in env_vars.items():
        tcl_content += f'set env({var}) "{value}"\n'
    
    tcl_content += f"""
#-------------------------------------------------------------------------------
# Set Global Variables
#-------------------------------------------------------------------------------
set TOP_NAME "{top_name}"
set FILE_FORMAT "verilog"

#-------------------------------------------------------------------------------
# Create Output Directories
#-------------------------------------------------------------------------------
file mkdir pnr_logs
file mkdir pnr_out
file mkdir pnr_reports
file mkdir pnr_save

#-------------------------------------------------------------------------------
# Design Config (from config.tcl)
#-------------------------------------------------------------------------------
{design_config_content}

#-------------------------------------------------------------------------------
# Technology Configuration (from tech.tcl)
#-------------------------------------------------------------------------------
{tech_content}

#-------------------------------------------------------------------------------
# Restore Design
#-------------------------------------------------------------------------------
restoreDesign "{restore_enc.resolve()}" {top_name}

#===============================================================================
# Placement Script: 4_place.tcl
#===============================================================================

{placement_content}

# Mark completion
exec touch _Done_

"""

    # Write TCL file
    tcl_file = result_dir / f"complete_placement.tcl"
    tcl_file.write_text(tcl_content)
    
    return tcl_file

def setup_placement_workspace(req: PlReq, log_file: pathlib.Path) -> tuple[bool, str, pathlib.Path]:
    """Setup placement workspace directory"""
    
    des_root = ROOT / "designs" / req.design / req.tech
    impl_dir = des_root / "implementation" / req.impl_ver
    
    if not impl_dir.exists():
        return False, "implementation directory not found", impl_dir
    
    # Check if directories exist, create if needed
    required_dirs = ["pnr_logs", "pnr_out", "pnr_reports", "pnr_save"]
    for dir_name in required_dirs:
        dir_path = impl_dir / dir_name
        dir_path.mkdir(exist_ok=True)
    
    # Copy config.tcl if it exists
    config_src = ROOT / "designs" / req.design / "config.tcl"
    config_dst = impl_dir / "config.tcl"
    if config_src.exists() and not config_dst.exists():
        config_dst.write_text(config_src.read_text())
    
    return True, "workspace setup successful", impl_dir

def call_placement_executor(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, req: PlReq, log_file: pathlib.Path) -> tuple[bool, str, dict]:
    """Call placement executor to run the generated TCL"""
    
    executor_path = ROOT / "server" / "placement_Executor.py"
    
    # Get synthesis results directory
    syn_ver = req.impl_ver.split("__", 1)[0]
    syn_res_dir = ROOT / "designs" / req.design / req.tech / "synthesis" / syn_ver / "results"
    
    # Build environment variables
    env = os.environ.copy()
    env.update({
        "BASE_DIR": str(ROOT),
        "NETLIST_DIR": str(syn_res_dir),
        "TOP_NAME": req.top_module or req.design,
        "FILE_FORMAT": "verilog", 
        "version": "custom",
        "design_flow_effort": req.design_flow_effort,
        "design_power_effort": req.design_power_effort,
        "target_util": str(req.target_util),
        "place_global_timing_effort": req.place_global_timing_effort,
        "place_global_cong_effort": req.place_global_cong_effort,
        "place_detail_wire_length_opt_effort": req.place_detail_wire_length_opt_effort,
        "place_global_max_density": str(req.place_global_max_density),
        "place_activity_power_driven": str(req.place_activity_power_driven).lower(),
        "prects_opt_max_density": str(req.prects_opt_max_density),
        "prects_opt_power_effort": req.prects_opt_power_effort,
        "prects_opt_reclaim_area": str(req.prects_opt_reclaim_area).lower(),
        "prects_fix_fanout_load": str(req.prects_fix_fanout_load).lower(),
    })
    
    # Add EDA tool paths
    eda_tool_paths = [
        "/opt/cadence/innovus221/tools/bin",
        "/opt/cadence/genus172/bin"
    ]
    current_path = env.get("PATH", "")
    env["PATH"] = ":".join(eda_tool_paths + [current_path])
    
    # Build executor command
    cmd = [
        "python", str(executor_path),
        "-mode", "placement",
        "-design", req.design,
        "-technode", req.tech,
        "-tcl", str(tcl_file),
        "-workspace", str(workspace_dir)
    ]
    
    if req.force:
        cmd.extend(["-force"])
    
    try:
        with log_file.open("a") as lf:
            lf.write(f"\n=== Starting Placement Executor ===\n")
            lf.write(f"Command: {' '.join(cmd)}\n")
            lf.write(f"Working directory: {workspace_dir}\n")
            lf.flush()
            
            process = subprocess.Popen(
                cmd,
                cwd=workspace_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                shell=False,
                executable=None
            )
            
            # Stream output to log file
            for line in process.stdout:
                lf.write(line)
                lf.flush()
            
            process.wait()
            
            lf.write(f"\n=== Placement Executor completed with return code: {process.returncode} ===\n")
        
        if process.returncode != 0:
            return False, f"Placement executor failed with return code {process.returncode}", {}
        
        # Check for completion marker
        done_file = workspace_dir / "_Done_"
        if not done_file.exists():
            return False, "Placement did not complete successfully (_Done_ file not found)", {}
        
        return True, "Placement completed successfully", {}
        
    except Exception as e:
        return False, f"Error running placement executor: {str(e)}", {}

app = FastAPI(title="MCP · Placement Service")

@app.post("/run", response_model=PlResp)
def run_placement(req: PlReq):
    """Main placement endpoint using server-executor architecture"""
    
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_placement_{ts}.log"
    
    try:
        with log_file.open("w") as lf:
            lf.write(f"=== MCP EDA Placement Service ===\n")
            lf.write(f"Design: {req.design}\n")
            lf.write(f"Tech: {req.tech}\n")
            lf.write(f"Implementation Version: {req.impl_ver}\n")
            lf.write(f"Restore ENC: {req.restore_enc}\n")
            lf.write(f"Force: {req.force}\n")
            lf.write(f"Started at: {datetime.datetime.now()}\n\n")
        
        # Validate restore_enc file
        restore_enc = pathlib.Path(req.restore_enc)
        if not restore_enc.exists():
            return PlResp(
                status="error: restore_enc not found",
                log_path=str(log_file),
                report="",
                tcl_path=""
            )
        
        # Parse TOP_NAME
        cfg_path = ROOT / "designs" / req.design / "config.tcl"
        if req.top_module:
            top_name = req.top_module
        else:
            parsed = parse_top_from_config(cfg_path)
            top_name = parsed if parsed else req.design
        
        # Step 1: Setup workspace
        success, message, workspace_dir = setup_placement_workspace(req, log_file)
        if not success:
            return PlResp(
                status=f"error: {message}",
                log_path=str(log_file),
                report="",
                tcl_path=""
            )
        
        # Step 2: Generate complete TCL
        result_dir = ROOT / "result" / req.design / req.tech
        result_dir.mkdir(parents=True, exist_ok=True)
        
        tcl_file = generate_complete_placement_tcl(req, result_dir, restore_enc, top_name)
        
        with log_file.open("a") as lf:
            lf.write(f"Generated TCL file: {tcl_file}\n")
        
        # Step 3: Call executor
        success, message, result_data = call_placement_executor(tcl_file, workspace_dir, req, log_file)
        
        if not success:
            return PlResp(
                status=f"error: {message}",
                log_path=str(log_file),
                report="",
                tcl_path=str(tcl_file)
            )
        
        # Step 4: Collect report
        report_text = "check_place.out not found"
        rpt_dir = workspace_dir / "pnr_reports"
        rpt_file = rpt_dir / "check_place.out"
        
        if rpt_file.exists():
            report_text = rpt_file.read_text(errors="ignore")
        
        with log_file.open("a") as lf:
            lf.write(f"\n=== Placement Service Completed Successfully ===\n")
            lf.write(f"Completed at: {datetime.datetime.now()}\n")
        
        return PlResp(
            status="ok",
            log_path=str(log_file),
            report=report_text,
            tcl_path=str(tcl_file)
        )
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        with log_file.open("a") as lf:
            lf.write(f"\n=== ERROR ===\n{error_msg}\n")
        
        return PlResp(
            status=f"error: {error_msg}",
            log_path=str(log_file),
            report="",
            tcl_path=""
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PLACEMENT_PORT", 13337)),
        help="listen port (env PLACEMENT_PORT overrides; default 13337)",
    )
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "placement_server:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
    )