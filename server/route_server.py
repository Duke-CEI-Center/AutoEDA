#!/usr/bin/env python3


from typing import Optional, Dict
import subprocess, pathlib, datetime, os, logging, sys, argparse
from fastapi import FastAPI
from pydantic import BaseModel

os.environ["PATH"] = (
    "/opt/cadence/innovus221/tools/bin:"
    "/opt/cadence/genus172/bin:" + os.environ.get("PATH", "")
)

ROOT     = pathlib.Path(__file__).resolve().parent.parent
# Use environment variable for log path, fallback to local logs directory
LOG_ROOT = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs"))); LOG_ROOT.mkdir(exist_ok=True)
LOG_DIR  = LOG_ROOT / "route"; LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_ROOT / "route_api.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

BACKEND_DIR_TMPL = ROOT / "scripts" / "{tech}" / "backend"

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

def run(cmd: str, log_file: pathlib.Path, cwd: pathlib.Path, env_extra: dict):
    env = os.environ.copy(); env.update(env_extra)
    with log_file.open("w") as lf, subprocess.Popen(
        cmd, cwd=str(cwd), shell=True, executable="/bin/bash",
        universal_newlines=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
    ) as p:
        for ln in p.stdout: lf.write(ln)
        p.wait()
    if p.returncode != 0:
        raise RuntimeError("Innovus exited %d" % p.returncode)

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

    rpt_dir = impl_dir / "pnr_reports"; rpt_dir.mkdir(exist_ok=True)
    if req.force:
        for rpt in ROUTE_RPTS:
            safe_unlink(rpt_dir / rpt)
        safe_unlink(impl_dir / "pnr_save" / "route.enc")

    top = req.top_module or parse_top_from_config(des_root.parent / "config.tcl") or req.design

    # Set environment variables from user input parameters (replacing CSV reading)
    env = {"BASE_DIR": str(ROOT), "TOP_NAME": top, "FILE_FORMAT": "verilog"}
    
    # Global parameters (mimicking the original CSV structure)
    env["version"] = "custom"  # Add version for compatibility
    env["design_flow_effort"] = req.design_flow_effort
    env["design_power_effort"] = req.design_power_effort
    env["target_util"] = str(req.target_util)
    
    # Placement parameters (mimicking the original CSV structure)
    env["place_global_timing_effort"] = req.place_global_timing_effort
    env["place_global_cong_effort"] = req.place_global_cong_effort
    env["place_detail_wire_length_opt_effort"] = req.place_detail_wire_length_opt_effort
    env["place_global_max_density"] = str(req.place_global_max_density)
    env["place_activity_power_driven"] = str(req.place_activity_power_driven).lower()
    env["prects_opt_max_density"] = str(req.prects_opt_max_density)
    env["prects_opt_power_effort"] = req.prects_opt_power_effort
    env["prects_opt_reclaim_area"] = str(req.prects_opt_reclaim_area).lower()
    env["prects_fix_fanout_load"] = str(req.prects_fix_fanout_load).lower()
    
    # CTS parameters (mimicking the original CSV structure)
    env["cts_cell_density"] = str(req.cts_cell_density)
    env["cts_clock_gate_buffering_location"] = req.cts_clock_gate_buffering_location
    env["cts_clone_clock_gates"] = str(req.cts_clone_clock_gates).lower()
    env["postcts_opt_max_density"] = str(req.postcts_opt_max_density)
    env["postcts_opt_power_effort"] = req.postcts_opt_power_effort
    env["postcts_opt_reclaim_area"] = str(req.postcts_opt_reclaim_area).lower()
    env["postcts_fix_fanout_load"] = str(req.postcts_fix_fanout_load).lower()

    backend_dir = pathlib.Path(str(BACKEND_DIR_TMPL).format(tech=req.tech))
    route_tcl   = backend_dir / "7_route.tcl"

    exec_cmd   = 'restoreDesign "{}" "{}"'.format(cts_enc.resolve(), top)
    innovus_cmd = 'innovus -no_gui -batch -files "{}" -execute "{}"'.format(route_tcl, exec_cmd)

    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_route_{ts}.log"

    try:
        run(innovus_cmd, log_file, impl_dir, env)
    except Exception as e:
        return RtResp(status="error: %s" % e, log_path=str(log_file), rpt_paths={})

    rpt_paths = {r: (rpt_dir / r).exists() and str((rpt_dir / r).relative_to(ROOT)) or "not found"
                 for r in ROUTE_RPTS}

    return RtResp(status="ok", log_path=str(log_file), rpt_paths=rpt_paths)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int,
                        default=int(os.getenv("ROUTE_PORT", 13339)),
                        help="listen port (env ROUTE_PORT overrides; default 13339)")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run("route_server:app", host="0.0.0.0", port=args.port, reload=False)
