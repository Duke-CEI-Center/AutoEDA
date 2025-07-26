#!/usr/bin/env python3

import subprocess, pathlib, datetime, os, argparse, tarfile
from fastapi import FastAPI
from pydantic import BaseModel
import re
from typing import Optional, Dict

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_DIR = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs"))) / "unified_cts"
LOG_DIR.mkdir(parents=True, exist_ok=True)

class UnifiedCtsReq(BaseModel):
    design: str
    tech: str = "FreePDK45"
    impl_ver: str
    restore_enc: str  # placement.enc file from previous stage
    force: bool = False
    top_module: Optional[str] = None
    archive: bool = True  # Whether to create tarball of final artifacts
    
    # Global design parameters
    design_flow_effort: str = "standard"  # express, standard
    design_power_effort: str = "none"     # none, medium, high
    target_util: float = 0.7              # target utilization
    
    # Placement parameters (needed for route stage)
    place_global_timing_effort: str = "medium"   # low, medium, high
    place_global_cong_effort: str = "medium"     # low, medium, high
    place_detail_wire_length_opt_effort: str = "medium"  # low, medium, high
    place_global_max_density: float = 0.9        # max density
    place_activity_power_driven: bool = False    # power driven placement
    prects_opt_max_density: float = 0.8          # pre-CTS optimization density
    prects_opt_power_effort: str = "low"         # none, low, medium, high
    prects_opt_reclaim_area: bool = False        # reclaim area during optimization
    prects_fix_fanout_load: bool = False         # fix fanout load violations
    
    # CTS parameters
    cts_cell_density: float = 0.5                # CTS cell density
    cts_clock_gate_buffering_location: str = "below"  # below, above
    cts_clone_clock_gates: bool = True            # clone clock gates
    postcts_opt_max_density: float = 0.8         # post-CTS optimization density
    postcts_opt_power_effort: str = "low"        # none, low, medium, high
    postcts_opt_reclaim_area: bool = False       # reclaim area during optimization
    postcts_fix_fanout_load: bool = False        # fix fanout load violations

class UnifiedCtsResp(BaseModel):
    status: str
    log_path: str
    reports: dict
    tcl_path: str
    artifacts: Dict[str, str] = {}
    tarball: Optional[str] = None

def parse_top_from_config(config_path: pathlib.Path) -> str:
    """Parse TOP_NAME from config.tcl"""
    if not config_path.exists():
        return None
    content = config_path.read_text()
    m = re.search(r'set\s+TOP_NAME\s+"([^"]+)"', content)
    if m:
        return m.group(1)
    return None

def generate_complete_unified_cts_tcl(req: UnifiedCtsReq, result_dir: pathlib.Path) -> pathlib.Path:
    """Generate complete unified CTS TCL script combining CTS, Route, and Save"""
    
    # Parse TOP_NAME from config.tcl
    design_config = ROOT / "designs" / req.design / "config.tcl"
    top_name = parse_top_from_config(design_config) or req.top_module or req.design
    
    # Read design config
    design_config_content = ""
    if design_config.exists():
        design_config_content = design_config.read_text()
    
    # Read tech config
    tech_tcl_path = ROOT / "scripts" / req.tech / "tech.tcl"
    tech_content = ""
    if tech_tcl_path.exists():
        tech_content = tech_tcl_path.read_text()
    
    # Read all backend TCL scripts in sequence: 5_cts, 7_route, 8_save_design
    backend_dir = ROOT / "scripts" / req.tech / "backend"
    if not backend_dir.exists():
        raise FileNotFoundError(f"Backend directory not found: {backend_dir}")
    
    # Get backend scripts in order
    backend_scripts = [
        backend_dir / "5_cts.tcl",
        backend_dir / "7_route.tcl", 
        backend_dir / "8_save_design.tcl"
    ]
    
    for script_path in backend_scripts:
        if not script_path.exists():
            raise FileNotFoundError(f"Required backend script not found: {script_path}")
    
    # Read and combine all backend scripts
    combined_backend_content = ""
    for script_path in backend_scripts:
        with open(script_path, "r") as f:
            script_content = f.read()
            combined_backend_content += f"#===============================================================================\n"
            combined_backend_content += f"# Backend Script: {script_path.name}\n"
            combined_backend_content += f"#===============================================================================\n\n"
            combined_backend_content += script_content + "\n\n"
    
    # Define comprehensive template variables for replacement
    template_variables = {
        # Basic design parameters
        "${TOP_NAME}": top_name,
        "$TOP_NAME": top_name,
        "${env(TOP_NAME)}": top_name,
        "$env(TOP_NAME)": top_name,
        
        # Base directory
        "${BASE_DIR}": str(ROOT),
        "$BASE_DIR": str(ROOT),
        "${env(BASE_DIR)}": str(ROOT),
        "$env(BASE_DIR)": str(ROOT),
        
        # Global design parameters
        "${design_flow_effort}": req.design_flow_effort,
        "$design_flow_effort": req.design_flow_effort,
        "${env(design_flow_effort)}": req.design_flow_effort,
        "$env(design_flow_effort)": req.design_flow_effort,
        "${design_power_effort}": req.design_power_effort,
        "$design_power_effort": req.design_power_effort,
        "${env(design_power_effort)}": req.design_power_effort,
        "$env(design_power_effort)": req.design_power_effort,
        "${target_util}": str(req.target_util),
        "$target_util": str(req.target_util),
        "${env(target_util)}": str(req.target_util),
        "$env(target_util)": str(req.target_util),
        
        # Placement parameters (needed for route)
        "${env(place_global_timing_effort)}": req.place_global_timing_effort,
        "$env(place_global_timing_effort)": req.place_global_timing_effort,
        "${env(place_global_cong_effort)}": req.place_global_cong_effort,
        "$env(place_global_cong_effort)": req.place_global_cong_effort,
        "${env(place_detail_wire_length_opt_effort)}": req.place_detail_wire_length_opt_effort,
        "$env(place_detail_wire_length_opt_effort)": req.place_detail_wire_length_opt_effort,
        "${env(place_global_max_density)}": str(req.place_global_max_density),
        "$env(place_global_max_density)": str(req.place_global_max_density),
        "${env(place_activity_power_driven)}": str(req.place_activity_power_driven).lower(),
        "$env(place_activity_power_driven)": str(req.place_activity_power_driven).lower(),
        "${env(prects_opt_max_density)}": str(req.prects_opt_max_density),
        "$env(prects_opt_max_density)": str(req.prects_opt_max_density),
        "${env(prects_opt_power_effort)}": req.prects_opt_power_effort,
        "$env(prects_opt_power_effort)": req.prects_opt_power_effort,
        "${env(prects_opt_reclaim_area)}": str(req.prects_opt_reclaim_area).lower(),
        "$env(prects_opt_reclaim_area)": str(req.prects_opt_reclaim_area).lower(),
        "${env(prects_fix_fanout_load)}": str(req.prects_fix_fanout_load).lower(),
        "$env(prects_fix_fanout_load)": str(req.prects_fix_fanout_load).lower(),
        
        # CTS parameters
        "${env(cts_cell_density)}": str(req.cts_cell_density),
        "$env(cts_cell_density)": str(req.cts_cell_density),
        "${env(cts_clock_gate_buffering_location)}": req.cts_clock_gate_buffering_location,
        "$env(cts_clock_gate_buffering_location)": req.cts_clock_gate_buffering_location,
        "${env(cts_clone_clock_gates)}": str(req.cts_clone_clock_gates).lower(),
        "$env(cts_clone_clock_gates)": str(req.cts_clone_clock_gates).lower(),
        "${env(postcts_opt_max_density)}": str(req.postcts_opt_max_density),
        "$env(postcts_opt_max_density)": str(req.postcts_opt_max_density),
        "${env(postcts_opt_power_effort)}": req.postcts_opt_power_effort,
        "$env(postcts_opt_power_effort)": req.postcts_opt_power_effort,
        "${env(postcts_opt_reclaim_area)}": str(req.postcts_opt_reclaim_area).lower(),
        "$env(postcts_opt_reclaim_area)": str(req.postcts_opt_reclaim_area).lower(),
        "${env(postcts_fix_fanout_load)}": str(req.postcts_fix_fanout_load).lower(),
        "$env(postcts_fix_fanout_load)": str(req.postcts_fix_fanout_load).lower(),
    }
    
    # Apply template variable replacements to all content
    for placeholder, value in template_variables.items():
        design_config_content = design_config_content.replace(placeholder, value)
        tech_content = tech_content.replace(placeholder, value)
        combined_backend_content = combined_backend_content.replace(placeholder, value)
    
    # Combine all content into a single TCL file with explicit environment variable settings
    tcl_content = f"""#===============================================================================
# Complete Unified CTS TCL Script (CTS + Route + Save)
# Generated by MCP EDA Server
# Design: {req.design}
# Tech: {req.tech}
# Implementation Version: {req.impl_ver}
# Generated at: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
#===============================================================================

#-------------------------------------------------------------------------------
# Set environment variables explicitly
#-------------------------------------------------------------------------------
set env(BASE_DIR) "{ROOT}"
set env(TOP_NAME) "{top_name}"
set env(FILE_FORMAT) "verilog"
set env(version) "custom"
set env(design_flow_effort) "{req.design_flow_effort}"
set env(design_power_effort) "{req.design_power_effort}"
set env(target_util) "{req.target_util}"
set env(place_global_timing_effort) "{req.place_global_timing_effort}"
set env(place_global_cong_effort) "{req.place_global_cong_effort}"
set env(place_detail_wire_length_opt_effort) "{req.place_detail_wire_length_opt_effort}"
set env(place_global_max_density) "{req.place_global_max_density}"
set env(place_activity_power_driven) "{str(req.place_activity_power_driven).lower()}"
set env(prects_opt_max_density) "{req.prects_opt_max_density}"
set env(prects_opt_power_effort) "{req.prects_opt_power_effort}"
set env(prects_opt_reclaim_area) "{str(req.prects_opt_reclaim_area).lower()}"
set env(prects_fix_fanout_load) "{str(req.prects_fix_fanout_load).lower()}"
set env(cts_cell_density) "{req.cts_cell_density}"
set env(cts_clock_gate_buffering_location) "{req.cts_clock_gate_buffering_location}"
set env(cts_clone_clock_gates) "{str(req.cts_clone_clock_gates).lower()}"
set env(postcts_opt_max_density) "{req.postcts_opt_max_density}"
set env(postcts_opt_power_effort) "{req.postcts_opt_power_effort}"
set env(postcts_opt_reclaim_area) "{str(req.postcts_opt_reclaim_area).lower()}"
set env(postcts_fix_fanout_load) "{str(req.postcts_fix_fanout_load).lower()}"
set env(CLKBUF_CELLS) "CLKBUF_X1 CLKBUF_X2 CLKBUF_X3 CLKBUF_X4 CLKBUF_X8"
set env(CLKGT_CELLS) "CLKGT_X1 CLKGT_X2"

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
# Technology Configuration (from tech.tcl)
#-------------------------------------------------------------------------------
{tech_content}

#-------------------------------------------------------------------------------
# Restore Design from placement stage
#-------------------------------------------------------------------------------
restoreDesign "{pathlib.Path(req.restore_enc).resolve()}" {top_name}

#-------------------------------------------------------------------------------
# Backend Scripts (5_cts.tcl + 7_route.tcl + 8_save_design.tcl)
#-------------------------------------------------------------------------------
{combined_backend_content}

#-------------------------------------------------------------------------------
# Unified CTS+Route+Save completed
#-------------------------------------------------------------------------------
exec touch _Done_
exit
"""
    
    # Apply template replacements to the final combined TCL content
    for placeholder, value in template_variables.items():
        tcl_content = tcl_content.replace(placeholder, value)
    
    tcl_path = result_dir / "complete_unified_cts.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

def setup_unified_cts_workspace(req: UnifiedCtsReq, log_file: pathlib.Path) -> tuple[bool, str, pathlib.Path]:
    """Setup unified CTS workspace directory structure"""
    
    try:
        # Create implementation version directory
        design_dir = ROOT / "designs" / req.design
        impl_dir = design_dir / req.tech / "implementation" / req.impl_ver
        
        # Check if directories exist
        if not impl_dir.exists():
            return False, f"Implementation directory not found: {impl_dir}", impl_dir
        
        if req.force:
            # Force overwrite - remove existing output directories
            import shutil
            for subdir in ["pnr_save", "pnr_out", "pnr_reports"]:
                target_dir = impl_dir / subdir
                if target_dir.exists():
                    for file in target_dir.glob("cts*"):
                        file.unlink()
                    for file in target_dir.glob("route*"):
                        file.unlink()
                    for file in target_dir.glob("*_pnr.*"):
                        file.unlink()
        
        # Create all necessary subdirectories
        (impl_dir / "pnr_save").mkdir(exist_ok=True)
        (impl_dir / "pnr_out").mkdir(exist_ok=True)
        (impl_dir / "pnr_reports").mkdir(exist_ok=True)
        
        # Copy config.tcl to implementation directory
        cfg_src = ROOT / "designs" / req.design / "config.tcl"
        cfg_dst = impl_dir / "config.tcl"
        if cfg_src.exists() and not cfg_dst.exists():
            import shutil
            shutil.copy2(cfg_src, cfg_dst)
        
        with log_file.open("w") as lf:
            lf.write("=== Unified CTS Workspace Setup ===\n")
            lf.write(f"Design: {req.design}\n")
            lf.write(f"Tech: {req.tech}\n")
            lf.write(f"Implementation Version: {req.impl_ver}\n")
            lf.write(f"Implementation Directory: {impl_dir}\n")
            lf.write("Workspace setup completed successfully.\n")

        return True, "workspace ok", impl_dir

    except Exception as e:
        return False, f"error: {e}", None

def call_unified_cts_executor(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, req: UnifiedCtsReq, log_file: pathlib.Path) -> tuple[bool, str, dict]:
    """Call the unified CTS executor to run EDA tools"""
    
    try:
        # Build executor command
        executor_path = ROOT / "server" / "unified_cts_Executor.py"
        cmd = [
            "python", str(executor_path),
            "-design", req.design,
            "-technode", req.tech,
            "-tcl", str(tcl_file),
            "-workspace", str(workspace_dir)
        ]
        
        if req.force:
            cmd.append("-force")
        
        # Set up environment
        env = os.environ.copy()
        env['BASE_DIR'] = str(ROOT)
        
        # Add EDA tools to PATH
        eda_paths = [
            "/opt/cadence/innovus221/tools/bin",
            "/opt/cadence/genus172/bin",
        ]
        current_path = env.get('PATH', '')
        for eda_path in eda_paths:
            if eda_path not in current_path:
                env['PATH'] = f"{eda_path}:{current_path}"
                current_path = env['PATH']
        
        # Execute the unified CTS executor
        with log_file.open("a") as lf:
            lf.write(f"\n=== Calling Unified CTS Executor ===\n")
            lf.write(f"Command: {' '.join(cmd)}\n")
            lf.write(f"Working Directory: {workspace_dir}\n")
            lf.write(f"Executor started at: {datetime.datetime.now()}\n\n")
        
        result = subprocess.run(
            cmd,
            cwd=str(workspace_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=7200  # 2 hour timeout for CTS+Route+Save
        )
        
        # Log the execution results
        with log_file.open("a") as lf:
            lf.write(f"\n=== Executor Results ===\n")
            lf.write(f"Return code: {result.returncode}\n")
            lf.write(f"STDOUT:\n{result.stdout}\n")
            if result.stderr:
                lf.write(f"STDERR:\n{result.stderr}\n")
        
        if result.returncode != 0:
            return False, f"executor failed with code {result.returncode}", {}
        
        # Collect reports
        reports = {}
        rpt_dir = workspace_dir / "pnr_reports"
        
        # Try to read various report files
        report_files = [
            ("cts_summary.rpt", "cts_summary.rpt"),
            ("cts_opt_timing.rpt.gz", "cts_opt_timing.rpt.gz"),
            ("route_summary.rpt", "route_summary.rpt"),
            ("route_timing.rpt.gz", "route_timing.rpt.gz"),
            ("postRoute_drc_max1M.rpt", "postRoute_drc_max1M.rpt"),
            ("postOpt_drc_max1M.rpt", "postOpt_drc_max1M.rpt"),
        ]
        
        for base_name, file_name in report_files:
            rpt_path = rpt_dir / file_name
            if rpt_path.exists():
                try:
                    if file_name.endswith('.gz'):
                        import gzip
                        with gzip.open(rpt_path, 'rt') as f:
                            reports[base_name] = f.read()
                    else:
                        reports[base_name] = rpt_path.read_text()
                except Exception as e:
                    reports[base_name] = f"Error reading {file_name}: {e}"
            else:
                reports[base_name] = "Report not found"
        
        return True, "unified CTS+Route+Save completed successfully", reports

    except subprocess.TimeoutExpired:
        return False, "executor timeout (2 hours)", {}
    except Exception as e:
        return False, f"executor error: {e}", {}

def collect_artifacts(workspace_dir: pathlib.Path) -> Dict[str, str]:
    """Collect generated artifacts from pnr_out directory"""
    out_dir = workspace_dir / "pnr_out"
    artifacts = {}
    
    # Define artifact patterns similar to save_server
    artifact_patterns = [
        ("gds", ["*.gds", "*.gds.gz"]),
        ("def", ["*.def"]),
        ("lef", ["*.lef"]),
        ("spef", ["*.spef", "*.spef.gz"]),
        ("verilog", ["*.v", "*.verilog"]),
    ]
    
    for key, patterns in artifact_patterns:
        found = "not found"
        for pattern in patterns:
            hits = list(out_dir.glob(pattern))
            if hits:
                found = str(hits[0].relative_to(ROOT))
                break
        artifacts[key] = found
    
    return artifacts

def create_tarball(req: UnifiedCtsReq, artifacts: Dict[str, str], ts: str) -> Optional[str]:
    """Create tarball archive of artifacts"""
    if not req.archive:
        return None
        
    try:
        deliver_dir = ROOT / "deliverables"
        deliver_dir.mkdir(exist_ok=True)
        tar_path = deliver_dir / f"{req.design}_{req.impl_ver}_unified_cts_{ts}.tgz"
        
        with tarfile.open(str(tar_path), "w:gz") as tar:
            for artifact_path in artifacts.values():
                if artifact_path != "not found":
                    full_path = ROOT / artifact_path
                    if full_path.exists():
                        tar.add(str(full_path), arcname=full_path.name)
        
        return str(tar_path.relative_to(ROOT))
        
    except Exception as e:
        return f"Error creating tarball: {e}"

app = FastAPI(title="MCP · Unified CTS Service (CTS + Route + Save)")

@app.post("/run", response_model=UnifiedCtsResp)
def run_unified_cts(req: UnifiedCtsReq):
    """Main unified CTS endpoint: TCL generation + executor call"""
    
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_unified_cts_{ts}.log"
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Phase 1: Setup workspace
        workspace_success, workspace_status, workspace_dir = setup_unified_cts_workspace(req, log_file)
        if not workspace_success:
            return UnifiedCtsResp(
                status=workspace_status,
                log_path=str(log_file),
                reports={"error": workspace_status},
                tcl_path=""
            )
        
        # Phase 2: Check restore file exists
        restore_path = pathlib.Path(req.restore_enc)
        if not restore_path.exists():
            return UnifiedCtsResp(
                status="error: restore_enc file not found",
                log_path=str(log_file),
                reports={"error": f"restore_enc file not found: {req.restore_enc}"},
                tcl_path=""
            )
        
        # Phase 3: Generate complete unified CTS TCL file
        tcl_file = generate_complete_unified_cts_tcl(req, result_dir)
        
        # Phase 4: Call executor to run unified CTS+Route+Save
        exec_success, exec_status, reports = call_unified_cts_executor(tcl_file, workspace_dir, req, log_file)
        
        if not exec_success:
            return UnifiedCtsResp(
                status=exec_status,
                log_path=str(log_file),
                reports={"error": exec_status},
                tcl_path=str(tcl_file)
            )

        # Phase 5: Collect artifacts
        artifacts = collect_artifacts(workspace_dir)
        
        # Phase 6: Create tarball if requested
        tarball_path = create_tarball(req, artifacts, ts)
        
        # Success
        final_reports = {"workspace": workspace_status, "execution": exec_status}
        final_reports.update(reports)
        
        return UnifiedCtsResp(
            status="ok",
            log_path=str(log_file),
            reports=final_reports,
            tcl_path=str(tcl_file),
            artifacts=artifacts,
            tarball=tarball_path
        )

    except Exception as e:
        return UnifiedCtsResp(
            status=f"error: {e}",
            log_path=str(log_file),
            reports={"error": str(e)},
            tcl_path="",
            artifacts={},
            tarball=None
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("UNIFIED_CTS_PORT", 13341)),
        help="listen port (env UNIFIED_CTS_PORT overrides; default 13341)",
    )
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "unified_cts_server:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
        log_level="info",
    ) 