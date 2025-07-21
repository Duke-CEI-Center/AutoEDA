#!/usr/bin/env python3

import subprocess, os, pathlib, datetime, argparse
from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_DIR = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs"))) / "setup"
LOG_DIR.mkdir(parents=True, exist_ok=True)

class SetupReq(BaseModel):
    design: str
    tech: str = "FreePDK45"
    version_idx: int = 0
    force: bool = False

class SetupResp(BaseModel):
    status: str
    log_path: str
    reports: dict
    tcl_path: str

def generate_setup_tcl(req: SetupReq, result_dir: pathlib.Path) -> pathlib.Path:
    """Generate synthesis setup TCL script from configuration"""
    
    # Read synthesis configuration
    config_path = ROOT / "config" / "synthesis.csv"
    config_pd = pd.read_csv(config_path, index_col='version')
    
    # Get parameters for this version
    syn_version = config_pd.index[req.version_idx]
    
    # Extract all environment variables from config
    env_vars = {}
    for col in config_pd.columns:
        env_vars[col] = str(config_pd.iloc[req.version_idx][col])
    
    # Create the setup TCL content
    tcl_content = f"""#===============================================================================
# Generated Synthesis Setup TCL Script
# Design: {req.design}
# Tech: {req.tech}
# Version: {syn_version}
# Generated at: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
#===============================================================================

# Set synthesis environment variables
"""
    
    # Add all environment variables from config
    for var_name, var_value in env_vars.items():
        tcl_content += f"set env({var_name}) \"{var_value}\"\n"
    
    tcl_content += f"""
# Set design variables
set env(design) "{req.design}"
set env(tech) "{req.tech}"
set env(syn_version) "{syn_version}"
set env(BASE_DIR) "{ROOT}"

# Create synthesis directory structure
set synthesis_dir "designs/{req.design}/{req.tech}/synthesis/{syn_version}"

# Create directories
file mkdir $synthesis_dir
file mkdir $synthesis_dir/results
file mkdir $synthesis_dir/reports
file mkdir $synthesis_dir/logs
file mkdir $synthesis_dir/data
file mkdir $synthesis_dir/WORK

puts "Synthesis setup completed successfully"
puts "Created synthesis directory: $synthesis_dir"
puts "Environment variables configured for version: {syn_version}"

exec touch _Finished_

exit
"""
    
    tcl_path = result_dir / "setup.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

app = FastAPI(title="MCP · Synthesis-Setup Service")

@app.post("/setup/run", response_model=SetupResp)
def synth_setup(req: SetupReq):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_setup_{ts}.log"

    # Create result directory for generated TCL
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Generate setup TCL
        tcl_path = generate_setup_tcl(req, result_dir)
        
        # Create executor command
        executor_path = ROOT / "server" / "synth_setup_Executor.py"
        cmd = [
            "python", str(executor_path),
            "-design", req.design,
            "-technode", req.tech,
            "-tcl", str(tcl_path),
            "-version_idx", str(req.version_idx)
        ]
        if req.force:
            cmd.append("-force")

        # Execute the setup using executor
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
            return SetupResp(
                status=f"error: setup executor failed with code {process.returncode}",
                log_path=str(log_file),
                reports={},
                tcl_path=str(tcl_path)
            )

        # Check for setup results
        synth_root = ROOT / "designs" / req.design / req.tech / "synthesis"
        if not synth_root.exists():
            return SetupResp(
                status="error: synthesis directory not created",
                log_path=str(log_file),
                reports={},
                tcl_path=str(tcl_path)
            )

        # Find the latest synthesis version
        latest_ver = max(synth_root.iterdir(), key=lambda p: p.stat().st_mtime)
        
        # Check for setup completion
        done_file = latest_ver / "_Finished_"
        if not done_file.exists():
            return SetupResp(
                status="error: setup did not complete successfully",
                log_path=str(log_file),
                reports={},
                tcl_path=str(tcl_path)
            )

        return SetupResp(
            status="ok",
            log_path=str(log_file),
            reports={"setup": "Synthesis setup completed successfully"},
            tcl_path=str(tcl_path)
        )

    except Exception as e:
        return SetupResp(
            status=f"error: {e}",
            log_path=str(log_file),
            reports={},
            tcl_path=str(result_dir / "setup.tcl")
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("SETUP_PORT", 13333)),
        help="listen port (env SETUP_PORT overrides; default 13333)",
    )
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "synth_setup_server:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
    )