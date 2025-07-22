#!/usr/bin/env python3

import subprocess, pathlib, datetime, os, argparse
from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import re
from jinja2 import Template

# Load environment variables from the .env file
from dotenv import load_dotenv
load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_DIR = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs"))) / "synthesis"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Request/Response Models
# ============================================================================

class SynthReq(BaseModel):
    version_idx: int = 0 ## Temporary, will be removed later
    design: str
    tech: str = "FreePDK45"
    top_name: str = "" 
    period: float = 1.0 
    fanout_limit: int = 10  
    transition_limit: float = 0.2 
    capacitance_limit: float = 4.5
    high_fanout_net_threshold: int = 64
    high_fanout_net_pin_capacitance: float = 0.15
    compile_cmd: str = "compile_ultra"
    power_effort: str = "medium"
    area_effort: str = "high"
    map_effort: str = "medium"
    dynamic_optimization: bool = True
    leakage_optimization: bool = False
    force: bool = False

# params = {
#         "design": req.design,
#         "tech": req.tech,
#         "TOP_NAME": top_name,
#         "period": getattr(req, 'period', 1.0),  # Default to 1.0 if not provided
#         "fanout_limit": getattr(req, 'fanout_limit', 10),  
#         "transition_limit": getattr(req, 'transition_limit', 0.2),
#         "capacitance_limit": getattr(req, 'capacitance_limit', 4.5),
#         "high_fanout_net_threshold": getattr(req, 'high_fanout_net_threshold', 64),
#         "high_fanout_net_pin_capacitance": getattr(req, 'high_fanout_net_pin_capacitance', 0.15),
#         "compile_cmd": getattr(req, 'compile_cmd', "compile_ultra"),
#         "power_effort": getattr(req, 'power_effort', "medium"),
#         "area_effort": getattr(req, 'area_effort', "high"),
#         "map_effort": getattr(req, 'map_effort', "medium"),
#         "dynamic_optimization": getattr(req, 'dynamic_optimization', True),
#         "leakage_optimization": getattr(req, 'leakage_optimization', False),
#         "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#     }

class SynthResp(BaseModel):
    status: str
    log_path: str
    reports: dict
    tcl_path: str

# ============================================================================
# Utility Functions
# ============================================================================

def parse_top_from_config(config_path: pathlib.Path) -> str:
    """Parse TOP_NAME from config.tcl"""
    if not config_path.exists():
        return None
    content = config_path.read_text()
    m = re.search(r'set\s+TOP_NAME\s+"([^"]+)"', content)
    if m:
        return m.group(1)
    return None

# ============================================================================
# Setup Phase Functions (from synth_setup_server.py)
# ============================================================================

def generate_setup_tcl(req: SynthReq, result_dir: pathlib.Path) -> pathlib.Path:
    """Generate synthesis setup TCL script from configuration"""
    
    # Parse TOP_NAME from config.tcl
    design_config = ROOT / "designs" / req.design / "config.tcl"
    req.top_name = parse_top_from_config(design_config) or req.design

    # Load the synthesis setup template
    template_path = ROOT / "scripts" / "FreePDK45" / "frontend" / "1_setup.tcl"
    if not template_path.exists():
        raise FileNotFoundError(f"Synthesis setup template not found: {template_path}")
    tcl_template = template_path.read_text()

    # Render the template
    tcl_content = Template(tcl_template).render(**vars(req))
    
    tcl_path = result_dir / "setup.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

def execute_setup_phase(req: SynthReq, log_file: pathlib.Path, result_dir: pathlib.Path) -> tuple[bool, str, pathlib.Path]:
    """Execute the setup phase (from original synth_setup_server logic)"""
    
    try:
        # Generate setup TCL
        setup_tcl_path = generate_setup_tcl(req, result_dir)
        
        # Create executor command (using setup mode)
        executor_path = ROOT / "server" / "synth_Executor.py"
        cmd = [
            "bash", "-c", 
            f"source ~/miniconda3/etc/profile.d/conda.sh && conda activate eda310 && python {executor_path} -mode setup -design {req.design} -technode {req.tech} -tcl {setup_tcl_path} -version_idx {req.version_idx}" + (" -force" if req.force else "")
        ]

        # Execute the setup using executor
        with log_file.open("w") as lf:
            lf.write("=== Synthesis Setup Phase ===\n")
            lf.write(f"Command: {' '.join(cmd)}\n\n")
            
            process = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=lf,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            process.wait()

        if process.returncode != 0:
            print(f"Conda failed: trying with venv...")

            # Fallback to using venv if Conda fails    # temporary !!!!
            # Command using venv
            venv_path = "venv"  
            cmd_venv = [
                "bash", "-c",
                f"source {venv_path}/bin/activate && python {executor_path} -mode setup -design {req.design} -technode {req.tech} -tcl {setup_tcl_path} -version_idx {req.version_idx}" + (" -force" if req.force else "")
            ]
            
            with log_file.open("w") as lf:
                lf.write("=== Synthesis Setup Phase ===\n")
                lf.write(f"Command: {' '.join(cmd_venv)}\n\n")

                # Execute the setup using venv        
                process_venv = subprocess.Popen(
                    cmd_venv,
                    cwd=str(ROOT),
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                process_venv.wait()

            if process_venv.returncode != 0:
                return False, f"error: setup executor failed with code {process_venv.returncode}", setup_tcl_path
            
            # return False, f"error: setup executor failed with code {process.returncode}", setup_tcl_path 

        # Check for setup results (from original logic)
        synth_root = ROOT / "designs" / req.design / req.tech / "synthesis"
        if not synth_root.exists():
            return False, "error: synthesis directory not created", setup_tcl_path

        # Find the latest synthesis version
        latest_ver = max(synth_root.iterdir(), key=lambda p: p.stat().st_mtime)
        
        # Check for setup completion
        done_file = latest_ver / "_Finished_"
        if not done_file.exists():
            return False, "error: setup did not complete successfully", setup_tcl_path

        return True, "setup ok", setup_tcl_path

    except Exception as e:
        return False, f"error: {e}", result_dir / "setup.tcl"

# ============================================================================
# Compile Phase Functions (from synth_compile_server.py)
# ============================================================================

def generate_compile_tcl(req: SynthReq, result_dir: pathlib.Path, synthesis_dir: pathlib.Path) -> pathlib.Path:
    """Generate synthesis compile TCL script from templates"""
    
    # Parse TOP_NAME from config.tcl
    design_config = ROOT / "designs" / req.design / "config.tcl"
    req.top_name = parse_top_from_config(design_config) or req.design

    # Load the synthesis setup template
    template_path = ROOT / "scripts" / "FreePDK45" / "frontend" / "2_synthesis.tcl"
    if not template_path.exists():
        raise FileNotFoundError(f"Synthesis setup template not found: {template_path}")
    tcl_template = template_path.read_text()

    # Render the template
    tcl_content = Template(tcl_template).render(**vars(req))
    
    tcl_path = result_dir / "compile.tcl"
    tcl_path.write_text(tcl_content)
    return tcl_path

def execute_compile_phase(req: SynthReq, log_file: pathlib.Path, result_dir: pathlib.Path) -> tuple[bool, str, pathlib.Path, dict]:
    """Execute the compile phase (from original synth_compile_server logic)"""
    
    try:
        # Find synthesis directory (from original compile server logic)
        synth_root = ROOT / "designs" / req.design / req.tech / "synthesis"
        if not synth_root.exists():
            return False, "error: synthesis directory not found", result_dir / "compile.tcl", {}

        # Find the synthesis version directory based on version_idx
        config_path = ROOT / "config" / "synthesis.csv"
        config_pd = pd.read_csv(config_path, index_col='version')
        syn_version = config_pd.index[req.version_idx]
        
        synthesis_dir = synth_root / syn_version
        if not synthesis_dir.exists():
            return False, f"error: synthesis version {syn_version} not found", result_dir / "compile.tcl", {}

        # Generate compile TCL
        compile_tcl_path = generate_compile_tcl(req, result_dir, synthesis_dir)
        
        # Create executor command (using compile mode)
        executor_path = ROOT / "server" / "synth_Executor.py"
        cmd = [
            "bash", "-c",
            f"source ~/miniconda3/etc/profile.d/conda.sh && conda activate eda310 && python {executor_path} -mode compile -design {req.design} -technode {req.tech} -tcl {compile_tcl_path} -synthesis_dir {synthesis_dir} -version_idx {req.version_idx}" + (" -force" if req.force else "")
        ]

        # Execute the compilation using executor
        with log_file.open("a") as lf:
            lf.write("\n=== Synthesis Compile Phase ===\n")
            lf.write(f"Command: {' '.join(cmd)}\n\n")
            
            process = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=lf,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            process.wait()

        if process.returncode != 0:
            print(f"Conda failed: trying with venv...")

            # Fallback to using venv if Conda fails    # temporary !!!!
            # Command using venv
            venv_path = "venv"  
            cmd_venv = [
                "bash", "-c",
                f"source {venv_path}/bin/activate && python {executor_path} -mode compile -design {req.design} -technode {req.tech} -tcl {compile_tcl_path} -synthesis_dir {synthesis_dir} -version_idx {req.version_idx}" + (" -force" if req.force else "")
            ]
            
            # Execute the compilation using executor
            with log_file.open("a") as lf:
                lf.write("\n=== Synthesis Compile Phase ===\n")
                lf.write(f"Command: {' '.join(cmd_venv)}\n\n")
                
                process_venv = subprocess.Popen(
                    cmd_venv,
                    cwd=str(ROOT),
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                process_venv.wait()

            if process_venv.returncode != 0:
                return False, f"error: compile executor failed with code {process.returncode}", compile_tcl_path, {}
            
            # return False, f"error: compile executor failed with code {process.returncode}", compile_tcl_path, {}

        # Collect synthesis reports (from original compile server logic)
        reports_dir = synthesis_dir / "reports"
        reports = {}
        
        for rpt in ("qor.rpt", "timing.rpt", "area.rpt", "power.rpt", "check_design.rpt"):
            rpt_path = reports_dir / rpt
            if rpt_path.exists():
                reports[rpt] = rpt_path.read_text()
            else:
                reports[rpt] = f"{rpt} not found"

        return True, "compile ok", compile_tcl_path, reports

    except Exception as e:
        return False, f"error: {e}", result_dir / "compile.tcl", {}

# ============================================================================
# FastAPI App and Endpoints
# ============================================================================

app = FastAPI(title="MCP · Synthesis Service")

@app.post("/run", response_model=SynthResp)
def synth_run(req: SynthReq):
    """Unified Synthesis Endpoint - combines setup and compile phases"""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_synthesis_{ts}.log"

    # Create result directory for generated TCL
    result_dir = ROOT / "result" / req.design / req.tech
    result_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: Execute Setup
    setup_success, setup_status, setup_tcl_path = execute_setup_phase(req, log_file, result_dir)
    
    if not setup_success:
        return SynthResp(
            status=setup_status,
            log_path=str(log_file),
            reports={"setup": setup_status},
            tcl_path=str(setup_tcl_path)
        )

    # Phase 2: Execute Compile
    compile_success, compile_status, compile_tcl_path, reports = execute_compile_phase(req, log_file, result_dir)
    
    if not compile_success:
        return SynthResp(
            status=compile_status,
            log_path=str(log_file),
            reports={"setup": "ok", "compile": compile_status},
            tcl_path=str(compile_tcl_path)
        )

    # Both phases successful
    final_reports = {"setup": "Synthesis setup completed successfully"}
    final_reports.update(reports)
    
    return SynthResp(
        status="ok",
        log_path=str(log_file),
        reports=final_reports,
        tcl_path=str(compile_tcl_path)
    )

# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "synthesis"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("SYNTH_PORT", 13333)),
        help="listen port (env SYNTH_PORT overrides; default 13333)",
    )
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "synth_server:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
    ) 