#!/usr/bin/env python3

from typing import Optional
import subprocess
import pathlib
import datetime
import os
import logging
import sys
import glob
import gzip
import argparse                        
from fastapi import FastAPI
from pydantic import BaseModel

os.environ["PATH"] = (
    "/opt/cadence/innovus221/tools/bin:"
    "/opt/cadence/genus172/bin:" + os.environ.get("PATH", "")
)

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

BACKEND = ROOT / "scripts" / "FreePDK45" / "backend"

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

def parse_top_from_config(cfg: pathlib.Path) -> str:
    if not cfg.exists():
        return ""
    for line in cfg.read_text().splitlines():
        if line.startswith("set TOP_NAME"):
            return line.split('"')[1]
    return ""

def run(cmd: str, log_file: pathlib.Path, cwd: pathlib.Path, env_extra: dict):
    env = os.environ.copy()
    env.update(env_extra)
    with log_file.open("w") as lf, subprocess.Popen(
        cmd,
        cwd=str(cwd),
        shell=True,
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        executable="/bin/bash",
        env=env,
    ) as proc:
        for line in proc.stdout:
            lf.write(line)
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"command exited {proc.returncode}")

app = FastAPI(title="MCP · CTS Service")

@app.post("/cts/run", response_model=CtsResp)
def cts_run(req: CtsReq):
    des_root = ROOT / "designs" / req.design / req.tech
    impl_dir = des_root / "implementation" / req.impl_ver
    if not impl_dir.exists():
        return CtsResp(status="error: implementation dir not found", log_path="", report="")

    placement_enc = pathlib.Path(req.restore_enc)
    if not placement_enc.exists():
        return CtsResp(status="error: restore_enc not found", log_path="", report="")

    rpt_dir   = impl_dir / "pnr_reports"
    cts_rpt   = rpt_dir / "cts_summary.rpt"
    extra_rpt = rpt_dir / "postcts_opt_max_density.rpt"
    if req.force:
        for rpt in (cts_rpt, extra_rpt):
            if rpt.exists():
                rpt.unlink()

    cfg_path = ROOT / "designs" / req.design / "config.tcl"
    if req.top_module:
        top = req.top_module
    else:
        parsed = parse_top_from_config(cfg_path)
        top = parsed or req.design

    # Set environment variables from user input parameters (replacing CSV reading)
    env = {"BASE_DIR": str(ROOT)}
    
    # Global parameters (mimicking the original CSV structure)
    env["version"] = "custom"  # Add version for compatibility
    env["design_flow_effort"] = req.design_flow_effort
    env["design_power_effort"] = req.design_power_effort
    env["target_util"] = str(req.target_util)
    
    # CTS parameters (mimicking the original CSV structure)
    env["cts_cell_density"] = str(req.cts_cell_density)
    env["cts_clock_gate_buffering_location"] = req.cts_clock_gate_buffering_location
    env["cts_clone_clock_gates"] = str(req.cts_clone_clock_gates).lower()
    env["postcts_opt_max_density"] = str(req.postcts_opt_max_density)
    env["postcts_opt_power_effort"] = req.postcts_opt_power_effort
    env["postcts_opt_reclaim_area"] = str(req.postcts_opt_reclaim_area).lower()
    env["postcts_fix_fanout_load"] = str(req.postcts_fix_fanout_load).lower()
    
    env.update(MANUAL_ENV)
    env.setdefault("TOP_NAME", top)
    env.setdefault("FILE_FORMAT", "verilog")

    cts_tcl    = BACKEND / "5_cts.tcl"
    files_arg  = str(cts_tcl)

    exec_cmd = (
        f'restoreDesign "{placement_enc.resolve()}" {top}; '
        'report_cts > pnr_reports/cts_summary.rpt'
    )

    innovus_cmd = (
        f'innovus -no_gui -batch '
        f'-execute "{exec_cmd}" '
        f'-files "{files_arg}"'
    )

    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_cts_{ts}.log"

    try:
        run(innovus_cmd, log_file, impl_dir, env)
    except Exception as e:
        return CtsResp(status=f"error: {e}", log_path=str(log_file), report="")

    if cts_rpt.exists():
        report_text = cts_rpt.read_text()
    elif extra_rpt.exists():
        report_text = extra_rpt.read_text()
    else:
        report_text = "cts report not found"

    return CtsResp(status="ok", log_path=str(log_file), report=report_text)

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
