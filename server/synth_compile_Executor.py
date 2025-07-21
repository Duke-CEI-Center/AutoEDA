#!/usr/bin/env python3

import argparse
import logging
import os
import pathlib
import subprocess
import sys
import pandas as pd
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get project root
ROOT = pathlib.Path(__file__).resolve().parent.parent

def setup_eda_environment():
    """Setup EDA tool paths"""
    # Add EDA tool paths to environment
    current_path = os.environ.get("PATH", "")
    eda_paths = [
        "/tools/synopsys/syn/P-2019.03-SP5-5/bin",
        "/tools/cadence/innovus191/bin",
    ]
    
    for eda_path in eda_paths:
        if pathlib.Path(eda_path).exists() and eda_path not in current_path:
            current_path = f"{eda_path}:{current_path}"
    
    os.environ["PATH"] = current_path
    logger.info(f"Updated PATH: {current_path}")

def parse_args():
    parser = argparse.ArgumentParser(description="Synthesis Compile Executor")
    parser.add_argument("-design", required=True, help="Design name")
    parser.add_argument("-technode", required=True, help="Technology node")
    parser.add_argument("-tcl", required=True, help="Path to compile TCL file")
    parser.add_argument("-synthesis_dir", required=True, help="Path to synthesis directory")
    parser.add_argument("-version_idx", type=int, required=True, help="Synthesis version index")
    parser.add_argument("-force", action="store_true", help="Force overwrite existing results")
    return parser.parse_args()

def run_design_compiler(tcl_path: pathlib.Path, synthesis_dir: pathlib.Path):
    """Execute Design Compiler with the provided TCL script"""
    logger.info(f"Running Design Compiler with TCL: {tcl_path}")
    logger.info(f"Working directory: {synthesis_dir}")
    
    # Design Compiler command
    cmd = [
        "dc_shell", 
        "-no_home_init",
        "-output_log_file", "console.log",
        "-x", f"source {tcl_path}"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(synthesis_dir),
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout for synthesis
        )
        
        if result.returncode != 0:
            logger.error(f"Design Compiler failed with return code {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return False
        
        logger.info("Design Compiler executed successfully")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("Design Compiler execution timed out")
        return False
    except Exception as e:
        logger.error(f"Error executing Design Compiler: {e}")
        return False

def parse_top_from_config(config_path: pathlib.Path) -> str:
    """Parse TOP_NAME from config.tcl"""
    if not config_path.exists():
        return None
    content = config_path.read_text()
    m = re.search(r'set\s+TOP_NAME\s+"([^"]+)"', content)
    if m:
        return m.group(1)
    return None

def verify_synthesis_outputs(synthesis_dir: pathlib.Path, design: str):
    """Verify synthesis outputs using TOP_NAME from config.tcl"""
    results_dir = synthesis_dir / "results"
    reports_dir = synthesis_dir / "reports"
    # Parse TOP_NAME from config.tcl
    config_path = synthesis_dir.parent.parent.parent / "config.tcl"
    top_name = parse_top_from_config(config_path) or design
    # Check required output files
    required_files = [
        results_dir / f"{top_name}.v",
        results_dir / f"{top_name}.sdc",
        results_dir / f"{top_name}.ddc",
        reports_dir / "qor.rpt",
        reports_dir / "timing.rpt",
        reports_dir / "area.rpt",
        reports_dir / "power.rpt"
    ]
    missing_files = []
    for file_path in required_files:
        if not file_path.exists():
            missing_files.append(str(file_path))
            logger.warning(f"Missing output file: {file_path}")
    # Check for completion marker
    done_file = synthesis_dir / "_Finished_"
    if not done_file.exists():
        logger.error("Synthesis completion marker not found")
        return False
    if missing_files:
        logger.warning(f"Some output files are missing: {missing_files}")
    logger.info("Synthesis output verification completed")
    return True

def safe_unlink(file_path: pathlib.Path):
    """Safely remove a file if it exists"""
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Removed existing file: {file_path}")
    except Exception as e:
        logger.warning(f"Could not remove file {file_path}: {e}")

def main():
    args = parse_args()
    
    logger.info(f"Starting synthesis compilation for design: {args.design}")
    logger.info(f"Technology: {args.technode}")
    logger.info(f"TCL script: {args.tcl}")
    logger.info(f"Synthesis directory: {args.synthesis_dir}")
    logger.info(f"Version index: {args.version_idx}")
    
    synthesis_dir = pathlib.Path(args.synthesis_dir)
    
    try:
        # Setup EDA environment
        setup_eda_environment()
        
        # Clean previous results if force is enabled
        if args.force:
            results_dir = synthesis_dir / "results"
            reports_dir = synthesis_dir / "reports"
            
            if results_dir.exists():
                for file in results_dir.iterdir():
                    safe_unlink(file)
            
            if reports_dir.exists():
                for file in reports_dir.iterdir():
                    safe_unlink(file)
        
        # Ensure necessary directories exist
        (synthesis_dir / "results").mkdir(exist_ok=True)
        (synthesis_dir / "reports").mkdir(exist_ok=True)
        (synthesis_dir / "logs").mkdir(exist_ok=True)
        (synthesis_dir / "data").mkdir(exist_ok=True)
        (synthesis_dir / "WORK").mkdir(exist_ok=True)
        
        # Execute Design Compiler
        if not run_design_compiler(pathlib.Path(args.tcl), synthesis_dir):
            logger.error("Failed to execute Design Compiler")
            sys.exit(1)
        
        # Verify outputs
        if not verify_synthesis_outputs(synthesis_dir, args.design):
            logger.error("Synthesis output verification failed")
            sys.exit(1)
        
        logger.info("Synthesis compilation completed successfully")
        
    except Exception as e:
        logger.error(f"Synthesis compilation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 