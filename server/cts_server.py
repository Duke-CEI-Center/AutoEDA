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

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_ROOT = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs")))
LOG_ROOT.mkdir(exist_ok=True)
LOG_DIR = LOG_ROOT / "cts"           
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_ROOT / "cts_api.log"), 
        logging.StreamHandler(sys.stdout),
    ],
)

class CtsReq(BaseModel):
    design: str
    tech: str = "FreePDK45"
    impl_ver: str
    force: bool = False
    restore_enc: str
    top_module: Optional[str] = None

    # User input parameters (previously from CSV)
    # Global parameters (from imp_global.csv)
    design_flow_effort: str = "standard"  # express, standard
    design_power_effort: str = "none"      # none, medium, high
    target_util: float = 0.7       # target utilization

    # CTS parameters (from cts.csv)
    cts_cell_density: float = 0.5      # CTS cell density
    cts_clock_gate_buffering_location: str = "below"  # below, above
    cts_clone_clock_gates: bool = True      # clone clock gates
    postcts_opt_max_density: float = 0.8      # post-CTS optimization density
    postcts_opt_power_effort: str = "low"      # none, low, medium, high
    postcts_opt_reclaim_area: bool = False     # reclaim area during optimization
    postcts_fix_fanout_load: bool = False     # fix fanout load violations

class CtsResp(BaseModel):
    status: str
    log_path: str
    report: str
    tcl_path: str

def parse_top_from_config(cfg: pathlib.Path) -> str:
    """Parse TOP_NAME from config.tcl file"""
    if not cfg.exists():
        return ""
    for line in cfg.read_text().splitlines():
        if line.startswith("set TOP_NAME"):
            return line.split('"')[1]
    return ""

def generate_complete_cts_tcl(req: CtsReq, result_dir: pathlib.Path) -> pathlib.Path:
    """Generate complete CTS TCL script with all components combined"""
    result_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse top name from config.tcl
    cfg_path = ROOT / "designs" / req.design / "config.tcl"
    if req.top_module:
        top_name = req.top_module
    else:
        parsed = parse_top_from_config(cfg_path)
        top_name = parsed or req.design

    # Read design config
    design_config_content = ""
    if cfg_path.exists():
        design_config_content = cfg_path.read_text()

    # Read tech config
    tech_config_path = ROOT / "scripts" / req.tech / "tech.tcl"
    tech_content = ""
    if tech_config_path.exists():
        tech_content = tech_config_path.read_text()

    # Read CTS backend script
    backend_script_path = ROOT / "scripts" / req.tech / "backend" / "5_cts.tcl"
    backend_content = ""
    if backend_script_path.exists():
        backend_content = backend_script_path.read_text()

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
        "${cts_cell_density}": str(req.cts_cell_density),
        "$cts_cell_density": str(req.cts_cell_density),
        "${env(cts_cell_density)}": str(req.cts_cell_density),
        "$env(cts_cell_density)": str(req.cts_cell_density),
        "${cts_clock_gate_buffering_location}": req.cts_clock_gate_buffering_location,
        "$cts_clock_gate_buffering_location": req.cts_clock_gate_buffering_location,
        "${env(cts_clock_gate_buffering_location)}": req.cts_clock_gate_buffering_location,
        "$env(cts_clock_gate_buffering_location)": req.cts_clock_gate_buffering_location,
        "${cts_clone_clock_gates}": str(req.cts_clone_clock_gates).lower(),
        "$cts_clone_clock_gates": str(req.cts_clone_clock_gates).lower(),
        "${env(cts_clone_clock_gates)}": str(req.cts_clone_clock_gates).lower(),
        "$env(cts_clone_clock_gates)": str(req.cts_clone_clock_gates).lower(),
        "${postcts_opt_max_density}": str(req.postcts_opt_max_density),
        "$postcts_opt_max_density": str(req.postcts_opt_max_density),
        "${env(postcts_opt_max_density)}": str(req.postcts_opt_max_density),
        "$env(postcts_opt_max_density)": str(req.postcts_opt_max_density),
        "${postcts_opt_power_effort}": req.postcts_opt_power_effort,
        "$postcts_opt_power_effort": req.postcts_opt_power_effort,
        "${env(postcts_opt_power_effort)}": req.postcts_opt_power_effort,
        "$env(postcts_opt_power_effort)": req.postcts_opt_power_effort,
        "${postcts_opt_reclaim_area}": str(req.postcts_opt_reclaim_area).lower(),
        "$postcts_opt_reclaim_area": str(req.postcts_opt_reclaim_area).lower(),
        "${env(postcts_opt_reclaim_area)}": str(req.postcts_opt_reclaim_area).lower(),
        "$env(postcts_opt_reclaim_area)": str(req.postcts_opt_reclaim_area).lower(),
        "${postcts_fix_fanout_load}": str(req.postcts_fix_fanout_load).lower(),
        "$postcts_fix_fanout_load": str(req.postcts_fix_fanout_load).lower(),
        "${env(postcts_fix_fanout_load)}": str(req.postcts_fix_fanout_load).lower(),
        "$env(postcts_fix_fanout_load)": str(req.postcts_fix_fanout_load).lower(),

    }

    # Apply template variable replacement
    for var, value in template_variables.items():
        tech_content = tech_content.replace(var, value)
        design_config_content = design_config_content.replace(var, value)
        backend_content = backend_content.replace(var, value)

    # Build environment variables from request parameters
    env_vars = {
        "BASE_DIR": str(ROOT),
        "TOP_NAME": top_name,
        "FILE_FORMAT": "verilog",
        "version": "custom",
        "design_flow_effort": req.design_flow_effort,
        "design_power_effort": req.design_power_effort,
        "target_util": str(req.target_util),
        "cts_cell_density": str(req.cts_cell_density),
        "cts_clock_gate_buffering_location": req.cts_clock_gate_buffering_location,
        "cts_clone_clock_gates": str(req.cts_clone_clock_gates).lower(),
        "postcts_opt_max_density": str(req.postcts_opt_max_density),
        "postcts_opt_power_effort": req.postcts_opt_power_effort,
        "postcts_opt_reclaim_area": str(req.postcts_opt_reclaim_area).lower(),
        "postcts_fix_fanout_load": str(req.postcts_fix_fanout_load).lower(),
        "CLKBUF_CELLS": "CLKBUF_X1 CLKBUF_X2 CLKBUF_X3 CLKBUF_X4 CLKBUF_X8",
        "CLKGT_CELLS": "CLKGT_X1 CLKGT_X2",
    }

    # Build the complete TCL content
    tcl_content = f"""#===============================================================================
# Complete CTS TCL Script
# Generated at: {datetime.datetime.now()}
# Design: {req.design}
# Technology: {req.tech}
# Implementation Version: {req.impl_ver}
#===============================================================================

#-------------------------------------------------------------------------------
# Environment Variables
#-------------------------------------------------------------------------------
"""

    # Add environment variables
    for key, value in env_vars.items():
        tcl_content += f'set env({key}) "{value}"\n'

    tcl_content += f"""

#-------------------------------------------------------------------------------
# Global Variables  
#-------------------------------------------------------------------------------
set start_time [clock seconds]

# Set PDK and library paths
set PDK_DIR $env(BASE_DIR)/libraries/{req.tech}

#-------------------------------------------------------------------------------
# Design Config (from config.tcl)
#-------------------------------------------------------------------------------
{design_config_content}

#-------------------------------------------------------------------------------
# Technology Config (from tech.tcl)
#-------------------------------------------------------------------------------
{tech_content}

#-------------------------------------------------------------------------------
# Restore Design
#-------------------------------------------------------------------------------
restoreDesign "{pathlib.Path(req.restore_enc).resolve()}" {top_name}

#===============================================================================
# CTS Script: 5_cts.tcl
#===============================================================================

{backend_content}

# Mark completion
exec touch _Done_
"""

    # Write the complete TCL file
    tcl_file = result_dir / "complete_cts.tcl"
    tcl_file.write_text(tcl_content)
    
    return tcl_file

def setup_cts_workspace(req: CtsReq, log_file: pathlib.Path) -> tuple[bool, str, pathlib.Path]:
    """Setup CTS workspace directory structure"""
    try:
        des_root = ROOT / "designs" / req.design / req.tech
        impl_dir = des_root / "implementation" / req.impl_ver
        
        if not impl_dir.exists():
            return False, f"Implementation directory not found: {impl_dir}", impl_dir
            
        # Ensure required directories exist
        (impl_dir / "pnr_reports").mkdir(parents=True, exist_ok=True)
        (impl_dir / "pnr_out").mkdir(parents=True, exist_ok=True)
        (impl_dir / "pnr_save").mkdir(parents=True, exist_ok=True)
        
        # Copy config.tcl to implementation directory
        cfg_src = ROOT / "designs" / req.design / "config.tcl"
        cfg_dst = impl_dir / "config.tcl"
        if cfg_src.exists() and not cfg_dst.exists():
            import shutil
            shutil.copy2(cfg_src, cfg_dst)
            
        return True, "Workspace setup completed", impl_dir
        
    except Exception as e:
        return False, f"Failed to setup workspace: {str(e)}", pathlib.Path()

def call_cts_executor(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, req: CtsReq, log_file: pathlib.Path) -> tuple[bool, str, dict]:
    """Call CTS executor via subprocess"""
    try:
        executor_path = ROOT / "server" / "cts_Executor.py"
        
        # Build the command
        cmd = f"python {executor_path} -mode cts -design {req.design} -technode {req.tech} -tcl {tcl_file} -workspace {workspace_dir}"
        
        # Prepare environment variables
        env = os.environ.copy()
        env["BASE_DIR"] = str(ROOT)
        env["TOP_NAME"] = req.top_module or req.design
        env["FILE_FORMAT"] = "verilog"
        env["version"] = "custom"
        env["design_flow_effort"] = req.design_flow_effort
        env["design_power_effort"] = req.design_power_effort
        env["target_util"] = str(req.target_util)
        env["cts_cell_density"] = str(req.cts_cell_density)
        env["cts_clock_gate_buffering_location"] = req.cts_clock_gate_buffering_location
        env["cts_clone_clock_gates"] = str(req.cts_clone_clock_gates).lower()
        env["postcts_opt_max_density"] = str(req.postcts_opt_max_density)
        env["postcts_opt_power_effort"] = req.postcts_opt_power_effort
        env["postcts_opt_reclaim_area"] = str(req.postcts_opt_reclaim_area).lower()
        env["postcts_fix_fanout_load"] = str(req.postcts_fix_fanout_load).lower()
        env["CLKBUF_CELLS"] = "CLKBUF_X1 CLKBUF_X2 CLKBUF_X3 CLKBUF_X4 CLKBUF_X8"
        env["CLKGT_CELLS"] = "CLKGT_X1 CLKGT_X2"
        
        # Add EDA tool paths to PATH
        eda_paths = [
            "/opt/cadence/innovus221/tools/bin",
            "/opt/cadence/genus172/bin",
            "/opt/cadence/innovus191/bin"
        ]
        current_path = env.get("PATH", "")
        env["PATH"] = ":".join(eda_paths + [current_path])
        
        # Execute the command
        with open(log_file, "a") as lf:
            lf.write(f"\n=== CTS Executor Command ===\n")
            lf.write(f"Command: {cmd}\n")
            lf.write(f"Working Directory: {workspace_dir}\n")
            lf.write(f"=== CTS Executor Output ===\n")
            
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=str(workspace_dir),
                env=env,
                capture_output=True,
                text=True,
                executable="/bin/tcsh"
            )
            
            lf.write(result.stdout)
            if result.stderr:
                lf.write(f"STDERR:\n{result.stderr}")
            
            lf.write(f"\n=== CTS Executor completed with return code: {result.returncode} ===\n")
        
        if result.returncode != 0:
            return False, f"CTS executor failed with return code {result.returncode}", {}
            
        # Check for success indicators
        success_indicators = [
            workspace_dir / "_Done_",
            workspace_dir / "pnr_save" / "cts.enc.dat"
        ]
        
        success = any(indicator.exists() for indicator in success_indicators)
        if not success:
            return False, "CTS did not complete successfully (_Done_ file not found)", {}
            
        return True, "CTS completed successfully", {}
        
    except Exception as e:
        return False, f"Failed to execute CTS: {str(e)}", {}

app = FastAPI(title="MCP · CTS Service")

@app.post("/run", response_model=CtsResp)
def run_cts(req: CtsReq):
    """Main CTS endpoint"""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_cts_{ts}.log"
    
    try:
        with open(log_file, "w") as lf:
            lf.write(f"=== CTS Service Started ===\n")
            lf.write(f"Design: {req.design}\n")
            lf.write(f"Technology: {req.tech}\n")
            lf.write(f"Implementation Version: {req.impl_ver}\n")
            lf.write(f"Force: {req.force}\n")
            lf.write(f"Restore ENC: {req.restore_enc}\n")
            lf.write(f"Started at: {datetime.datetime.now()}\n\n")
        
        # Step 1: Setup workspace
        success, message, workspace_dir = setup_cts_workspace(req, log_file)
        if not success:
            return CtsResp(status=f"error: {message}", log_path=str(log_file), report="", tcl_path="")
        
        # Step 2: Check restore file exists
        restore_path = pathlib.Path(req.restore_enc)
        if not restore_path.exists():
            return CtsResp(status="error: restore_enc file not found", log_path=str(log_file), report="", tcl_path="")
        
        # Step 3: Generate complete CTS TCL
        result_dir = ROOT / "result" / req.design / req.tech
        tcl_file = generate_complete_cts_tcl(req, result_dir)
        
        # Step 4: Call CTS executor
        success, message, _ = call_cts_executor(tcl_file, workspace_dir, req, log_file)
        if not success:
            return CtsResp(status=f"error: {message}", log_path=str(log_file), report="", tcl_path=str(tcl_file))
        
        # Step 5: Generate report
        rpt_dir = workspace_dir / "pnr_reports"
        cts_rpt = rpt_dir / "cts_summary.rpt"
        extra_rpt = rpt_dir / "postcts_opt_max_density.rpt"
        
        if cts_rpt.exists():
            report_text = cts_rpt.read_text()
        elif extra_rpt.exists():
            report_text = extra_rpt.read_text()
        else:
            report_text = "CTS report not found"
        
        with open(log_file, "a") as lf:
            lf.write(f"\n=== CTS Service Completed Successfully ===\n")
            lf.write(f"Completed at: {datetime.datetime.now()}\n")
        
        return CtsResp(
            status="ok",
            log_path=str(log_file),
            report=report_text,
            tcl_path=str(tcl_file)
        )
        
    except Exception as e:
        with open(log_file, "a") as lf:
            lf.write(f"\n=== CTS Service Failed ===\n")
            lf.write(f"Error: {str(e)}\n")
            lf.write(f"Failed at: {datetime.datetime.now()}\n")
        
        return CtsResp(
            status=f"error: {str(e)}",
            log_path=str(log_file),
            report="",
            tcl_path=""
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("CTS_PORT", 13338)),
        help="listen port (env CTS_PORT overrides; default 13338)",
    )
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "cts_server:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
    )