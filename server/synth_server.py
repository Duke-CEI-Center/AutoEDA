#!/usr/bin/env python3

import subprocess, pathlib, datetime, os, argparse
from fastapi import FastAPI
from pydantic import BaseModel
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_DIR = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs"))) / "synthesis"
LOG_DIR.mkdir(parents=True, exist_ok=True)

class SynthReq(BaseModel):
    design: str
    tech: str = "FreePDK45"
    version_idx: int = 0  # Keep for compatibility, but not used for CSV lookup
    force: bool = False
    
    # Synthesis configuration parameters (replacing CSV reading)
    syn_version: str = "cpV1_clkP1_drcV1"
    clk_period: float = 1.0
    DRC_max_fanout: int = 10
    DRC_max_transition: float = 0.5
    DRC_max_capacitance: int = 5
    DRC_high_fanout_net_threshold: int = 10
    DRC_high_fanout_pin_capacitance: float = 0.01
    compile_cmd: str = "compile"
    power_effort: str = "high"
    area_effort: str = "high"
    map_effort: str = "high"
    set_dyn_opt: bool = True
    set_lea_opt: bool = True

class SynthResp(BaseModel):
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

def generate_complete_synthesis_tcl(req: SynthReq, result_dir: pathlib.Path) -> pathlib.Path:
    """Generate complete synthesis TCL script with all configurations filled"""
    
    # Parse TOP_NAME from config.tcl
    design_config = ROOT / "designs" / req.design / "config.tcl"
    top_name = parse_top_from_config(design_config) or req.design
    
    # Read all frontend TCL scripts
    frontend_dir = ROOT / "scripts" / req.tech / "frontend"
    if not frontend_dir.exists():
        raise FileNotFoundError(f"Frontend directory not found: {frontend_dir}")
    
    # Get all TCL files in frontend directory, sorted by name
    frontend_scripts = sorted([f for f in frontend_dir.iterdir() if f.suffix == '.tcl'])
    if not frontend_scripts:
        raise FileNotFoundError(f"No TCL scripts found in: {frontend_dir}")
    
    # Read and combine all frontend scripts
    combined_frontend_content = ""
    for script_path in frontend_scripts:
        with open(script_path, "r") as f:
            script_content = f.read()
            combined_frontend_content += f"#===============================================================================\n"
            combined_frontend_content += f"# Frontend Script: {script_path.name}\n"
            combined_frontend_content += f"#===============================================================================\n\n"
            combined_frontend_content += script_content + "\n\n"
    
    # Replace the template's completion marker with our own (in the last script)
    combined_frontend_content = combined_frontend_content.replace(
        "exec touch _Finished_\n\nexit",
        "# Synthesis completed\nexec touch _Done_\n\nexit"
    )
    
    # Define template variables for replacement
    template_variables = {
        "${TOP_NAME}": top_name,
        "$TOP_NAME": top_name,
        "${FILE_FORMAT}": "verilog",
        "$FILE_FORMAT": "verilog",
        "${CLOCK_NAME}": "clk",
        "$CLOCK_NAME": "clk",
        "${RTL_DIR}": "../../../rtl",
        "$RTL_DIR": "../../../rtl",
        "${REPORTS_DIR}": "reports",
        "$REPORTS_DIR": "reports",
        "${RESULTS_DIR}": "results",
        "$RESULTS_DIR": "results",
        "${FINAL_VERILOG_OUTPUT_FILE}": f"{top_name}.mapped.v",
        "$FINAL_VERILOG_OUTPUT_FILE": f"{top_name}.mapped.v",
        "${FINAL_SDC_OUTPUT_FILE}": f"{top_name}.mapped.sdc",
        "$FINAL_SDC_OUTPUT_FILE": f"{top_name}.mapped.sdc",
        "${FINAL_PARSITICS_OUTPUT_FILE}": f"{top_name}.spef.gz",
        "$FINAL_PARSITICS_OUTPUT_FILE": f"{top_name}.spef.gz",
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
    
    # Replace template variables in frontend content
    for placeholder, value in template_variables.items():
        combined_frontend_content = combined_frontend_content.replace(placeholder, value)
    
    # Build environment variables from request parameters
    env_vars = {
        "clk_period": str(req.clk_period),
        "DRC_max_fanout": str(req.DRC_max_fanout),
        "DRC_max_transition": str(req.DRC_max_transition),
        "DRC_max_capacitance": str(req.DRC_max_capacitance),
        "DRC_high_fanout_net_threshold": str(req.DRC_high_fanout_net_threshold),
        "DRC_high_fanout_pin_capacitance": str(req.DRC_high_fanout_pin_capacitance),
        "compile_cmd": req.compile_cmd,
        "power_effort": req.power_effort,
        "area_effort": req.area_effort,
        "map_effort": req.map_effort,
        "set_dyn_opt": str(req.set_dyn_opt).lower(),
        "set_lea_opt": str(req.set_lea_opt).lower(),
    }
    
    # Generate complete synthesis TCL content
    tcl_content = f"""#===============================================================================
# Complete Synthesis TCL Script
# Generated by MCP EDA Server
# Design: {req.design}
# Tech: {req.tech}
# Version: {req.syn_version}
# Generated at: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
#===============================================================================

#-------------------------------------------------------------------------------
# Environment Variables Configuration
#-------------------------------------------------------------------------------
"""
    
    # Add all environment variables
    for var_name, var_value in env_vars.items():
        tcl_content += f"set env({var_name}) \"{var_value}\"\n"
    
    tcl_content += f"""
#-------------------------------------------------------------------------------
# Design Config (from config.tcl)
#-------------------------------------------------------------------------------
{design_config_content}

#-------------------------------------------------------------------------------
# Technology Configuration (from tech.tcl)
#-------------------------------------------------------------------------------
{tech_content}

#-------------------------------------------------------------------------------
# Frontend Scripts (from scripts/{req.tech}/frontend/)
#-------------------------------------------------------------------------------
{combined_frontend_content}

# Replace the exit in synthesis template with our completion marker
# (The synthesis template ends with 'exit', so we add our marker before it)
"""
    
    tcl_path = result_dir / "complete_synthesis.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

def setup_synthesis_workspace(req: SynthReq, log_file: pathlib.Path) -> tuple[bool, str, pathlib.Path]:
    """Setup synthesis workspace directory structure"""
    
    try:
        # Create directories structure
        design_dir = ROOT / "designs" / req.design
        synthesis_dir = design_dir / req.tech / "synthesis"
        syn_version_dir = synthesis_dir / req.syn_version
        
        # Check if version directory already exists
        if syn_version_dir.exists():
            if not req.force:
                with log_file.open("w") as lf:
                    lf.write(f"=== Synthesis Workspace Setup ===\n")
                    lf.write(f"[Warning] {syn_version_dir} already exists! Skipped...\n")
                return True, "workspace ok (already exists)", syn_version_dir
            else:
                # Force overwrite - remove existing directory
                import shutil
                shutil.rmtree(syn_version_dir)
        
        # Create synthesis version directory
        syn_version_dir.mkdir(parents=True, exist_ok=True)
        
        with log_file.open("w") as lf:
            lf.write("=== Synthesis Workspace Setup ===\n")
            lf.write(f"Design: {req.design}\n")
            lf.write(f"Tech: {req.tech}\n")
            lf.write(f"Synthesis Version: {req.syn_version}\n")
            lf.write(f"Created workspace: {syn_version_dir}\n")
            lf.write("Workspace setup completed successfully.\n")

        return True, "workspace ok", syn_version_dir

    except Exception as e:
        return False, f"error: {e}", None

def call_synthesis_executor(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, req: SynthReq, log_file: pathlib.Path) -> tuple[bool, str, dict]:
    """Call the synthesis executor to run EDA tools"""
    
    try:
        # Build executor command
        executor_path = ROOT / "server" / "synth_Executor.py"
        cmd = [
            "python", str(executor_path),
            "-mode", "synthesis",
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
            "/opt/synopsys/syn/V-2023.12-SP2/bin",
            "/tools/cadence/innovus191/bin",
        ]
        current_path = env.get("PATH", "")
        env["PATH"] = ":".join(eda_paths) + ":" + current_path
        
        # Add synthesis configuration to environment
        env_vars = {
            "clk_period": str(req.clk_period),
            "DRC_max_fanout": str(req.DRC_max_fanout),
            "DRC_max_transition": str(req.DRC_max_transition),
            "DRC_max_capacitance": str(req.DRC_max_capacitance),
            "DRC_high_fanout_net_threshold": str(req.DRC_high_fanout_net_threshold),
            "DRC_high_fanout_pin_capacitance": str(req.DRC_high_fanout_pin_capacitance),
            "compile_cmd": req.compile_cmd,
            "power_effort": req.power_effort,
            "area_effort": req.area_effort,
            "map_effort": req.map_effort,
            "set_dyn_opt": str(req.set_dyn_opt).lower(),
            "set_lea_opt": str(req.set_lea_opt).lower(),
        }
        
        for var_name, var_value in env_vars.items():
            env[var_name] = var_value

        with log_file.open("a") as lf:
            lf.write("\n=== Calling Synthesis Executor ===\n")
            lf.write(f"Executor: {executor_path}\n")
            lf.write(f"TCL File: {tcl_file}\n")
            lf.write(f"Workspace: {workspace_dir}\n")
            lf.write(f"Command: {' '.join(cmd)}\n\n")
            
            # Execute the synthesis using executor
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
            return False, f"error: executor failed with code {process.returncode}", {}

        # Check for completion marker
        done_file = workspace_dir / "_Done_"
        if not done_file.exists():
            return False, "error: synthesis did not complete successfully (_Done_ file not found)", {}

        # Collect synthesis reports
        reports_dir = workspace_dir / "reports"
        reports = {}
        for rpt in ("qor.rpt", "timing.rpt", "area.rpt", "power.rpt"):
            rpt_path = reports_dir / rpt
            if rpt_path.exists():
                reports[rpt] = rpt_path.read_text()
            else:
                reports[rpt] = f"{rpt} not found"

        return True, "synthesis completed successfully", reports

    except Exception as e:
        return False, f"error: {e}", {}

app = FastAPI(title="MCP · Synthesis Server")

@app.post("/run", response_model=SynthResp)
def run_synthesis(req: SynthReq):
    """Main synthesis endpoint: TCL generation + executor call"""
    
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_synthesis_{ts}.log"
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Phase 1: Setup workspace
        workspace_success, workspace_status, workspace_dir = setup_synthesis_workspace(req, log_file)
        if not workspace_success:
            return SynthResp(
                status=workspace_status,
                log_path=str(log_file),
                reports={"error": workspace_status},
                tcl_path=""
            )
        
        # Phase 2: Generate complete TCL file with all configurations
        tcl_file = generate_complete_synthesis_tcl(req, result_dir)
        
        # Phase 3: Call executor to run synthesis
        exec_success, exec_status, reports = call_synthesis_executor(tcl_file, workspace_dir, req, log_file)
        
        if not exec_success:
            return SynthResp(
                status=exec_status,
                log_path=str(log_file),
                reports={"error": exec_status},
                tcl_path=str(tcl_file)
            )

        # Success
        final_reports = {"workspace": workspace_status, "synthesis": exec_status}
        final_reports.update(reports)
        
        return SynthResp(
            status="ok",
            log_path=str(log_file),
            reports=final_reports,
            tcl_path=str(tcl_file)
        )

    except Exception as e:
        return SynthResp(
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
        default=int(os.getenv("SYN_PORT", 13333)),
        help="listen port (env SYN_PORT overrides; default 13333)",
    )
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "synth_server:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
        log_level="info",
    ) 