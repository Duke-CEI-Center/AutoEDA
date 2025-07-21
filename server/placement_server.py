#!/usr/bin/env python3

from typing import Optional
import subprocess, pathlib, datetime, os, logging, sys, argparse   
from fastapi import FastAPI
from pydantic import BaseModel

ROOT     = pathlib.Path(__file__).resolve().parent.parent
# Use environment variable for log path, fallback to local logs directory
LOG_ROOT = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs")))
LOG_ROOT.mkdir(exist_ok=True)
LOG_DIR  = LOG_ROOT / "placement"
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

class PlResp(BaseModel):
    status:     str
    log_path:   str
    report:     str
    tcl_path:   str  # Add generated TCL path

def generate_placement_tcl(req: PlReq, result_dir: pathlib.Path, restore_enc: pathlib.Path) -> pathlib.Path:
    """Generate complete placement TCL script by reading templates and filling parameters"""
    
    # Read template file directly
    with open(f"{ROOT}/scripts/FreePDK45/backend/4_place.tcl", "r") as f:
        placement_content = f.read()
    
    top_name = req.top_module if req.top_module else req.design
    
    # Extract synthesis version from impl_ver for NETLIST_DIR
    syn_ver = req.impl_ver.split("__", 1)[0]
    netlist_dir = ROOT / "designs" / req.design / req.tech / "synthesis" / syn_ver / "results"
    
    # Create complete TCL content: variable definitions + template content
    tcl_content = f"""# Generated Placement TCL Script - {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

# Set design variables
set TOP_NAME "{top_name}"
set FILE_FORMAT "verilog"
set NETLIST_DIR "{netlist_dir}"

# Set environment variables
set env(design_flow_effort) "{req.design_flow_effort}"
set env(design_power_effort) "{req.design_power_effort}"
set env(target_util) "{req.target_util}"
set env(BASE_DIR) "{ROOT}"
set env(TOP_NAME) "{top_name}"

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

# Create output directories
file mkdir pnr_logs pnr_out pnr_reports pnr_save

# Restore Design from Powerplan
restoreDesign "{restore_enc}" {top_name}

# Placement phase content
{placement_content}

puts "Placement completed successfully"
"""
    
    tcl_path = result_dir / "placement.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

app = FastAPI(title="MCP · Placement Service")

@app.post("/place/run", response_model=PlResp)
def place_run(req: PlReq):
    des_root = ROOT / "designs" / req.design / req.tech
    impl_dir = des_root / "implementation" / req.impl_ver
    if not impl_dir.exists():
        return PlResp(status="error: implementation dir not found", log_path="", report="", tcl_path="")

    floor_enc = pathlib.Path(req.restore_enc)
    if not floor_enc.exists():
        return PlResp(status="error: restore_enc not found", log_path="", report="", tcl_path="")

    # Create result directory for generated TCL
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)

    top = req.top_module if req.top_module else req.design

    try:
        # Step 1: Generate combined TCL script
        tcl_path = generate_placement_tcl(req, result_dir, floor_enc)
        logging.info(f"Generated TCL script: {tcl_path}")
        
        # Step 2: Call executor
        executor_script = ROOT / "server" / "placement_Executor.py"
        
        executor_args = [
            "python3", str(executor_script),
            "-design", req.design,
            "-technode", req.tech,
            "-tcl", str(tcl_path),
            "-impl_dir", str(impl_dir),
            "-restore_enc", str(floor_enc),
            "-top_module", top
        ]
        
        if req.force:
            executor_args.append("-force")
            
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"{req.design}_pl_{ts}.log"
        
        logging.info(f"Calling executor: {' '.join(executor_args)}")
        
        # Execute the placement executor
        with log_file.open("w") as lf:
            result = subprocess.run(
                executor_args,
                cwd=str(ROOT),
                stdout=lf,
                stderr=subprocess.STDOUT,
                text=True
            )
        
        if result.returncode != 0:
            return PlResp(
                status=f"error: executor failed with return code {result.returncode}",
                log_path=str(log_file),
                report="",
                tcl_path=str(tcl_path)
            )
        
        # Step 3: Collect results
        enc_path = impl_dir / "pnr_save" / "placement.enc"
        if not enc_path.exists():
            return PlResp(
                status="error: Placement did not produce placement.enc",
                log_path=str(log_file),
                report="",
                tcl_path=str(tcl_path)
            )

        rpt = impl_dir / "pnr_reports" / "check_place.out"
        report_text = rpt.read_text(errors="ignore") if rpt.exists() else "check_place.out not found"

        return PlResp(
            status="ok", 
            log_path=str(log_file), 
            report=report_text,
            tcl_path=str(tcl_path)
        )
        
    except Exception as e:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"{req.design}_pl_{ts}.log"
        return PlResp(
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