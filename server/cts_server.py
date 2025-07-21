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

ROOT    = pathlib.Path(__file__).resolve().parent.parent
# Use environment variable for log path, fallback to local logs directory
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



MANUAL_ENV = {
    "CLKBUF_CELLS": "CLKBUF_X1 CLKBUF_X2 CLKBUF_X3 CLKBUF_X4 CLKBUF_X8",
    "CLKGT_CELLS":  "CLKGT_X1 CLKGT_X2",
}

class CtsReq(BaseModel):
    design:      str
    tech:        str = "FreePDK45"
    impl_ver:    str
    force:       bool = False
    restore_enc: str
    top_module:  Optional[str] = None
    
    # User input parameters (previously from CSV)
    # Global parameters (from imp_global.csv)
    design_flow_effort:  str = "standard"  # express, standard
    design_power_effort: str = "none"      # none, medium, high
    target_util:         float = 0.7       # target utilization
    
    # CTS parameters (from cts.csv)
    cts_cell_density:              float = 0.5      # CTS cell density
    cts_clock_gate_buffering_location: str = "below"  # below, above
    cts_clone_clock_gates:         bool = True      # clone clock gates
    postcts_opt_max_density:       float = 0.8      # post-CTS optimization density
    postcts_opt_power_effort:      str = "low"      # none, low, medium, high
    postcts_opt_reclaim_area:      bool = False     # reclaim area during optimization
    postcts_fix_fanout_load:       bool = False     # fix fanout load violations

class CtsResp(BaseModel):
    status:    str
    log_path:  str
    report:    str
    tcl_path:  str  # Add generated TCL path

def parse_top_from_config(cfg: pathlib.Path) -> str:
    if not cfg.exists():
        return ""
    for line in cfg.read_text().splitlines():
        if line.startswith("set TOP_NAME"):
            return line.split('"')[1]
    return ""

def generate_cts_tcl(req: CtsReq, result_dir: pathlib.Path, restore_enc: pathlib.Path) -> pathlib.Path:
    """Generate complete CTS TCL script by reading templates and filling parameters"""
    
    # Read template file directly
    with open(f"{ROOT}/scripts/FreePDK45/backend/5_cts.tcl", "r") as f:
        cts_content = f.read()
    
    cfg_path = ROOT / "designs" / req.design / "config.tcl"
    if req.top_module:
        top_name = req.top_module
    else:
        parsed = parse_top_from_config(cfg_path)
        top_name = parsed or req.design
    
    # Create complete TCL content: variable definitions + template content
    tcl_content = f"""# Generated CTS TCL Script - {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

# Set design variables
set TOP_NAME "{top_name}"
set FILE_FORMAT "verilog"

# Set environment variables
set env(design_flow_effort) "{req.design_flow_effort}"
set env(design_power_effort) "{req.design_power_effort}"
set env(target_util) "{req.target_util}"
set env(BASE_DIR) "{ROOT}"
set env(TOP_NAME) "{top_name}"
set env(version) "custom"

# CTS parameters
set env(cts_cell_density) "{req.cts_cell_density}"
set env(cts_clock_gate_buffering_location) "{req.cts_clock_gate_buffering_location}"
set env(cts_clone_clock_gates) "{str(req.cts_clone_clock_gates).lower()}"
set env(postcts_opt_max_density) "{req.postcts_opt_max_density}"
set env(postcts_opt_power_effort) "{req.postcts_opt_power_effort}"
set env(postcts_opt_reclaim_area) "{str(req.postcts_opt_reclaim_area).lower()}"
set env(postcts_fix_fanout_load) "{str(req.postcts_fix_fanout_load).lower()}"

# Manual environment variables
set env(CLKBUF_CELLS) "{MANUAL_ENV['CLKBUF_CELLS']}"
set env(CLKGT_CELLS) "{MANUAL_ENV['CLKGT_CELLS']}"

# Create output directories
file mkdir pnr_logs pnr_out pnr_reports pnr_save

# Restore Design from Placement
restoreDesign "{restore_enc}" {top_name}

# CTS phase content
{cts_content}

# Generate CTS report - use timeDesign instead of ambiguous report_cts
timeDesign -postCTS -outDir pnr_reports/cts_time

puts "CTS completed successfully"
"""
    
    tcl_path = result_dir / "cts.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

app = FastAPI(title="MCP · CTS Service")

@app.post("/cts/run", response_model=CtsResp)
def cts_run(req: CtsReq):
    des_root = ROOT / "designs" / req.design / req.tech
    impl_dir = des_root / "implementation" / req.impl_ver
    if not impl_dir.exists():
        return CtsResp(status="error: implementation dir not found", log_path="", report="", tcl_path="")

    placement_enc = pathlib.Path(req.restore_enc)
    if not placement_enc.exists():
        return CtsResp(status="error: restore_enc not found", log_path="", report="", tcl_path="")

    # Create result directory for generated TCL
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = ROOT / "designs" / req.design / "config.tcl"
    if req.top_module:
        top = req.top_module
    else:
        parsed = parse_top_from_config(cfg_path)
        top = parsed or req.design

    try:
        # Step 1: Generate combined TCL script
        tcl_path = generate_cts_tcl(req, result_dir, placement_enc)
        logging.info(f"Generated TCL script: {tcl_path}")
        
        # Step 2: Call executor
        executor_script = ROOT / "server" / "cts_Executor.py"
        
        executor_args = [
            "python3", str(executor_script),
            "-design", req.design,
            "-technode", req.tech,
            "-tcl", str(tcl_path),
            "-impl_dir", str(impl_dir),
            "-restore_enc", str(placement_enc),
            "-top_module", top
        ]
        
        if req.force:
            executor_args.append("-force")
            
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"{req.design}_cts_{ts}.log"
        
        logging.info(f"Calling executor: {' '.join(executor_args)}")
        
        # Execute the CTS executor
        with log_file.open("w") as lf:
            result = subprocess.run(
                executor_args,
                cwd=str(ROOT),
                stdout=lf,
                stderr=subprocess.STDOUT,
                text=True
            )
        
        if result.returncode != 0:
            return CtsResp(
                status=f"error: executor failed with return code {result.returncode}",
                log_path=str(log_file),
                report="",
                tcl_path=str(tcl_path)
            )
        
        # Step 3: Collect results
        rpt_dir = impl_dir / "pnr_reports"
        cts_rpt = rpt_dir / "cts_time"
        timing_rpt = cts_rpt / "timing.rpt" if cts_rpt.exists() and cts_rpt.is_dir() else None
        extra_rpt = rpt_dir / "postcts_opt_max_density.rpt"

        if timing_rpt and timing_rpt.exists():
            report_text = timing_rpt.read_text()
        elif extra_rpt.exists():
            report_text = extra_rpt.read_text()
        else:
            report_text = "cts timing report not found"

        return CtsResp(
            status="ok", 
            log_path=str(log_file), 
            report=report_text,
            tcl_path=str(tcl_path)
        )
        
    except Exception as e:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"{req.design}_cts_{ts}.log"
        return CtsResp(
            status=f"error: {e}", 
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