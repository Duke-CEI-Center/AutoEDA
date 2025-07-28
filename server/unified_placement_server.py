#!/usr/bin/env python3

import subprocess, pathlib, datetime, os, argparse
from fastapi import FastAPI
from pydantic import BaseModel
import re
from typing import Optional

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_DIR = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs"))) / "unified_placement"
LOG_DIR.mkdir(parents=True, exist_ok=True)

class UnifiedPlacementReq(BaseModel):
    design: str
    tech: str = "FreePDK45"
    syn_ver: str
    force: bool = False
    top_module: Optional[str] = None
    
    # Floorplan configuration parameters
    design_flow_effort: str = "standard"  # express, standard
    design_power_effort: str = "none"     # none, medium, high
    ASPECT_RATIO: float = 1.0             # die aspect ratio
    target_util: float = 0.7              # target utilization
    clock_name: str = "clk"               # clock signal name
    clock_period: float = 1.0             # clock period
    
    # Placement parameters
    place_global_timing_effort: str = "medium"   # low, medium, high
    place_global_cong_effort: str = "medium"     # low, medium, high
    place_detail_wire_length_opt_effort: str = "medium"  # low, medium, high
    place_global_max_density: float = 0.9        # max density
    place_activity_power_driven: bool = False    # power driven placement
    prects_opt_max_density: float = 0.8          # pre-CTS optimization density
    prects_opt_power_effort: str = "low"         # none, low, medium, high
    prects_opt_reclaim_area: bool = False        # reclaim area during optimization
    prects_fix_fanout_load: bool = False         # fix fanout load violations

class UnifiedPlacementResp(BaseModel):
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

def generate_complete_unified_placement_tcl(req: UnifiedPlacementReq, result_dir: pathlib.Path) -> pathlib.Path:
    """Generate complete unified placement TCL script combining floorplan, powerplan, and placement"""
    
    # Parse TOP_NAME from config.tcl
    design_config = ROOT / "designs" / req.design / "config.tcl"
    top_name = parse_top_from_config(design_config) or req.top_module or req.design
    
    # Define synthesis results directory
    syn_res_dir = ROOT / "designs" / req.design / req.tech / "synthesis" / req.syn_ver / "results"
    
    # Read design config
    design_config_content = ""
    if design_config.exists():
        design_config_content = design_config.read_text()
    
    # Read tech config
    tech_tcl_path = ROOT / "scripts" / req.tech / "tech.tcl"
    tech_content = ""
    if tech_tcl_path.exists():
        tech_content = tech_tcl_path.read_text()
    
    # Read all backend TCL scripts in sequence: 1_setup, 2_floorplan, 3_powerplan, 4_place
    backend_dir = ROOT / "scripts" / req.tech / "backend"
    if not backend_dir.exists():
        raise FileNotFoundError(f"Backend directory not found: {backend_dir}")
    
    # Get backend scripts in order
    backend_scripts = [
        backend_dir / "1_setup.tcl",
        backend_dir / "2_floorplan.tcl",
        backend_dir / "3_powerplan.tcl",
        backend_dir / "4_place.tcl"
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
        
        # File and directory paths
        "${NETLIST_DIR}": str(syn_res_dir),
        "$NETLIST_DIR": str(syn_res_dir),
        "${FILE_FORMAT}": "verilog",
        "$FILE_FORMAT": "verilog",
        "${VERILOG_FILE}": f"{syn_res_dir}/{top_name}.mapped.v",
        "$VERILOG_FILE": f"{syn_res_dir}/{top_name}.mapped.v",
        "${SDC_FILE}": f"{syn_res_dir}/{top_name}.mapped.sdc",
        "$SDC_FILE": f"{syn_res_dir}/{top_name}.mapped.sdc",
        
        # Clock parameters
        "${CLOCK_NAME}": req.clock_name,
        "$CLOCK_NAME": req.clock_name,
        "${clk_period}": str(req.clock_period),
        "$clk_period": str(req.clock_period),
        
        # Floorplan parameters
        "${ASPECT_RATIO}": str(req.ASPECT_RATIO),
        "$ASPECT_RATIO": str(req.ASPECT_RATIO),
        "${target_util}": str(req.target_util),
        "$target_util": str(req.target_util),
        "${env(target_util)}": str(req.target_util),
        "$env(target_util)": str(req.target_util),
        
        # Global design parameters
        "${design_flow_effort}": req.design_flow_effort,
        "$design_flow_effort": req.design_flow_effort,
        "${design_power_effort}": req.design_power_effort,
        "$design_power_effort": req.design_power_effort,
        "${env(design_flow_effort)}": req.design_flow_effort,
        "$env(design_flow_effort)": req.design_flow_effort,
        "${env(design_power_effort)}": req.design_power_effort,
        "$env(design_power_effort)": req.design_power_effort,
        
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
        
        # Base directory
        "${env(BASE_DIR)}": str(ROOT),
        "$env(BASE_DIR)": str(ROOT),
    }
    
    # Apply template variable replacements to all content
    for placeholder, value in template_variables.items():
        design_config_content = design_config_content.replace(placeholder, value)
        tech_content = tech_content.replace(placeholder, value)
        combined_backend_content = combined_backend_content.replace(placeholder, value)
    
    # Combine all content into a single TCL file with explicit environment variable settings
    tcl_content = f"""#===============================================================================
# Complete Unified Placement TCL Script (Floorplan + Powerplan + Placement)
# Generated by MCP EDA Server
# Design: {req.design}
# Tech: {req.tech}
# Synthesis Version: {req.syn_ver}
# Generated at: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
#===============================================================================

#-------------------------------------------------------------------------------
# Set environment variables explicitly
#-------------------------------------------------------------------------------
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

#-------------------------------------------------------------------------------
# Design Config (from config.tcl)
#-------------------------------------------------------------------------------
{design_config_content}

#-------------------------------------------------------------------------------
# Technology Configuration (from tech.tcl)
#-------------------------------------------------------------------------------
{tech_content}

#-------------------------------------------------------------------------------
# Backend Scripts (1_setup.tcl + 2_floorplan.tcl + 3_powerplan.tcl + 4_place.tcl)
#-------------------------------------------------------------------------------
{combined_backend_content}

#-------------------------------------------------------------------------------
# Save final placement
#-------------------------------------------------------------------------------
saveDesign pnr_save/placement.enc
defOut pnr_out/place.def
streamOut pnr_out/{top_name}_place.gds.gz

# Unified placement completed
exec touch _Done_
exit
"""
    
    # Apply template replacements to the final combined TCL content
    for placeholder, value in template_variables.items():
        tcl_content = tcl_content.replace(placeholder, value)
    
    tcl_path = result_dir / "complete_unified_placement.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

def setup_unified_placement_workspace(req: UnifiedPlacementReq, log_file: pathlib.Path) -> tuple[bool, str, pathlib.Path]:
    """Setup unified placement workspace directory structure"""
    
    try:
        # Create implementation version directory
        design_dir = ROOT / "designs" / req.design
        impl_dir = design_dir / req.tech / "implementation" / f"{req.syn_ver}__g0_p0"
        
        # Check if directories exist
        if impl_dir.exists():
            if not req.force:
                with log_file.open("w") as lf:
                    lf.write(f"=== Unified Placement Workspace Setup ===\n")
                    lf.write(f"[Warning] {impl_dir} already exists! Skipped...\n")
                return True, "workspace ok (already exists)", impl_dir
            else:
                # Force overwrite - remove existing output directories
                import shutil
                for subdir in ["pnr_save", "pnr_out", "pnr_reports"]:
                    target_dir = impl_dir / subdir
                    if target_dir.exists():
                        shutil.rmtree(target_dir)
        
        # Create all necessary subdirectories
        impl_dir.mkdir(parents=True, exist_ok=True)
        (impl_dir / "pnr_save").mkdir(exist_ok=True)
        (impl_dir / "pnr_out").mkdir(exist_ok=True)
        (impl_dir / "pnr_reports").mkdir(exist_ok=True)
        
        with log_file.open("w") as lf:
            lf.write("=== Unified Placement Workspace Setup ===\n")
            lf.write(f"Design: {req.design}\n")
            lf.write(f"Tech: {req.tech}\n")
            lf.write(f"Synthesis Version: {req.syn_ver}\n")
            lf.write(f"Implementation Directory: {impl_dir}\n")
            lf.write("Workspace setup completed successfully.\n")

        return True, "workspace ok", impl_dir

    except Exception as e:
        return False, f"error: {e}", None

def call_unified_placement_executor(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, req: UnifiedPlacementReq, log_file: pathlib.Path) -> tuple[bool, str, dict]:
    """Call the unified placement executor to run EDA tools"""
    
    try:
        # Build executor command
        executor_path = ROOT / "server" / "unified_placement_Executor.py"
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
        
        # Execute the unified placement executor
        with log_file.open("a") as lf:
            lf.write(f"\n=== Calling Unified Placement Executor ===\n")
            lf.write(f"Command: {' '.join(cmd)}\n")
            lf.write(f"Working Directory: {workspace_dir}\n")
            lf.write(f"Executor started at: {datetime.datetime.now()}\n\n")
        
        result = subprocess.run(
            cmd,
            cwd=str(workspace_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
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
            ("floorplan_summary.rpt", "floorplan_summary.rpt.gz"),
            ("check_place.out", "check_place.out"),
            ("place_timing.rpt", "place_timing.rpt.gz"),
            ("place_opt_timing.rpt", "place_opt_timing.rpt.gz")
        ]
        
        for base_name, gz_name in report_files:
            for name in [base_name, gz_name]:
                rpt_path = rpt_dir / name
                if rpt_path.exists():
                    try:
                        if name.endswith('.gz'):
                            import gzip
                            with gzip.open(rpt_path, 'rt') as f:
                                reports[base_name] = f.read()
                        else:
                            reports[base_name] = rpt_path.read_text()
                        break
                    except Exception as e:
                        reports[base_name] = f"Error reading {name}: {e}"
                else:
                    reports[base_name] = "Report not found"
        
        return True, "unified placement completed successfully", reports

    except subprocess.TimeoutExpired:
        return False, "executor timeout (1 hour)", {}
    except Exception as e:
        return False, f"executor error: {e}", {}

app = FastAPI(title="MCP · Unified Placement Service (Floorplan + Powerplan + Placement)")

@app.post("/run", response_model=UnifiedPlacementResp)
def run_unified_placement(req: UnifiedPlacementReq):
    """Main unified placement endpoint: TCL generation + executor call"""
    
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_unified_placement_{ts}.log"
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Phase 1: Setup workspace
        workspace_success, workspace_status, workspace_dir = setup_unified_placement_workspace(req, log_file)
        if not workspace_success:
            return UnifiedPlacementResp(
                status=workspace_status,
                log_path=str(log_file),
                reports={"error": workspace_status},
                tcl_path=""
            )
        
        # Phase 2: Generate complete unified placement TCL file
        tcl_file = generate_complete_unified_placement_tcl(req, result_dir)
        
        # Phase 3: Call executor to run unified placement
        exec_success, exec_status, reports = call_unified_placement_executor(tcl_file, workspace_dir, req, log_file)
        
        if not exec_success:
            return UnifiedPlacementResp(
                status=exec_status,
                log_path=str(log_file),
                reports={"error": exec_status},
                tcl_path=str(tcl_file)
            )

        # Success
        final_reports = {"workspace": workspace_status, "placement": exec_status}
        final_reports.update(reports)
        
        return UnifiedPlacementResp(
            status="ok",
            log_path=str(log_file),
            reports=final_reports,
            tcl_path=str(tcl_file)
        )

    except Exception as e:
        return UnifiedPlacementResp(
            status=f"error: {e}",
            log_path=str(log_file),
            reports={"error": str(e)},
            tcl_path=""
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("UNIFIED_PLACEMENT_PORT", 13340)),
        help="listen port (env UNIFIED_PLACEMENT_PORT overrides; default 13340)",
    )
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "unified_placement_server:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
        log_level="info",
    ) 
