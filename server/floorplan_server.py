#!/usr/bin/env python3

from typing import Optional
import subprocess, pathlib, datetime, os, logging, sys, glob, gzip, argparse, json   
from fastapi import FastAPI
from pydantic import BaseModel

ROOT      = pathlib.Path(__file__).resolve().parent.parent
# Use environment variable for log path, fallback to local logs directory
LOG_ROOT  = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs")))
LOG_ROOT.mkdir(exist_ok=True)
LOG_DIR   = LOG_ROOT / "floorplan"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_ROOT / "fp_api.log"), 
        logging.StreamHandler(sys.stdout),
    ],
)



class FPReq(BaseModel):
    design:      str
    tech:        str = "FreePDK45"
    syn_ver:     str
    force:       bool = False
    top_module:  Optional[str] = None
    restore_enc: Optional[str] = None
    
    # User input parameters (previously from CSV)
    design_flow_effort:  str = "standard"  # express, standard
    design_power_effort: str = "none"      # none, medium, high
    ASPECT_RATIO:        float = 1.0       # die aspect ratio
    target_util:         float = 0.7       # target utilization

class FPResp(BaseModel):
    status:   str
    log_path: str
    report:   str
    tcl_path: str  # Add generated TCL path

def generate_floorplan_tcl(req: FPReq, result_dir: pathlib.Path, syn_res: pathlib.Path) -> pathlib.Path:
    """Generate complete floorplan TCL script by reading templates and filling parameters"""
    
    # Read template files directly
    with open(f"{ROOT}/scripts/FreePDK45/backend/1_setup.tcl", "r") as f:
        setup_content = f.read()
    with open(f"{ROOT}/scripts/FreePDK45/backend/2_floorplan.tcl", "r") as f:
        floorplan_content = f.read()
    
    top_name = req.top_module or req.design
    clock_name = "clk"
    clock_period = "1."
    
    # Create complete TCL content: variable definitions + template content
    tcl_content = f"""# Generated Floorplan TCL Script - {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

# Set design variables
set NETLIST_DIR "{syn_res}"
set TOP_NAME "{top_name}"
set FILE_FORMAT "verilog"
set CLOCK_NAME "{clock_name}"
set clk_period {clock_period}

# Set environment variables
set env(design_flow_effort) "{req.design_flow_effort}"
set env(design_power_effort) "{req.design_power_effort}"
set env(target_util) "{req.target_util}"
set env(BASE_DIR) "{ROOT}"

# Create output directories
file mkdir pnr_logs pnr_out pnr_reports pnr_save

# Source configuration files
source config.tcl
source tech.tcl

# Setup phase content
{setup_content}

# Floorplan phase content
{floorplan_content}

puts "Floorplan completed successfully"
"""
    
    tcl_path = result_dir / "floorplan.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

app = FastAPI(title="MCP · Floorplan Service")

@app.post("/floorplan/run", response_model=FPResp)
def floorplan_run(req: FPReq):
    des_root = ROOT / "designs" / req.design / req.tech
    syn_res  = des_root / "synthesis" / req.syn_ver / "results"
    if not syn_res.exists():
        return FPResp(status="error: synthesis results not found", log_path="", report="", tcl_path="")

    impl_ver = f"{req.syn_ver}__g0_p0"  # Simplified version naming
    impl_dir = des_root / "implementation" / impl_ver
    if impl_dir.exists() and req.force:
        subprocess.run(["rm", "-rf", str(impl_dir)], check=True)
    impl_dir.mkdir(parents=True, exist_ok=True)

    # Create result directory for generated TCL
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)

    top_name = req.top_module or req.design

    # Check restore_enc if provided
    if req.restore_enc:
        restore_abs = pathlib.Path(req.restore_enc).resolve()
        if not restore_abs.exists():
            return FPResp(status="error: provided restore_enc not found", log_path="", report="", tcl_path="")

    # Copy design config to implementation directory
    design_config = ROOT / "designs" / req.design / "config.tcl"
    local_config  = impl_dir / "config.tcl"
    if not local_config.exists():
        if design_config.exists():
            subprocess.run(["cp", str(design_config), str(local_config)], check=True)
        else:
            return FPResp(
                status=f"error: can not find config.tcl: neither {design_config} nor {ROOT/'config.tcl'} exist",
                log_path="", report="", tcl_path=""
            )

    # Copy tech.tcl to implementation directory
    tech_tcl = ROOT / "scripts" / req.tech / "tech.tcl"
    local_tech = impl_dir / "tech.tcl"
    if tech_tcl.exists():
        subprocess.run(["cp", str(tech_tcl), str(local_tech)], check=True)

    try:
        # Step 1: Generate combined TCL script
        tcl_path = generate_floorplan_tcl(req, result_dir, syn_res)
        logging.info(f"Generated TCL script: {tcl_path}")
        
        # Step 2: Call executor
        executor_script = ROOT / "server" / "floorplan_Executor.py"
        
        executor_args = [
            "python3", str(executor_script),
            "-design", req.design,
            "-technode", req.tech,
            "-tcl", str(tcl_path),
            "-impl_dir", str(impl_dir),
            "-restore_enc", req.restore_enc or "",
            "-top_module", top_name
        ]
        
        if req.force:
            executor_args.append("-force")
            
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"{req.design}_fp_{ts}.log"
        
        logging.info(f"Calling executor: {' '.join(executor_args)}")
        
        # Execute the floorplan executor
        with log_file.open("w") as lf:
            result = subprocess.run(
                executor_args,
                cwd=str(ROOT),
                stdout=lf,
                stderr=subprocess.STDOUT,
                text=True
            )
        
        if result.returncode != 0:
            return FPResp(
                status=f"error: executor failed with return code {result.returncode}",
                log_path=str(log_file),
                report="",
                tcl_path=str(tcl_path)
            )
        
        # Step 3: Collect results
        rpt_dir = impl_dir / "pnr_reports"
        candidates = glob.glob(str(rpt_dir / "floorplan_summary.rpt*"))
        if candidates:
            rpt_file = pathlib.Path(candidates[0])
            rpt_text = (
                gzip.open(rpt_file, "rt").read()
                if rpt_file.suffix == ".gz"
                else rpt_file.read_text()
            )
        else:
            rpt_text = "floorplan_summary.rpt(.gz) not found"

        enc_path = impl_dir / "pnr_save" / "floorplan.enc.dat"
        if not enc_path.exists():
            return FPResp(
                status="error: Floorplan did not produce floorplan.enc.dat",
                log_path=str(log_file),
                report=rpt_text,
                tcl_path=str(tcl_path)
            )

        return FPResp(
            status="ok", 
            log_path=str(log_file), 
            report=rpt_text,
            tcl_path=str(tcl_path)
        )
        
    except Exception as e:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"{req.design}_fp_{ts}.log"
        return FPResp(
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
        default=int(os.getenv("FLOORPLAN_PORT", 13335)),
        help="listen port (env FLOORPLAN_PORT overrides; default 13335)",
    )
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "floorplan_server:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
    )