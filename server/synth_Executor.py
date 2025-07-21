#!/usr/bin/env python3

import argparse
import logging
import os
import pathlib
import shutil
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
    parser = argparse.ArgumentParser(description="Unified Synthesis Executor")
    parser.add_argument("-mode", required=True, choices=["setup", "compile", "synthesis"], help="Execution mode")
    parser.add_argument("-design", required=True, help="Design name")
    parser.add_argument("-technode", required=True, help="Technology node")
    parser.add_argument("-tcl", required=True, help="Path to TCL file")
    parser.add_argument("-version_idx", type=int, required=True, help="Synthesis version index")
    parser.add_argument("-synthesis_dir", help="Path to synthesis directory (for compile mode)")
    parser.add_argument("-force", action="store_true", help="Force overwrite existing results")
    return parser.parse_args()

def read_synthesis_config(version_idx: int):
    """Read synthesis configuration from CSV"""
    config_path = ROOT / "config" / "synthesis.csv"
    config_pd = pd.read_csv(config_path, index_col='version')
    
    syn_version = config_pd.index[version_idx]
    config_row = config_pd.iloc[version_idx]
    
    return syn_version, config_row

def parse_top_from_config(config_path: pathlib.Path) -> str:
    """Parse TOP_NAME from config.tcl"""
    if not config_path.exists():
        return None
    content = config_path.read_text()
    m = re.search(r'set\s+TOP_NAME\s+"([^"]+)"', content)
    if m:
        return m.group(1)
    return None

def safe_unlink(file_path: pathlib.Path):
    """Safely remove a file if it exists"""
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Removed existing file: {file_path}")
    except Exception as e:
        logger.warning(f"Could not remove file {file_path}: {e}")

# ============================================================================
# Setup Mode Functions
# ============================================================================

def create_synthesis_directories(design: str, tech: str, syn_version: str, force: bool = False):
    """Create synthesis directory structure"""
    design_dir = ROOT / "designs" / design
    synthesis_dir = design_dir / tech / "synthesis" / syn_version
    
    if synthesis_dir.exists() and force:
        logger.info(f"Removing existing synthesis directory: {synthesis_dir}")
        shutil.rmtree(synthesis_dir)
    
    # Create directory structure
    synthesis_dir.mkdir(parents=True, exist_ok=True)
    (synthesis_dir / "results").mkdir(exist_ok=True)
    (synthesis_dir / "reports").mkdir(exist_ok=True)
    (synthesis_dir / "logs").mkdir(exist_ok=True)
    (synthesis_dir / "data").mkdir(exist_ok=True)
    (synthesis_dir / "WORK").mkdir(exist_ok=True)
    
    logger.info(f"Created synthesis directory structure: {synthesis_dir}")
    
    # Copy design configuration
    design_config = design_dir / "config.tcl"
    target_config = synthesis_dir / "config.tcl"
    
    if design_config.exists():
        shutil.copy2(design_config, target_config)
        logger.info(f"Copied design config to {target_config}")
    
    # Copy tech configuration
    tech_config = ROOT / "scripts" / tech / "tech.tcl"
    target_tech = synthesis_dir / "tech.tcl"
    
    if tech_config.exists():
        shutil.copy2(tech_config, target_tech)
        logger.info(f"Copied tech config to {target_tech}")
    
    return synthesis_dir

def run_setup_tcl(tcl_path: pathlib.Path, work_dir: pathlib.Path):
    """Execute setup TCL script"""
    logger.info(f"Executing setup TCL script: {tcl_path}")
    logger.info(f"Working directory: {work_dir}")
    
    # Just run the TCL to create directories and set environment
    cmd = ["tclsh", str(tcl_path)]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for setup
        )
        
        if result.returncode != 0:
            logger.error(f"Setup TCL script failed with return code {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return False
        
        logger.info("Setup TCL script executed successfully")
        logger.info(f"Output: {result.stdout}")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("Setup TCL script execution timed out")
        return False
    except Exception as e:
        logger.error(f"Error executing setup TCL script: {e}")
        return False

def verify_setup(synthesis_dir: pathlib.Path):
    """Verify synthesis setup completion"""
    required_dirs = ["results", "reports", "logs", "data", "WORK"]
    
    for dir_name in required_dirs:
        dir_path = synthesis_dir / dir_name
        if not dir_path.exists():
            logger.error(f"Required directory not found: {dir_path}")
            return False
    
    # Check for completion marker
    done_file = synthesis_dir / "_Finished_"
    if not done_file.exists():
        logger.error("Setup completion marker not found")
        return False
    
    logger.info("Synthesis setup verification passed")
    return True

# ============================================================================
# Compile Mode Functions
# ============================================================================

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

# ============================================================================
# Main Execution Functions
# ============================================================================

def execute_setup_mode(args):
    """Execute synthesis setup mode"""
    logger.info(f"Starting synthesis setup for design: {args.design}")
    
    try:
        # Read synthesis configuration
        syn_version, config_row = read_synthesis_config(args.version_idx)
        logger.info(f"Using synthesis version: {syn_version}")
        
        # Create synthesis directories
        synthesis_dir = create_synthesis_directories(
            args.design, args.technode, syn_version, args.force
        )
        
        # Execute setup TCL script
        if not run_setup_tcl(pathlib.Path(args.tcl), synthesis_dir):
            logger.error("Failed to execute setup TCL script")
            return False
        
        # Verify setup
        if not verify_setup(synthesis_dir):
            logger.error("Setup verification failed")
            return False
        
        logger.info("Synthesis setup completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Synthesis setup failed: {e}")
        return False

def execute_compile_mode(args):
    """Execute synthesis compile mode"""
    logger.info(f"Starting synthesis compilation for design: {args.design}")
    
    synthesis_dir = pathlib.Path(args.synthesis_dir)
    
    try:
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
            return False
        
        # Verify outputs
        if not verify_synthesis_outputs(synthesis_dir, args.design):
            logger.error("Synthesis output verification failed")
            return False
        
        logger.info("Synthesis compilation completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Synthesis compilation failed: {e}")
        return False

def execute_synthesis_mode(args):
    """Execute unified synthesis mode (like floorplan)"""
    logger.info(f"Starting unified synthesis for design: {args.design}")
    
    synthesis_dir = pathlib.Path(args.synthesis_dir)
    
    try:
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
        
        # Execute Design Compiler with the unified TCL
        if not run_design_compiler(pathlib.Path(args.tcl), synthesis_dir):
            logger.error("Failed to execute Design Compiler for unified synthesis")
            return False
        
        # Verify outputs
        if not verify_synthesis_outputs(synthesis_dir, args.design):
            logger.error("Unified synthesis output verification failed")
            return False
        
        logger.info("Unified synthesis completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Unified synthesis failed: {e}")
        return False

def main():
    args = parse_args()
    
    logger.info(f"Unified Synthesis Executor - Mode: {args.mode}")
    logger.info(f"Technology: {args.technode}")
    logger.info(f"TCL script: {args.tcl}")
    logger.info(f"Version index: {args.version_idx}")
    
    # Setup EDA environment
    setup_eda_environment()
    
    # Execute based on mode
    success = False
    if args.mode == "setup":
        success = execute_setup_mode(args)
    elif args.mode == "compile":
        if not args.synthesis_dir:
            logger.error("Synthesis directory is required for compile mode")
            sys.exit(1)
        success = execute_compile_mode(args)
    elif args.mode == "synthesis":
        if not args.synthesis_dir:
            logger.error("Synthesis directory is required for synthesis mode")
            sys.exit(1)
        success = execute_synthesis_mode(args)
    else:
        logger.error(f"Unknown mode: {args.mode}")
        sys.exit(1)
    
    if not success:
        sys.exit(1)
    
    logger.info(f"Synthesis {args.mode} completed successfully")

if __name__ == "__main__":
    main() 