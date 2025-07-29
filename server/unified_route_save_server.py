#!/usr/bin/env python3

import subprocess, pathlib, datetime, os, argparse
from fastapi import FastAPI
from pydantic import BaseModel
import re
from typing import Optional, Dict

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_DIR = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs"))) / "unified_route_save"
LOG_DIR.mkdir(parents=True, exist_ok=True)

class UnifiedRouteSaveReq(BaseModel):
    design: str
    tech: str = "FreePDK45"
    impl_ver: str
    restore_enc: str  # CTS enc file to restore from
    force: bool = False
    top_module: Optional[str] = None
    archive: bool = True  # Create tarball archive
    
    # Global parameters (from imp_global.csv)
    design_flow_effort: str = "standard"  # express, standard
    design_power_effort: str = "none"      # none, medium, high
    target_util: float = 0.7       # target utilization

    # Placement parameters (from placement.csv)
    place_global_timing_effort: str = "medium"   # low, medium, high
    place_global_cong_effort: str = "medium"   # low, medium, high
    place_detail_wire_length_opt_effort: str = "medium"  # low, medium, high
    place_global_max_density: float = 0.9      # max density
    place_activity_power_driven: bool = False     # power driven placement
    prects_opt_max_density: float = 0.8      # pre-CTS optimization density
    prects_opt_power_effort: str = "low"      # none, low, medium, high
    prects_opt_reclaim_area: bool = False     # reclaim area during optimization
    prects_fix_fanout_load: bool = False     # fix fanout load violations

    # CTS parameters (from cts.csv)
    cts_cell_density: float = 0.5      # CTS cell density
    cts_clock_gate_buffering_location: str = "below"  # below, above
    cts_clone_clock_gates: bool = True      # clone clock gates
    postcts_opt_max_density: float = 0.8      # post-CTS optimization density
    postcts_opt_power_effort: str = "low"      # none, low, medium, high
    postcts_opt_reclaim_area: bool = False     # reclaim area during optimization
    postcts_fix_fanout_load: bool = False     # fix fanout load violations

class UnifiedRouteSaveResp(BaseModel):
    status: str
    log_path: str
    reports: dict
    artifacts: Dict[str, str]
    tarball: Optional[str] = None
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

def generate_complete_unified_route_save_tcl(req: UnifiedRouteSaveReq, result_dir: pathlib.Path) -> pathlib.Path:
    """Generate complete unified route+save TCL script combining 7_route.tcl and 8_save_design.tcl"""
    
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
    
    # Read backend TCL scripts in sequence: 7_route.tcl, 8_save_design.tcl
    backend_dir = ROOT / "scripts" / req.tech / "backend"
    if not backend_dir.exists():
        raise FileNotFoundError(f"Backend directory not found: {backend_dir}")
    
    # Get backend scripts in order
    backend_scripts = [
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
        "${top_module}": top_name,
        "$top_module": top_name,
        "${env(top_module)}": top_name,
        "$env(top_module)": top_name,
        
        # Base directory
        "${BASE_DIR}": str(ROOT),
        "$BASE_DIR": str(ROOT),
        "${env(BASE_DIR)}": str(ROOT),
        "$env(BASE_DIR)": str(ROOT),
        
        # Global design parameters
        "${design_flow_effort}": req.design_flow_effort,
        "$design_flow_effort": req.design_flow_effort,
        "${design_power_effort}": req.design_power_effort,
        "$design_power_effort": req.design_power_effort,
        "${target_util}": str(req.target_util),
        "$target_util": str(req.target_util),
        "${env(design_flow_effort)}": req.design_flow_effort,
        "$env(design_flow_effort)": req.design_flow_effort,
        "${env(design_power_effort)}": req.design_power_effort,
        "$env(design_power_effort)": req.design_power_effort,
        "${env(target_util)}": str(req.target_util),
        "$env(target_util)": str(req.target_util),
        
        # Environment variables for placement parameters
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
        
        # Environment variables for CTS parameters
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
    
    # Build environment variables from request parameters
    env_vars = {
        "BASE_DIR": str(ROOT),
        "TOP_NAME": top_name,
        "top_module": top_name,
        "FILE_FORMAT": "verilog",
        "version": "custom",
        "design_flow_effort": req.design_flow_effort,
        "design_power_effort": req.design_power_effort,
        "target_util": str(req.target_util),
        "place_global_timing_effort": req.place_global_timing_effort,
        "place_global_cong_effort": req.place_global_cong_effort,
        "place_detail_wire_length_opt_effort": req.place_detail_wire_length_opt_effort,
        "place_global_max_density": str(req.place_global_max_density),
        "place_activity_power_driven": str(req.place_activity_power_driven).lower(),
        "prects_opt_max_density": str(req.prects_opt_max_density),
        "prects_opt_power_effort": req.prects_opt_power_effort,
        "prects_opt_reclaim_area": str(req.prects_opt_reclaim_area).lower(),
        "prects_fix_fanout_load": str(req.prects_fix_fanout_load).lower(),
        "cts_cell_density": str(req.cts_cell_density),
        "cts_clock_gate_buffering_location": req.cts_clock_gate_buffering_location,
        "cts_clone_clock_gates": str(req.cts_clone_clock_gates).lower(),
        "postcts_opt_max_density": str(req.postcts_opt_max_density),
        "postcts_opt_power_effort": req.postcts_opt_power_effort,
        "postcts_opt_reclaim_area": str(req.postcts_opt_reclaim_area).lower(),
        "postcts_fix_fanout_load": str(req.postcts_fix_fanout_load).lower(),
    }
    
    # Combine all content into a single TCL file with explicit environment variable settings
    tcl_content = f"""#===============================================================================
# Complete Unified Route+Save TCL Script (Routing + Final Save)
# Generated by MCP EDA Server
# Design: {req.design}
# Tech: {req.tech}
# Implementation Version: {req.impl_ver}
# Generated at: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
#===============================================================================

#-------------------------------------------------------------------------------
# Set environment variables explicitly
#-------------------------------------------------------------------------------
"""
    
    # Add environment variables
    for key, value in env_vars.items():
        tcl_content += f'set env({key}) "{value}"\n'

    tcl_content += f"""

#-------------------------------------------------------------------------------
# Global Variables  
#-------------------------------------------------------------------------------
set start_time [clock seconds]
set top_module "{top_name}"

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
# Restore Design from CTS
#-------------------------------------------------------------------------------
restoreDesign "{pathlib.Path(req.restore_enc).resolve()}" {top_name}

#-------------------------------------------------------------------------------
# Backend Scripts (7_route.tcl + 8_save_design.tcl)
#-------------------------------------------------------------------------------
{combined_backend_content}

#-------------------------------------------------------------------------------
# Final completion marker
#-------------------------------------------------------------------------------
exec touch _Done_
exit
"""
    
    # Apply template replacements to the final combined TCL content
    for placeholder, value in template_variables.items():
        tcl_content = tcl_content.replace(placeholder, value)
    
    tcl_path = result_dir / "complete_unified_route_save.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

def setup_unified_route_save_workspace(req: UnifiedRouteSaveReq, log_file: pathlib.Path) -> tuple[bool, str, pathlib.Path]:
    """Setup unified route+save workspace directory structure"""
    
    try:
        # Create implementation version directory
        design_dir = ROOT / "designs" / req.design
        impl_dir = design_dir / req.tech / "implementation" / req.impl_ver
        
        if not impl_dir.exists():
            return False, f"Implementation directory not found: {impl_dir}", impl_dir
        
        # Check if restore file exists
        restore_path = pathlib.Path(req.restore_enc)
        if not restore_path.exists():
            return False, f"Restore ENC file not found: {restore_path}", impl_dir
        
        # Ensure required directories exist
        (impl_dir / "pnr_save").mkdir(exist_ok=True)
        (impl_dir / "pnr_out").mkdir(exist_ok=True)
        (impl_dir / "pnr_reports").mkdir(exist_ok=True)
        
        # Handle force cleanup
        if req.force:
            import shutil
            for subdir in ["pnr_reports", "pnr_out"]:
                target_dir = impl_dir / subdir
                if target_dir.exists():
                    # Remove route/save specific files
                    for pattern in ["*route*", "*_pnr.*", "*final*", "*.gds*", "*.spef*"]:
                        for file_path in target_dir.glob(pattern):
                            if file_path.is_file():
                                file_path.unlink()
        
        # Copy config.tcl to implementation directory
        cfg_src = ROOT / "designs" / req.design / "config.tcl"
        cfg_dst = impl_dir / "config.tcl"
        if cfg_src.exists() and not cfg_dst.exists():
            import shutil
            shutil.copy2(cfg_src, cfg_dst)
        
        with log_file.open("w") as lf:
            lf.write("=== Unified Route+Save Workspace Setup ===\n")
            lf.write(f"Design: {req.design}\n")
            lf.write(f"Tech: {req.tech}\n")
            lf.write(f"Implementation Version: {req.impl_ver}\n")
            lf.write(f"Restore ENC: {req.restore_enc}\n")
            lf.write(f"Implementation Directory: {impl_dir}\n")
            lf.write("Workspace setup completed successfully.\n")

        return True, "workspace ok", impl_dir

    except Exception as e:
        return False, f"error: {e}", None

def call_unified_route_save_executor(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, req: UnifiedRouteSaveReq, log_file: pathlib.Path) -> tuple[bool, str, dict]:
    """Call the unified route+save executor to run EDA tools"""
    
    try:
        # Build executor command
        executor_path = ROOT / "server" / "unified_route_save_Executor.py"
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
            "/opt/cadence/innovus191/bin"
        ]
        current_path = env.get('PATH', '')
        for eda_path in eda_paths:
            if eda_path not in current_path:
                env['PATH'] = f"{eda_path}:{current_path}"
                current_path = env['PATH']
        
        # Execute the unified route+save executor
        with log_file.open("a") as lf:
            lf.write(f"\n=== Calling Unified Route+Save Executor ===\n")
            lf.write(f"Command: {' '.join(cmd)}\n")
            lf.write(f"Working Directory: {workspace_dir}\n")
            lf.write(f"Executor started at: {datetime.datetime.now()}\n\n")
        
        result = subprocess.run(
            cmd,
            cwd=str(workspace_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=7200  # 2 hour timeout (route+save can take longer)
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
        
        # Collect reports and artifacts
        reports = {}
        rpt_dir = workspace_dir / "pnr_reports"
        
        # Route reports
        route_report_files = [
            ("route_summary.rpt", "route_summary.rpt"),
            ("congestion.rpt", "congestion.rpt"),
            ("postRoute_drc_max1M.rpt", "postRoute_drc_max1M.rpt"),
            ("postOpt_drc_max1M.rpt", "postOpt_drc_max1M.rpt"),
            ("route_timing.rpt.gz", "route_timing.rpt.gz")
        ]
        
        for base_name, file_name in route_report_files:
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
        
        # Check for GDS file (use glob pattern to find *_pnr.gds.gz)
        gds_files = list((workspace_dir / "pnr_out").glob("*_pnr.gds.gz"))
        if gds_files:
            with log_file.open("a") as lf:
                lf.write(f"✓ GDS file found: {gds_files[0].name}\n")
        else:
            with log_file.open("a") as lf:
                lf.write(f"⚠ Warning: GDS file (*_pnr.gds.gz) not found in pnr_out/\n")
        
        return True, "unified route+save completed successfully", reports

    except subprocess.TimeoutExpired:
        return False, "executor timeout (2 hours)", {}
    except Exception as e:
        return False, f"executor error: {e}", {}

def collect_artifacts(workspace_dir: pathlib.Path) -> Dict[str, str]:
    """Collect generated artifacts from pnr_out directory"""
    out_dir = workspace_dir / "pnr_out"
    artifacts: Dict[str, str] = {}
    
    # Artifact patterns based on save server
    art_patterns = [
        ("gds", ["*.gds", "*.gds.gz"]),
        ("def", ["*.def"]),
        ("lef", ["*.lef"]),
        ("spef", ["*.spef", "*.spef.gz"]),
        ("verilog", ["*.v", "*.verilog"]),
    ]
    
    for key, patterns in art_patterns:
        hit = "not found"
        for pat in patterns:
            hits = list(out_dir.glob(pat))
            if hits:
                hit = str(hits[0])
                break
        artifacts[key] = hit
    
    return artifacts

def create_tarball(req: UnifiedRouteSaveReq, artifacts: Dict[str, str], ts: str) -> Optional[str]:
    """Create tarball archive of artifacts"""
    try:
        deliver_dir = ROOT / "deliverables"
        deliver_dir.mkdir(exist_ok=True)
        tar_path = deliver_dir / f"{req.design}_{req.impl_ver}_route_save_{ts}.tgz"
        
        import tarfile
        with tarfile.open(str(tar_path), "w:gz") as tar:
            for fp in artifacts.values():
                if fp != "not found" and pathlib.Path(fp).exists():
                    tar.add(fp, arcname=pathlib.Path(fp).name)
        
        return str(tar_path)
        
    except Exception as e:
        return None

app = FastAPI(title="MCP · Unified Route+Save Service (Routing + Final Save)")

@app.post("/run", response_model=UnifiedRouteSaveResp)
def run_unified_route_save(req: UnifiedRouteSaveReq):
    """Main unified route+save endpoint: TCL generation + executor call"""
    
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_unified_route_save_{ts}.log"
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Phase 1: Setup workspace
        workspace_success, workspace_status, workspace_dir = setup_unified_route_save_workspace(req, log_file)
        if not workspace_success:
            return UnifiedRouteSaveResp(
                status=workspace_status,
                log_path=str(log_file),
                reports={"error": workspace_status},
                artifacts={},
                tcl_path=""
            )
        
        # Phase 2: Generate complete unified route+save TCL file
        tcl_file = generate_complete_unified_route_save_tcl(req, result_dir)
        
        # Phase 3: Call executor to run unified route+save
        exec_success, exec_status, reports = call_unified_route_save_executor(tcl_file, workspace_dir, req, log_file)
        
        if not exec_success:
            return UnifiedRouteSaveResp(
                status=exec_status,
                log_path=str(log_file),
                reports={"error": exec_status},
                artifacts={},
                tcl_path=str(tcl_file)
            )

        # Phase 4: Collect artifacts
        artifacts = collect_artifacts(workspace_dir)
        
        # Phase 5: Create tarball if requested
        tar_path = None
        if req.archive:
            tar_path = create_tarball(req, artifacts, ts)

        # Success
        final_reports = {"workspace": workspace_status, "route_save": exec_status}
        final_reports.update(reports)
        
        return UnifiedRouteSaveResp(
            status="ok",
            log_path=str(log_file),
            reports=final_reports,
            artifacts=artifacts,
            tarball=tar_path,
            tcl_path=str(tcl_file)
        )

    except Exception as e:
        return UnifiedRouteSaveResp(
            status=f"error: {e}",
            log_path=str(log_file),
            reports={"error": str(e)},
            artifacts={},
            tcl_path=""
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("UNIFIED_ROUTE_SAVE_PORT", 13341)),
        help="listen port (env UNIFIED_ROUTE_SAVE_PORT overrides; default 13341)",
    )
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "unified_route_save_server:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
        log_level="info",
    ) 
