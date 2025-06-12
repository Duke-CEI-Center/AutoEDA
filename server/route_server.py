#!/usr/bin/env python3

import csv
import datetime as dt
import gzip
import logging
import os
import pathlib
import subprocess
import sys
import glob
from typing import Dict, Optional

from fastapi import FastAPI
from pydantic import BaseModel

os.environ["PATH"] = (
    "/opt/cadence/innovus221/tools/bin:"
    "/opt/cadence/genus172/bin:" + os.environ.get("PATH", "")
)

LOG_DIR = pathlib.Path(__file__).resolve().parent.parent / "logs" / "route"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "route_api.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname).1s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("route_server")

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKEND_DIR_TMPL = ROOT / "scripts" / "{tech}" / "backend"
IMP_CSV = ROOT / "config" / "imp_global.csv"
PLC_CSV = ROOT / "config" / "placement.csv"
CTS_CSV = ROOT / "config" / "cts.csv"

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
    g_idx:       int = 0
    p_idx:       int = 0
    c_idx:       int = 0
    restore_enc: str
    force:       bool = False
    top_module:  Optional[str] = None

class RtResp(BaseModel):
    status:    str
    log_path:  str
    rpt_paths: Dict[str, str]

def read_csv_row(path: pathlib.Path, idx: int) -> dict:
    rows = list(csv.DictReader(path.open()))
    if not rows:
        raise ValueError(f"{path.name} is empty")
    if idx >= len(rows):
        raise IndexError(f"{path.name}: row {idx} out of range")
    return rows[idx]

def parse_top_from_config(cfg: pathlib.Path) -> Optional[str]:
    if not cfg.exists():
        return None
    for line in cfg.read_text().splitlines():
        if line.strip().startswith("set TOP_NAME"):
            return line.split('"')[1]
    return None

def run(cmd: str, log_file: pathlib.Path, cwd: pathlib.Path, env_extra: dict):
    env = os.environ.copy()
    env.update(env_extra)
    logger.info("Launching Innovus cmd → %s", cmd)
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
        raise RuntimeError(f"Innovus exited with code {proc.returncode}")

app = FastAPI(title="MCP · Routing Service")

@app.post("/route/run", response_model=RtResp)
def route_run(req: RtReq):
    des_root = ROOT / "designs" / req.design / req.tech
    impl_dir = des_root / "implementation" / req.impl_ver
    if not impl_dir.exists():
        return RtResp(status="error: implementation dir not found", log_path="", rpt_paths={})

    cts_enc = pathlib.Path(req.restore_enc)
    if not cts_enc.exists():
        return RtResp(status="error: restore_enc not found", log_path="", rpt_paths={})

    rpt_dir = impl_dir / "pnr_reports"
    rpt_dir.mkdir(exist_ok=True)
    if req.force:
        for rpt in ROUTE_RPTS:
            (rpt_dir / rpt).unlink(missing_ok=True)
        (impl_dir / "pnr_save" / "route.enc").unlink(missing_ok=True)

    if req.top_module:
        top = req.top_module
    else:
        parsed = parse_top_from_config(ROOT / "designs" / req.design / "config.tcl")
        top = parsed or req.design

    env = {
        "BASE_DIR":   str(ROOT),
        "TOP_NAME":   top,
        "FILE_FORMAT":"verilog",
    }
    env.update(read_csv_row(IMP_CSV, req.g_idx))
    env.update(read_csv_row(PLC_CSV, req.p_idx))
    env.update(read_csv_row(CTS_CSV, req.c_idx))

    backend_dir = pathlib.Path(str(BACKEND_DIR_TMPL).format(tech=req.tech))
    route_tcl    = backend_dir / "7_route.tcl"
    files_arg    = str(route_tcl)
    exec_cmd     = f'restoreDesign "{cts_enc.resolve()}" "{top}"'

    innovus_cmd = (
        f'innovus -no_gui -batch '
        f'-files "{files_arg}" '
        f'-execute "{exec_cmd}"'
    )

    ts       = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_route_{ts}.log"
    try:
        run(innovus_cmd, log_file, impl_dir, env)
    except Exception as e:
        logger.exception("Routing failed")
        return RtResp(status=f"error: {e}", log_path=str(log_file), rpt_paths={})

    rpt_paths: Dict[str, str] = {}
    for rpt in ROUTE_RPTS:
        p = rpt_dir / rpt
        rpt_paths[rpt] = str(p.relative_to(ROOT)) if p.exists() else "not found"

    return RtResp(status="ok", log_path=str(log_file), rpt_paths=rpt_paths)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("route_server:app", host="0.0.0.0", port=3339, reload=False)
