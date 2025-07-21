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

ROOT      = pathlib.Path(__file__).resolve().parent.parent
# Use environment variable for log path, fallback to local logs directory
LOG_ROOT  = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs")))
LOG_ROOT.mkdir(exist_ok=True)
LOG_DIR   = LOG_ROOT / "save"
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
    ("gds",      ["*.gds", "*.gds.gz"]),
    ("def",      ["*.def"]),
    ("lef",      ["*.lef"]),
    ("spef",     ["*.spef", "*.spef.gz"]),
    # ("sdc",      ["*.sdc"]),
    ("verilog",  ["*.v", "*.verilog"]),
    # ("sdf",      ["*.sdf"]),
    # ("emp",      ["*.emp"]),
    # ("enc.dat",  ["*.enc.dat"]),
]

class SaveReq(BaseModel):
    design:     str
    tech:       str = "FreePDK45"
    impl_ver:   str
    archive:    bool = True
    force:      bool = False
    top_module: Optional[str] = None

class SaveResp(BaseModel):
    status:    str
    log_path:  str
    artifacts: Dict[str, str]
    tarball:   Optional[str] = None
    tcl_path:  str  # Add generated TCL path

def locate_route_enc(pnr_save: pathlib.Path) -> Optional[pathlib.Path]:
    for name in (
        "route_opt.enc.dat",
        "detail_route.enc.dat",
        "route.enc.dat",         
    ):
        fp = pnr_save / name
        if fp.exists():
            return fp
    return None

def generate_save_tcl(req: SaveReq, result_dir: pathlib.Path, restore_enc: pathlib.Path) -> pathlib.Path:
    """Generate complete save TCL script by reading templates and filling parameters"""
    
    # Read template file directly
    with open(f"{ROOT}/scripts/FreePDK45/backend/8_save_design.tcl", "r") as f:
        save_content = f.read()
    
    top_name = req.top_module or req.design
    
    # Create complete TCL content: variable definitions + template content
    tcl_content = f"""# Generated Save TCL Script - {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

# Set design variables
set TOP_NAME "{top_name}"
set env(TOP_NAME) "{top_name}"

# Create output directories
file mkdir pnr_logs pnr_out pnr_reports pnr_save

# Restore Design from Route
restoreDesign "{restore_enc}" {top_name}

# Save phase content
{save_content}

puts "Save completed successfully"
"""
    
    tcl_path = result_dir / "save.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

app = FastAPI(title="MCP · Save Service")

@app.post("/save/run", response_model=SaveResp)
def save_run(req: SaveReq):
    impl_dir = (
        ROOT / "designs" / req.design / req.tech / "implementation" / req.impl_ver
    )
    if not impl_dir.exists():
        return SaveResp(
            status="error: implementation dir not found",
            log_path="",
            artifacts={},
            tcl_path=""
        )

    pnr_save = impl_dir / "pnr_save"
    route_enc = locate_route_enc(pnr_save)
    if route_enc is None:
        return SaveResp(
            status="error: route_opt/detail_route/route.enc.dat not found",
            log_path="",
            artifacts={},
            tcl_path=""
        )

    # Create result directory for generated TCL
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)

    top = req.top_module or req.design

    try:
        # Step 1: Generate combined TCL script
        tcl_path = generate_save_tcl(req, result_dir, route_enc)
        logging.info(f"Generated TCL script: {tcl_path}")
        
        # Step 2: Call executor
        executor_script = ROOT / "server" / "save_Executor.py"
        
        executor_args = [
            "python3", str(executor_script),
            "-design", req.design,
            "-technode", req.tech,
            "-tcl", str(tcl_path),
            "-impl_dir", str(impl_dir),
            "-restore_enc", str(route_enc),
            "-top_module", top
        ]
        
        if req.force:
            executor_args.append("-force")
        
        if req.archive:
            executor_args.append("-archive")
            
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"{req.design}_save_{ts}.log"
        
        logging.info(f"Calling executor: {' '.join(executor_args)}")
        
        # Execute the save executor
        with log_file.open("w") as lf:
            result = subprocess.run(
                executor_args,
                cwd=str(ROOT),
                stdout=lf,
                stderr=subprocess.STDOUT,
                text=True
            )
        
        if result.returncode != 0:
            return SaveResp(
                status=f"error: executor failed with return code {result.returncode}",
                log_path=str(log_file),
                artifacts={},
                tcl_path=str(tcl_path)
            )
        
        # Step 3: Collect results
        out_dir   = impl_dir / "pnr_out"
        artifacts: Dict[str, str] = {}
        for key, patterns in ART_PATTERNS:
            hit = "not found"
            for pat in patterns:
                hits = list(out_dir.glob(pat))
                if hits:
                    hit = str(hits[0])
                    break
            artifacts[key] = hit

        tar_path = None
        if req.archive:
            deliver_dir = ROOT / "deliverables"
            deliver_dir.mkdir(exist_ok=True)
            tar_path = deliver_dir / f"{req.design}_{req.impl_ver}_{ts}.tgz"
            with tarfile.open(str(tar_path), "w:gz") as tar:
                for fp in artifacts.values():
                    if fp != "not found":
                        tar.add(fp, arcname=pathlib.Path(fp).name)
            logging.info("Tarball created: %s", tar_path)

        return SaveResp(
            status="ok",
            log_path=str(log_file),
            artifacts=artifacts,
            tarball=str(tar_path) if tar_path else None,
            tcl_path=str(tcl_path)
        )
        
    except Exception as e:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"{req.design}_save_{ts}.log"
        return SaveResp(
            status=f"error: {e}",
            log_path=str(log_file),
            artifacts={},
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