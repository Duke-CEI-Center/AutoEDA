#!/usr/bin/env python3

from typing import Optional
import subprocess, pathlib, datetime, os, logging, sys, gzip, glob, argparse
from fastapi import FastAPI
from pydantic import BaseModel

ROOT      = pathlib.Path(__file__).resolve().parent.parent
# Use environment variable for log path, fallback to local logs directory
LOG_ROOT  = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs")))
LOG_ROOT.mkdir(exist_ok=True)
LOG_DIR   = LOG_ROOT / "powerplan"            
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_ROOT / "pwr_api.log"), 
        logging.StreamHandler(sys.stdout),
    ],
)



class PwrReq(BaseModel):
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

class PwrResp(BaseModel):
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

def generate_powerplan_tcl(req: PwrReq, result_dir: pathlib.Path, restore_enc: pathlib.Path) -> pathlib.Path:
    """Generate complete powerplan TCL script by reading templates and filling parameters"""
    
    # Read template file directly
    with open(f"{ROOT}/scripts/FreePDK45/backend/3_powerplan.tcl", "r") as f:
        powerplan_content = f.read()
    
    top_name = req.top_module if req.top_module else req.design
    
    # Create complete TCL content: variable definitions + template content  
    tcl_content = f"""# Generated Powerplan TCL Script - {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

# Set design variables
set TOP_NAME "{top_name}"
set FILE_FORMAT "verilog"

# Set environment variables
set env(design_flow_effort) "{req.design_flow_effort}"
set env(design_power_effort) "{req.design_power_effort}"
set env(target_util) "{req.target_util}"
set env(BASE_DIR) "{ROOT}"

# Create output directories
file mkdir pnr_logs pnr_out pnr_reports pnr_save

# Restore Design from Floorplan
restoreDesign "{restore_enc}" {top_name}

# Powerplan phase content
{powerplan_content}

puts "Powerplan completed successfully"
"""
    
    tcl_path = result_dir / "powerplan.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

app = FastAPI(title="MCP · Power-plan Service")

@app.post("/power/run", response_model=PwrResp)
def powerplan(req: PwrReq):
    des_root = ROOT / "designs" / req.design / req.tech
    impl_dir = des_root / "implementation" / req.impl_ver
    if not impl_dir.exists():
        return PwrResp(status="error: implementation dir not found", log_path="", report="", tcl_path="")

    floor_enc = pathlib.Path(req.restore_enc)
    if not floor_enc.exists():
        return PwrResp(status="error: floorplan.enc.dat not found", log_path="", report="", tcl_path="")

    # Create result directory for generated TCL
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = ROOT / "designs" / req.design / "config.tcl"
    if req.top_module:
        top = req.top_module
    else:
        parsed = parse_top_from_config(cfg_path)
        top = parsed if parsed else req.design

    try:
        # Step 1: Generate combined TCL script
        tcl_path = generate_powerplan_tcl(req, result_dir, floor_enc)
        logging.info(f"Generated TCL script: {tcl_path}")
        
        # Step 2: Call executor
        executor_script = ROOT / "server" / "powerplan_Executor.py"
        
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
        log_file = LOG_DIR / f"{req.design}_pwr_{ts}.log"
        
        logging.info(f"Calling executor: {' '.join(executor_args)}")
        
        # Execute the powerplan executor
        with log_file.open("w") as lf:
            result = subprocess.run(
                executor_args,
                cwd=str(ROOT),
                stdout=lf,
                stderr=subprocess.STDOUT,
                text=True
            )
        
        if result.returncode != 0:
            return PwrResp(
                status=f"error: executor failed with return code {result.returncode}",
                log_path=str(log_file),
                report="",
                tcl_path=str(tcl_path)
            )
        
        # Step 3: Collect results
        rpt_dir  = impl_dir / "pnr_reports"
        rpt_file = rpt_dir / "powerplan.rpt"
        
        report_text = "powerplan.rpt(.gz) not found"
        if rpt_file.exists():
            report_text = rpt_file.read_text(errors="ignore")
        else:
            for cand in glob.glob(str(rpt_dir / "powerplan.rpt*")):
                p = pathlib.Path(cand)
                if p.suffix == ".gz":
                    with gzip.open(p, "rt") as f:
                        report_text = f.read()
                else:
                    report_text = p.read_text(errors="ignore")
                break

        # Check if powerplan.enc was created
        power_enc_path = impl_dir / "pnr_save" / "powerplan.enc"
        if not power_enc_path.exists():
            return PwrResp(
                status="error: Powerplan did not produce powerplan.enc",
                log_path=str(log_file),
                report=report_text,
                tcl_path=str(tcl_path)
            )

        return PwrResp(
            status="ok", 
            log_path=str(log_file), 
            report=report_text,
            tcl_path=str(tcl_path)
        )
        
    except Exception as e:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"{req.design}_pwr_{ts}.log"
        return PwrResp(
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
        default=int(os.getenv("POWERPLAN_PORT", 13336)),
        help="listen port (env POWERPLAN_PORT overrides; default 13336)",
    )
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "powerplan_server:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
    )