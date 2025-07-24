#!/usr/bin/env python3

import subprocess, pathlib, datetime, os, argparse
from fastapi import FastAPI
from pydantic import BaseModel
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_DIR = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs"))) / "floorplan"
LOG_DIR.mkdir(parents=True, exist_ok=True)

class FPReq(BaseModel):
    design: str
    tech: str = "FreePDK45"
    syn_ver: str
    force: bool = False
    top_module: str = None
    restore_enc: str = None
    
    # Floorplan configuration parameters (replacing CSV reading)
    design_flow_effort: str = "standard"  # express, standard
    design_power_effort: str = "none"     # none, medium, high
    ASPECT_RATIO: float = 1.0             # die aspect ratio
    target_util: float = 0.7              # target utilization
    clock_name: str = "clk"               # clock signal name
    clock_period: float = 1.0             # clock period

class FPResp(BaseModel):
    status: str
    log_path: str
    report: str
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

def generate_complete_floorplan_tcl(req: FPReq, result_dir: pathlib.Path) -> pathlib.Path:
    """Generate complete floorplan TCL script with all configurations filled"""
    
    # Parse TOP_NAME from config.tcl
    design_config = ROOT / "designs" / req.design / "config.tcl"
    top_name = parse_top_from_config(design_config) or req.top_module or req.design
    
    # Define synthesis results directory
    syn_res_dir = ROOT / "designs" / req.design / req.tech / "synthesis" / req.syn_ver / "results"
    
    # Read all backend TCL scripts
    backend_dir = ROOT / "scripts" / req.tech / "backend"
    if not backend_dir.exists():
        raise FileNotFoundError(f"Backend directory not found: {backend_dir}")
    
    # Get backend scripts in order
    backend_scripts = [
        backend_dir / "1_setup.tcl",
        backend_dir / "2_floorplan.tcl"
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
    
    # Define template variables for replacement
    template_variables = {
        "${TOP_NAME}": top_name,
        "$TOP_NAME": top_name,
        "${NETLIST_DIR}": str(syn_res_dir),
        "$NETLIST_DIR": str(syn_res_dir),
        "${FILE_FORMAT}": "verilog",
        "$FILE_FORMAT": "verilog",
        "${CLOCK_NAME}": req.clock_name,
        "$CLOCK_NAME": req.clock_name,
        "${clk_period}": str(req.clock_period),
        "$clk_period": str(req.clock_period),
        "${ASPECT_RATIO}": str(req.ASPECT_RATIO),
        "$ASPECT_RATIO": str(req.ASPECT_RATIO),
        "${target_util}": str(req.target_util),
        "$target_util": str(req.target_util),
        "${VERILOG_FILE}": f"{syn_res_dir}/{top_name}.mapped.v",
        "$VERILOG_FILE": f"{syn_res_dir}/{top_name}.mapped.v",
        "${SDC_FILE}": f"{syn_res_dir}/{top_name}.mapped.sdc",
        "$SDC_FILE": f"{syn_res_dir}/{top_name}.mapped.sdc",
    }
    
    # Read tech.tcl content
    tech_tcl_path = ROOT / "scripts" / req.tech / "tech.tcl"
    if not tech_tcl_path.exists():
        raise FileNotFoundError(f"Tech file not found: {tech_tcl_path}")
        
    with open(tech_tcl_path, "r") as f:
        tech_content = f.read()
    
    # Replace template variables in tech config
    for placeholder, value in template_variables.items():
        tech_content = tech_content.replace(placeholder, value)
    
    # Read design config.tcl content  
    if not design_config.exists():
        raise FileNotFoundError(f"Design config not found: {design_config}")
        
    with open(design_config, "r") as f:
        design_config_content = f.read()
    
    # Replace template variables in design config
    for placeholder, value in template_variables.items():
        design_config_content = design_config_content.replace(placeholder, value)
    
    # Replace template variables in backend content
    for placeholder, value in template_variables.items():
        combined_backend_content = combined_backend_content.replace(placeholder, value)
    
    # Build environment variables from request parameters
    env_vars = {
        "BASE_DIR": str(ROOT),
        "NETLIST_DIR": str(syn_res_dir),
        "TOP_NAME": top_name,
        "FILE_FORMAT": "verilog",
        "CLOCK_NAME": req.clock_name,
        "clk_period": str(req.clock_period),
        "design_flow_effort": req.design_flow_effort,
        "design_power_effort": req.design_power_effort,
        "ASPECT_RATIO": str(req.ASPECT_RATIO),
        "target_util": str(req.target_util),
    }
    
    # Handle restore command if provided
    restore_cmd = ""
    if req.restore_enc:
        restore_abs = pathlib.Path(req.restore_enc).resolve()
        if not restore_abs.exists():
            raise FileNotFoundError(f"Restore file not found: {restore_abs}")
        restore_cmd = f'restoreDesign "{restore_abs}" {top_name};\n'
    
    # Generate complete floorplan TCL content
    tcl_content = f"""#===============================================================================
# Complete Floorplan TCL Script
# Generated by MCP EDA Server
# Design: {req.design}
# Tech: {req.tech}
# Synthesis Version: {req.syn_ver}
# Generated at: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
#===============================================================================

#-------------------------------------------------------------------------------
# Environment Variables Configuration
#-------------------------------------------------------------------------------
"""
    
    # Add all environment variables
    for var_name, var_value in env_vars.items():
        tcl_content += f'set env({var_name}) "{var_value}"\n'
    
    tcl_content += f"""
#-------------------------------------------------------------------------------
# Set Global Variables
#-------------------------------------------------------------------------------
set NETLIST_DIR "{syn_res_dir}"
set TOP_NAME "{top_name}"
set FILE_FORMAT "verilog"
set CLOCK_NAME "{req.clock_name}"
set clk_period {req.clock_period}

#-------------------------------------------------------------------------------
# Create Output Directories
#-------------------------------------------------------------------------------
file mkdir pnr_logs
file mkdir pnr_out
file mkdir pnr_reports
file mkdir pnr_save

#-------------------------------------------------------------------------------
# Design Config (from config.tcl)
#-------------------------------------------------------------------------------
{design_config_content}

#-------------------------------------------------------------------------------
# Technology Configuration (from tech.tcl)
#-------------------------------------------------------------------------------
{tech_content}

#-------------------------------------------------------------------------------
# Restore Design (if provided)
#-------------------------------------------------------------------------------
{restore_cmd}

#-------------------------------------------------------------------------------
# Backend Scripts (from scripts/{req.tech}/backend/)
#-------------------------------------------------------------------------------
{combined_backend_content}

# Mark completion
exec touch _Done_

"""
    
    tcl_path = result_dir / "complete_floorplan.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

def setup_floorplan_workspace(req: FPReq, log_file: pathlib.Path) -> tuple[bool, str, pathlib.Path]:
    """Setup floorplan workspace directory structure"""
    
    try:
        # Verify synthesis results exist
        syn_res_dir = ROOT / "designs" / req.design / req.tech / "synthesis" / req.syn_ver / "results"
        if not syn_res_dir.exists():
            return False, f"error: synthesis results not found at {syn_res_dir}", None
        
        # Create implementation directory structure
        impl_ver = f"{req.syn_ver}__g0_p0"  # Simplified version naming
        impl_dir = ROOT / "designs" / req.design / req.tech / "implementation" / impl_ver
        
        # Check if implementation directory already exists
        if impl_dir.exists():
            if not req.force:
                with log_file.open("w") as lf:
                    lf.write(f"=== Floorplan Workspace Setup ===\n")
                    lf.write(f"[Warning] {impl_dir} already exists! Skipped...\n")
                return True, "workspace ok (already exists)", impl_dir
            else:
                # Force overwrite - remove existing directory
                import shutil
                shutil.rmtree(impl_dir)
        
        # Create implementation directory and subdirectories
        impl_dir.mkdir(parents=True, exist_ok=True)
        (impl_dir / "pnr_save").mkdir(exist_ok=True)
        (impl_dir / "pnr_logs").mkdir(exist_ok=True)
        (impl_dir / "pnr_out").mkdir(exist_ok=True)
        (impl_dir / "pnr_reports").mkdir(exist_ok=True)
        
        # Copy config.tcl to implementation directory
        design_config = ROOT / "designs" / req.design / "config.tcl"
        local_config = impl_dir / "config.tcl"
        if design_config.exists() and not local_config.exists():
            import shutil
            shutil.copy2(design_config, local_config)
        
        with log_file.open("w") as lf:
            lf.write("=== Floorplan Workspace Setup ===\n")
            lf.write(f"Design: {req.design}\n")
            lf.write(f"Tech: {req.tech}\n")
            lf.write(f"Synthesis Version: {req.syn_ver}\n")
            lf.write(f"Implementation Version: {impl_ver}\n")
            lf.write(f"Created workspace: {impl_dir}\n")
            lf.write("Workspace setup completed successfully.\n")

        return True, "workspace ok", impl_dir

    except Exception as e:
        return False, f"error: {e}", None

def call_floorplan_executor(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, req: FPReq, log_file: pathlib.Path) -> tuple[bool, str, str]:
    """Call the floorplan executor to run EDA tools"""
    
    try:
        # Build executor command
        executor_path = ROOT / "server" / "floorplan_Executor.py"
        cmd = [
            "python", str(executor_path),
            "-mode", "floorplan",
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
        current_path = env.get("PATH", "")
        env["PATH"] = ":".join(eda_paths) + ":" + current_path
        
        # Add floorplan configuration to environment
        env_vars = {
            "NETLIST_DIR": str(ROOT / "designs" / req.design / req.tech / "synthesis" / req.syn_ver / "results"),
            "TOP_NAME": req.top_module or req.design,
            "FILE_FORMAT": "verilog",
            "CLOCK_NAME": req.clock_name,
            "clk_period": str(req.clock_period),
            "design_flow_effort": req.design_flow_effort,
            "design_power_effort": req.design_power_effort,
            "ASPECT_RATIO": str(req.ASPECT_RATIO),
            "target_util": str(req.target_util),
        }
        
        for var_name, var_value in env_vars.items():
            env[var_name] = var_value

        with log_file.open("a") as lf:
            lf.write("\n=== Calling Floorplan Executor ===\n")
            lf.write(f"Executor: {executor_path}\n")
            lf.write(f"TCL File: {tcl_file}\n")
            lf.write(f"Workspace: {workspace_dir}\n")
            lf.write(f"Command: {' '.join(cmd)}\n\n")
            
            # Execute the floorplan using executor
            process = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                universal_newlines=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
            )
            for line in process.stdout:
                lf.write(line)
            process.wait()

        if process.returncode != 0:
            return False, f"error: executor failed with code {process.returncode}", ""

        # Check for completion marker
        done_file = workspace_dir / "_Done_"
        if not done_file.exists():
            return False, "error: floorplan did not complete successfully (_Done_ file not found)", ""

        # Check for expected output file
        enc_path = workspace_dir / "pnr_save" / "floorplan.enc.dat"
        if not enc_path.exists():
            return False, "error: floorplan did not produce floorplan.enc.dat", ""

        # Collect floorplan report
        import glob, gzip
        rpt_dir = workspace_dir / "pnr_reports"
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

        return True, "floorplan completed successfully", rpt_text

    except Exception as e:
        return False, f"error: {e}", ""

app = FastAPI(title="MCP · Floorplan Server")

@app.post("/run", response_model=FPResp)
def run_floorplan(req: FPReq):
    """Main floorplan endpoint: TCL generation + executor call"""
    
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_floorplan_{ts}.log"
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Phase 1: Setup workspace
        workspace_success, workspace_status, workspace_dir = setup_floorplan_workspace(req, log_file)
        if not workspace_success:
            return FPResp(
                status=workspace_status,
                log_path=str(log_file),
                report=workspace_status,
                tcl_path=""
            )
        
        # Phase 2: Generate complete TCL file with all configurations
        tcl_file = generate_complete_floorplan_tcl(req, result_dir)
        
        # Phase 3: Call executor to run floorplan
        exec_success, exec_status, report = call_floorplan_executor(tcl_file, workspace_dir, req, log_file)
        
        if not exec_success:
            return FPResp(
                status=exec_status,
                log_path=str(log_file),
                report=exec_status,
                tcl_path=str(tcl_file)
            )

        # Success
        return FPResp(
            status="ok",
            log_path=str(log_file),
            report=report,
            tcl_path=str(tcl_file)
        )

    except Exception as e:
        return FPResp(
            status=f"error: {e}",
            log_path=str(log_file),
            report=str(e),
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
        log_level="info",
    )