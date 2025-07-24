#!/usr/bin/env python3

import datetime
import logging
import os
import pathlib
import subprocess
import sys
import tarfile
import argparse
from typing import Dict, Optional

from fastapi import FastAPI
from pydantic import BaseModel

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_ROOT = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs")))
LOG_ROOT.mkdir(exist_ok=True)
LOG_DIR = LOG_ROOT / "save"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname).1s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_ROOT / "save_api.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

ART_PATTERNS = [
    ("gds", ["*.gds", "*.gds.gz"]),
    ("def", ["*.def"]),
    ("lef", ["*.lef"]),
    ("spef", ["*.spef", "*.spef.gz"]),
    ("verilog", ["*.v", "*.verilog"]),
]

class SaveReq(BaseModel):
    design: str
    tech: str = "FreePDK45"
    impl_ver: str
    archive: bool = True
    force: bool = False
    top_module: Optional[str] = None

class SaveResp(BaseModel):
    status: str
    log_path: str
    artifacts: Dict[str, str]
    tarball: Optional[str] = None
    tcl_path: str

def parse_top_from_config(cfg: pathlib.Path) -> str:
    """Parse TOP_NAME from config.tcl file"""
    if not cfg.exists():
        return ""
    for line in cfg.read_text().splitlines():
        if line.startswith("set TOP_NAME"):
            return line.split('"')[1]
    return ""

def locate_route_enc(pnr_save: pathlib.Path) -> Optional[pathlib.Path]:
    """Locate the latest route .enc.dat file"""
    for name in (
        "route_opt.enc.dat",
        "detail_route.enc.dat", 
        "route.enc.dat",
    ):
        fp = pnr_save / name
        if fp.exists():
            return fp
    return None

def generate_complete_save_tcl(req: SaveReq, result_dir: pathlib.Path, route_enc: pathlib.Path) -> pathlib.Path:
    """Generate complete save TCL script with all components combined"""
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

    # Read save backend script
    backend_script_path = ROOT / "scripts" / req.tech / "backend" / "8_save_design.tcl"
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
    }

    # Apply template variable replacement
    for var, value in template_variables.items():
        tech_content = tech_content.replace(var, value)
        design_config_content = design_config_content.replace(var, value)
        backend_content = backend_content.replace(var, value)

    # Build the complete TCL content
    tcl_content = f"""#===============================================================================
# Complete Save TCL Script
# Generated at: {datetime.datetime.now()}
# Design: {req.design}
# Technology: {req.tech}
# Implementation Version: {req.impl_ver}
#===============================================================================

#-------------------------------------------------------------------------------
# Environment Variables
#-------------------------------------------------------------------------------
set env(BASE_DIR) "{ROOT}"
set env(TOP_NAME) "{top_name}"
set env(FILE_FORMAT) "verilog"

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
restoreDesign "{route_enc.resolve()}" {top_name}

#===============================================================================
# Save Script: 8_save_design.tcl
#===============================================================================

{backend_content}

# Mark completion
exec touch _Done_
"""

    # Write the complete TCL file
    tcl_file = result_dir / "complete_save.tcl"
    tcl_file.write_text(tcl_content)
    
    return tcl_file

def setup_save_workspace(req: SaveReq, log_file: pathlib.Path) -> tuple[bool, str, pathlib.Path]:
    """Setup save workspace directory structure"""
    try:
        des_root = ROOT / "designs" / req.design / req.tech
        impl_dir = des_root / "implementation" / req.impl_ver
        
        if not impl_dir.exists():
            return False, f"Implementation directory not found: {impl_dir}", impl_dir
            
        # Ensure required directories exist
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

def call_save_executor(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, req: SaveReq, log_file: pathlib.Path) -> tuple[bool, str, dict]:
    """Call save executor via subprocess"""
    try:
        executor_path = ROOT / "server" / "save_Executor.py"
        
        # Build the command
        cmd = f"python {executor_path} -mode save -design {req.design} -technode {req.tech} -tcl {tcl_file} -workspace {workspace_dir}"
        
        # Prepare environment variables
        env = os.environ.copy()
        env["BASE_DIR"] = str(ROOT)
        env["TOP_NAME"] = req.top_module or req.design
        env["FILE_FORMAT"] = "verilog"
        
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
            lf.write(f"\n=== Save Executor Command ===\n")
            lf.write(f"Command: {cmd}\n")
            lf.write(f"Working Directory: {workspace_dir}\n")
            lf.write(f"=== Save Executor Output ===\n")
            
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
            
            lf.write(f"\n=== Save Executor completed with return code: {result.returncode} ===\n")
        
        if result.returncode != 0:
            return False, f"Save executor failed with return code {result.returncode}", {}
            
        # Check for success indicators
        success_indicators = [
            workspace_dir / "_Done_",
            workspace_dir / "_Finished_"
        ]
        
        success = any(indicator.exists() for indicator in success_indicators)
        if not success:
            return False, "Save did not complete successfully (_Done_ or _Finished_ file not found)", {}
            
        return True, "Save completed successfully", {}
        
    except Exception as e:
        return False, f"Failed to execute save: {str(e)}", {}

def collect_artifacts(workspace_dir: pathlib.Path) -> Dict[str, str]:
    """Collect generated artifacts from pnr_out directory"""
    out_dir = workspace_dir / "pnr_out"
    artifacts: Dict[str, str] = {}
    
    for key, patterns in ART_PATTERNS:
        hit = "not found"
        for pat in patterns:
            hits = list(out_dir.glob(pat))
            if hits:
                hit = str(hits[0])
                break
        artifacts[key] = hit
    
    return artifacts

def create_tarball(req: SaveReq, artifacts: Dict[str, str], ts: str) -> Optional[str]:
    """Create tarball archive of artifacts"""
    try:
        deliver_dir = ROOT / "deliverables"
        deliver_dir.mkdir(exist_ok=True)
        tar_path = deliver_dir / f"{req.design}_{req.impl_ver}_{ts}.tgz"
        
        with tarfile.open(str(tar_path), "w:gz") as tar:
            for fp in artifacts.values():
                if fp != "not found" and pathlib.Path(fp).exists():
                    tar.add(fp, arcname=pathlib.Path(fp).name)
        
        logging.info("Tarball created: %s", tar_path)
        return str(tar_path)
        
    except Exception as e:
        logging.error(f"Failed to create tarball: {e}")
        return None

app = FastAPI(title="MCP · Save Service")

@app.post("/run", response_model=SaveResp)
def run_save(req: SaveReq):
    """Main save endpoint"""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_save_{ts}.log"
    
    try:
        with open(log_file, "w") as lf:
            lf.write(f"=== Save Service Started ===\n")
            lf.write(f"Design: {req.design}\n")
            lf.write(f"Technology: {req.tech}\n")
            lf.write(f"Implementation Version: {req.impl_ver}\n")
            lf.write(f"Archive: {req.archive}\n")
            lf.write(f"Force: {req.force}\n")
            lf.write(f"Started at: {datetime.datetime.now()}\n\n")
        
        # Step 1: Setup workspace
        success, message, workspace_dir = setup_save_workspace(req, log_file)
        if not success:
            return SaveResp(status=f"error: {message}", log_path=str(log_file), artifacts={}, tcl_path="")
        
        # Step 2: Locate route enc file
        pnr_save = workspace_dir / "pnr_save"
        route_enc = locate_route_enc(pnr_save)
        if route_enc is None:
            return SaveResp(
                status="error: route_opt/detail_route/route.enc.dat not found",
                log_path=str(log_file),
                artifacts={},
                tcl_path=""
            )
        
        # Step 3: Generate complete save TCL
        result_dir = ROOT / "result" / req.design / req.tech
        tcl_file = generate_complete_save_tcl(req, result_dir, route_enc)
        
        # Step 4: Call save executor
        success, message, _ = call_save_executor(tcl_file, workspace_dir, req, log_file)
        if not success:
            return SaveResp(status=f"error: {message}", log_path=str(log_file), artifacts={}, tcl_path=str(tcl_file))
        
        # Step 5: Collect artifacts
        artifacts = collect_artifacts(workspace_dir)
        
        # Step 6: Create tarball if requested
        tar_path = None
        if req.archive:
            tar_path = create_tarball(req, artifacts, ts)
        
        with open(log_file, "a") as lf:
            lf.write(f"\n=== Save Service Completed Successfully ===\n")
            lf.write(f"Completed at: {datetime.datetime.now()}\n")
        
        return SaveResp(
            status="ok",
            log_path=str(log_file),
            artifacts=artifacts,
            tarball=tar_path,
            tcl_path=str(tcl_file)
        )
        
    except Exception as e:
        with open(log_file, "a") as lf:
            lf.write(f"\n=== Save Service Failed ===\n")
            lf.write(f"Error: {str(e)}\n")
            lf.write(f"Failed at: {datetime.datetime.now()}\n")
        
        return SaveResp(
            status=f"error: {str(e)}",
            log_path=str(log_file),
            artifacts={},
            tarball=None,
            tcl_path=""
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("SAVE_PORT", 13440)),
        help="listen port (env SAVE_PORT overrides; default 13440)",
    )
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "save_server:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
    )