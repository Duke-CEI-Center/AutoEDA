#!/usr/bin/env python3

import argparse
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import pandas as pd

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
    parser = argparse.ArgumentParser(description="Synthesis Setup Executor")
    parser.add_argument("-design", required=True, help="Design name")
    parser.add_argument("-technode", required=True, help="Technology node")
    parser.add_argument("-tcl", required=True, help="Path to setup TCL file")
    parser.add_argument("-version_idx", type=int, required=True, help="Synthesis version index")
    parser.add_argument("-force", action="store_true", help="Force overwrite existing results")
    return parser.parse_args()

def read_synthesis_config(version_idx: int):
    """Read synthesis configuration from CSV"""
    config_path = ROOT / "config" / "synthesis.csv"
    config_pd = pd.read_csv(config_path, index_col='version')
    
    syn_version = config_pd.index[version_idx]
    config_row = config_pd.iloc[version_idx]
    
    return syn_version, config_row

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

def run_tcl_script(tcl_path: pathlib.Path, work_dir: pathlib.Path):
    """Execute TCL script"""
    logger.info(f"Executing TCL script: {tcl_path}")
    logger.info(f"Working directory: {work_dir}")
    
    # Just run the TCL to create directories and set environment
    # The actual synthesis compilation will be handled by the compile server
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
            logger.error(f"TCL script failed with return code {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return False
        
        logger.info("TCL script executed successfully")
        logger.info(f"Output: {result.stdout}")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("TCL script execution timed out")
        return False
    except Exception as e:
        logger.error(f"Error executing TCL script: {e}")
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

def main():
    args = parse_args()
    
    logger.info(f"Starting synthesis setup for design: {args.design}")
    logger.info(f"Technology: {args.technode}")
    logger.info(f"TCL script: {args.tcl}")
    logger.info(f"Version index: {args.version_idx}")
    
    try:
        # Setup EDA environment
        setup_eda_environment()
        
        # Read synthesis configuration
        syn_version, config_row = read_synthesis_config(args.version_idx)
        logger.info(f"Using synthesis version: {syn_version}")
        
        # Create synthesis directories
        synthesis_dir = create_synthesis_directories(
            args.design, args.technode, syn_version, args.force
        )
        
        # Execute TCL script
        if not run_tcl_script(pathlib.Path(args.tcl), synthesis_dir):
            logger.error("Failed to execute setup TCL script")
            sys.exit(1)
        
        # Verify setup
        if not verify_setup(synthesis_dir):
            logger.error("Setup verification failed")
            sys.exit(1)
        
        logger.info("Synthesis setup completed successfully")
        
    except Exception as e:
        logger.error(f"Synthesis setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 