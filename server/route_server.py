#!/usr/bin/env python3

from typing import Optional, Dict
import subprocess, pathlib, datetime, os, logging, sys, argparse
from fastapi import FastAPI
from pydantic import BaseModel

ROOT     = pathlib.Path(__file__).resolve().parent.parent
# Use environment variable for log path, fallback to local logs directory
LOG_ROOT = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs")))
LOG_ROOT.mkdir(exist_ok=True)
LOG_DIR  = LOG_ROOT / "route"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_ROOT / "route_api.log"),
        logging.StreamHandler(sys.stdout),
    ],
)



ROUTE_RPTS = [
    "route_summary.rpt",
    "postRoute_drc_max1M.rpt",
    "congestion.rpt",
    "postOpt_drc_max1M.rpt",
    "route_timing.rpt.gz",
]

class RtReq(BaseModel):
    design:      str
    tech:        str = "FreePDK45"
    impl_ver:    str
    restore_enc: str
    force:       bool = False
    top_module:  Optional[str] = None
    
    # User input parameters (previously from CSV)
    # Global parameters (from imp_global.csv)
    design_flow_effort:  str = "standard"  # express, standard
    design_power_effort: str = "none"      # none, medium, high
    target_util:         float = 0.7       # target utilization
    
    # Placement parameters (from placement.csv)
    place_global_timing_effort:      str = "medium"   # low, medium, high
    place_global_cong_effort:        str = "medium"   # low, medium, high
    place_detail_wire_length_opt_effort: str = "medium"  # low, medium, high
    place_global_max_density:        float = 0.9      # max density
    place_activity_power_driven:     bool = False     # power driven placement
    prects_opt_max_density:          float = 0.8      # pre-CTS optimization density
    prects_opt_power_effort:         str = "low"      # none, low, medium, high
    prects_opt_reclaim_area:         bool = False     # reclaim area during optimization
    prects_fix_fanout_load:          bool = False     # fix fanout load violations
    
    # CTS parameters (from cts.csv)
    cts_cell_density:              float = 0.5      # CTS cell density
    cts_clock_gate_buffering_location: str = "below"  # below, above
    cts_clone_clock_gates:         bool = True      # clone clock gates
    postcts_opt_max_density:       float = 0.8      # post-CTS optimization density
    postcts_opt_power_effort:      str = "low"      # none, low, medium, high
    postcts_opt_reclaim_area:      bool = False     # reclaim area during optimization
    postcts_fix_fanout_load:       bool = False     # fix fanout load violations

class RtResp(BaseModel):
    status:    str
    log_path:  str
    rpt_paths: Dict[str, str]
    tcl_path:  str  # Add generated TCL path

def safe_unlink(path: pathlib.Path):
    try:
        path.unlink()
    except FileNotFoundError:
        pass

def parse_top_from_config(cfg: pathlib.Path) -> str:
    if not cfg.exists():
        return ""
    for line in cfg.read_text().splitlines():
        if line.startswith("set TOP_NAME"):
            return line.split('"')[1]
    return ""

def generate_route_tcl(req: RtReq, result_dir: pathlib.Path, restore_enc: pathlib.Path) -> pathlib.Path:
    """Generate complete routing TCL script by reading templates and filling parameters"""
    
    # Read template file directly  
    with open(f"{ROOT}/scripts/FreePDK45/backend/7_route.tcl", "r") as f:
        route_content = f.read()
    
    top_name = req.top_module or parse_top_from_config(ROOT / "designs" / req.design / "config.tcl") or req.design
    
    # Create complete TCL content: variable definitions + template content
    tcl_content = f"""# Generated Routing TCL Script - {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

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

# Placement parameters
set env(place_global_timing_effort) "{req.place_global_timing_effort}"
set env(place_global_cong_effort) "{req.place_global_cong_effort}"
set env(place_detail_wire_length_opt_effort) "{req.place_detail_wire_length_opt_effort}"
set env(place_global_max_density) "{req.place_global_max_density}"
set env(place_activity_power_driven) "{str(req.place_activity_power_driven).lower()}"
set env(prects_opt_max_density) "{req.prects_opt_max_density}"
set env(prects_opt_power_effort) "{req.prects_opt_power_effort}"
set env(prects_opt_reclaim_area) "{str(req.prects_opt_reclaim_area).lower()}"
set env(prects_fix_fanout_load) "{str(req.prects_fix_fanout_load).lower()}"

# CTS parameters
set env(cts_cell_density) "{req.cts_cell_density}"
set env(cts_clock_gate_buffering_location) "{req.cts_clock_gate_buffering_location}"
set env(cts_clone_clock_gates) "{str(req.cts_clone_clock_gates).lower()}"
set env(postcts_opt_max_density) "{req.postcts_opt_max_density}"
set env(postcts_opt_power_effort) "{req.postcts_opt_power_effort}"
set env(postcts_opt_reclaim_area) "{str(req.postcts_opt_reclaim_area).lower()}"
set env(postcts_fix_fanout_load) "{str(req.postcts_fix_fanout_load).lower()}"

# Create output directories
file mkdir pnr_logs pnr_out pnr_reports pnr_save

# Restore Design from CTS
restoreDesign "{restore_enc}" {top_name}

# Routing phase content
{route_content}

puts "Routing completed successfully"
"""
    
    tcl_path = result_dir / "route.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

app = FastAPI(title="MCP · Routing Service")

@app.post("/route/run", response_model=RtResp)
def route_run(req: RtReq):
    des_root = ROOT / "designs" / req.design / req.tech
    impl_dir = des_root / "implementation" / req.impl_ver
    if not impl_dir.exists():
        return RtResp(status="error: implementation dir not found", log_path="", rpt_paths={}, tcl_path="")

    cts_enc = pathlib.Path(req.restore_enc)
    if not cts_enc.exists():
        return RtResp(status="error: restore_enc not found", log_path="", rpt_paths={}, tcl_path="")

    # Create result directory for generated TCL
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)

    top = req.top_module or parse_top_from_config(ROOT / "designs" / req.design / "config.tcl") or req.design

    try:
        # Step 1: Generate combined TCL script
        tcl_path = generate_route_tcl(req, result_dir, cts_enc)
        logging.info(f"Generated TCL script: {tcl_path}")
        
        # Step 2: Call executor
        executor_script = ROOT / "server" / "route_Executor.py"
        
        executor_args = [
            "python3", str(executor_script),
            "-design", req.design,
            "-technode", req.tech,
            "-tcl", str(tcl_path),
            "-impl_dir", str(impl_dir),
            "-restore_enc", str(cts_enc),
            "-top_module", top
        ]
        
        if req.force:
            executor_args.append("-force")
            
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"{req.design}_route_{ts}.log"
        
        logging.info(f"Calling executor: {' '.join(executor_args)}")
        
        # Execute the routing executor
        with log_file.open("w") as lf:
            result = subprocess.run(
                executor_args,
                cwd=str(ROOT),
                stdout=lf,
                stderr=subprocess.STDOUT,
                text=True
            )
        
        if result.returncode != 0:
            return RtResp(
                status=f"error: executor failed with return code {result.returncode}",
                log_path=str(log_file),
                rpt_paths={},
                tcl_path=str(tcl_path)
            )
        
        # Step 3: Collect results
        rpt_dir = impl_dir / "pnr_reports"
        rpt_paths = {r: (rpt_dir / r).exists() and str((rpt_dir / r).relative_to(ROOT)) or "not found"
                     for r in ROUTE_RPTS}

        return RtResp(
            status="ok", 
            log_path=str(log_file), 
            rpt_paths=rpt_paths,
            tcl_path=str(tcl_path)
        )
        
    except Exception as e:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"{req.design}_route_{ts}.log"
        return RtResp(
            status=f"error: {e}", 
            log_path=str(log_file), 
            rpt_paths={},
            tcl_path=""
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int,
                        default=int(os.getenv("ROUTE_PORT", 13339)),
                        help="listen port (env ROUTE_PORT overrides; default 13339)")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run("route_server:app", host="0.0.0.0", port=args.port, reload=False)