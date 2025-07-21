#!/usr/bin/env python3

import subprocess, pathlib, datetime, os, argparse
from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_DIR = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs"))) / "compile"
LOG_DIR.mkdir(parents=True, exist_ok=True)

class CompileReq(BaseModel):
    design: str
    tech: str = "FreePDK45"
    version_idx: int = 0
    force: bool = False

class CompileResp(BaseModel):
    status: str
    log_path: str
    reports: dict
    tcl_path: str

def parse_top_from_config(config_path: pathlib.Path) -> str:
    """Parse TOP_NAME from config.tcl"""
    if not config_path.exists():
        return None
    content = config_path.read_text()
    m = re.search(r'set\s+TOP_NAME\s+"([^"]+)"', content)
    if m:
        return m.group(1)
    return None

def generate_compile_tcl(req: CompileReq, result_dir: pathlib.Path, synthesis_dir: pathlib.Path) -> pathlib.Path:
    """Generate synthesis compile TCL script from templates"""
    
    # Read synthesis configuration
    config_path = ROOT / "config" / "synthesis.csv"
    config_pd = pd.read_csv(config_path, index_col='version')
    
    # Get parameters for this version
    syn_version = config_pd.index[req.version_idx]
    config_row = config_pd.iloc[req.version_idx]
    
    # Parse TOP_NAME from config.tcl
    design_config = ROOT / "designs" / req.design / "config.tcl"
    top_name = parse_top_from_config(design_config) or req.design
    
    # Read the synthesis template
    with open(f"{ROOT}/scripts/{req.tech}/frontend/2_synthesis.tcl", "r") as f:
        synthesis_content = f.read()
    
    # Create the compile TCL content
    tcl_content = f"""#===============================================================================
# Generated Synthesis Compile TCL Script
# Design: {req.design}
# Tech: {req.tech}
# Version: {syn_version}
# Generated at: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
#===============================================================================

# Set synthesis environment variables
"""
    
    # Add all environment variables from config
    for var_name, var_value in config_row.items():
        tcl_content += f"set env({var_name}) \"{var_value}\"\n"
    
    tcl_content += f"""
# Set design variables
set TOP_NAME \"{top_name}\"
set FILE_FORMAT \"verilog\"
set CLOCK_NAME \"clk\"
set RTL_DIR \"../../../rtl\"

# Set directory paths
set REPORTS_DIR \"reports\"
set RESULTS_DIR \"results\"

# Set output file names
set FINAL_VERILOG_OUTPUT_FILE \"{top_name}.v\"
set FINAL_SDC_OUTPUT_FILE \"{top_name}.sdc\"
set FINAL_PARSITICS_OUTPUT_FILE \"{top_name}.spef\"

# Set base directory
set env(BASE_DIR) \"{ROOT}\"

# Create output directories
file mkdir $REPORTS_DIR
file mkdir $RESULTS_DIR
file mkdir data
file mkdir WORK

# Source design and tech configuration
source config.tcl
source tech.tcl

# Synthesis content
{synthesis_content}

puts \"Synthesis compilation completed successfully\"
"""
    
    tcl_path = result_dir / "compile.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

app = FastAPI(title="MCP · Synthesis Compile Service")

@app.post("/compile/run", response_model=CompileResp)
def compile_stage(req: CompileReq):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_compile_{ts}.log"

    # Find synthesis directory
    synth_root = ROOT / "designs" / req.design / req.tech / "synthesis"
    if not synth_root.exists():
        return CompileResp(
            status="error: synthesis directory not found",
            log_path=str(log_file),
            reports={},
            tcl_path=""
        )

    # Find the synthesis version directory based on version_idx
    config_path = ROOT / "config" / "synthesis.csv"
    config_pd = pd.read_csv(config_path, index_col='version')
    syn_version = config_pd.index[req.version_idx]
    
    synthesis_dir = synth_root / syn_version
    if not synthesis_dir.exists():
        return CompileResp(
            status=f"error: synthesis version {syn_version} not found",
            log_path=str(log_file),
            reports={},
            tcl_path=""
        )

    # Create result directory for generated TCL
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Generate compile TCL
        tcl_path = generate_compile_tcl(req, result_dir, synthesis_dir)
        
        # Create executor command
        executor_path = ROOT / "server" / "synth_compile_Executor.py"
        cmd = [
            "python", str(executor_path),
            "-design", req.design,
            "-technode", req.tech,
            "-tcl", str(tcl_path),
            "-synthesis_dir", str(synthesis_dir),
            "-version_idx", str(req.version_idx)
        ]
        if req.force:
            cmd.append("-force")

        # Execute the compilation using executor
        with log_file.open("w") as lf:
            process = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=lf,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            process.wait()

        if process.returncode != 0:
            return CompileResp(
                status=f"error: compile executor failed with code {process.returncode}",
                log_path=str(log_file),
                reports={},
                tcl_path=str(tcl_path)
            )

        # Collect synthesis reports
        reports_dir = synthesis_dir / "reports"
        reports = {}
        
        for rpt in ("qor.rpt", "timing.rpt", "area.rpt", "power.rpt", "check_design.rpt"):
            rpt_path = reports_dir / rpt
            if rpt_path.exists():
                reports[rpt] = rpt_path.read_text()
            else:
                reports[rpt] = f"{rpt} not found"

        return CompileResp(
            status="ok",
            log_path=str(log_file),
            reports=reports,
            tcl_path=str(tcl_path)
        )

    except Exception as e:
        return CompileResp(
            status=f"error: {e}",
            log_path=str(log_file),
            reports={},
            tcl_path=str(result_dir / "compile.tcl")
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("SYN_PORT", 13334)),
        help="listen port (env SYN_PORT overrides; default 13334)",
    )
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "synth_compile_server:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
        log_level="info",
    )