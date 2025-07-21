#!/usr/bin/env python3

import argparse
import pathlib
import subprocess
import sys
import os
import logging

# Set up EDA tool paths
os.environ["PATH"] = (
    "/opt/cadence/innovus221/tools/bin:"
    "/opt/cadence/genus172/bin:"
    + os.environ.get("PATH", "")
)

def setup_logging():
    """Setup logging for the executor"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def run_innovus(tcl_path: pathlib.Path, impl_dir: pathlib.Path, restore_enc: str = "", top_module: str = ""):
    """Execute Innovus with the generated TCL script"""
    
    # Ensure directories exist
    (impl_dir / "pnr_save").mkdir(exist_ok=True)
    (impl_dir / "pnr_reports").mkdir(exist_ok=True)
    (impl_dir / "pnr_out").mkdir(exist_ok=True)
    (impl_dir / "pnr_logs").mkdir(exist_ok=True)
    
    # Build Innovus command - for placement, we use the TCL script directly
    # as it contains the restoreDesign command
    innovus_cmd_parts = [
        "innovus",
        "-no_gui",
        "-batch",
        "-files", str(tcl_path)
    ]
    
    logging.info(f"Running Innovus command: {' '.join(innovus_cmd_parts)}")
    logging.info(f"Working directory: {impl_dir}")
    logging.info(f"TCL script: {tcl_path}")
    
    # Execute Innovus
    try:
        result = subprocess.run(
            innovus_cmd_parts,
            cwd=str(impl_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        # Print Innovus output
        print(result.stdout)
        
        if result.returncode != 0:
            logging.error(f"Innovus execution failed with return code: {result.returncode}")
            return False
        else:
            logging.info("Innovus execution completed successfully")
            return True
            
    except subprocess.TimeoutExpired:
        logging.error("Innovus execution timed out")
        return False
    except Exception as e:
        logging.error(f"Innovus execution failed with exception: {e}")
        return False

def verify_outputs(impl_dir: pathlib.Path):
    """Verify that required output files are generated"""
    
    required_outputs = [
        "pnr_save/placement.enc",
        "pnr_reports/check_place.out"
    ]
    
    missing_outputs = []
    for output in required_outputs:
        output_path = impl_dir / output
        if not output_path.exists():
            missing_outputs.append(output)
    
    if missing_outputs:
        logging.warning(f"Missing expected outputs: {missing_outputs}")
        return False
    else:
        logging.info("All expected outputs generated successfully")
        return True

def main():
    parser = argparse.ArgumentParser(description="Placement Executor - Execute placement TCL scripts")
    parser.add_argument("-design", required=True, help="Design name")
    parser.add_argument("-technode", required=True, help="Technology node")
    parser.add_argument("-tcl", required=True, help="Path to TCL script")
    parser.add_argument("-impl_dir", required=True, help="Implementation directory")
    parser.add_argument("-restore_enc", required=True, help="Path to restore .enc file")
    parser.add_argument("-top_module", required=True, help="Top module name")
    parser.add_argument("-force", action="store_true", help="Force overwrite existing results")
    
    args = parser.parse_args()
    
    setup_logging()
    
    # Convert string paths to Path objects
    tcl_path = pathlib.Path(args.tcl)
    impl_dir = pathlib.Path(args.impl_dir)
    restore_enc = pathlib.Path(args.restore_enc)
    
    # Validate inputs
    if not tcl_path.exists():
        logging.error(f"TCL script not found: {tcl_path}")
        sys.exit(1)
    
    if not impl_dir.exists():
        logging.error(f"Implementation directory not found: {impl_dir}")
        sys.exit(1)
        
    if not restore_enc.exists():
        logging.error(f"Restore file not found: {restore_enc}")
        sys.exit(1)
    
    logging.info(f"Starting placement execution for design: {args.design}")
    logging.info(f"Technology: {args.technode}")
    logging.info(f"TCL script: {tcl_path}")
    logging.info(f"Implementation directory: {impl_dir}")
    logging.info(f"Top module: {args.top_module}")
    logging.info(f"Restore file: {restore_enc}")
    
    # Clean existing results if force is specified
    if args.force:
        outputs_to_clean = [
            impl_dir / "pnr_save" / "placement.enc",
            impl_dir / "pnr_reports" / "check_place.out",
            impl_dir / "pnr_reports" / "placement_summary.rpt",
            impl_dir / "_Place_Finished_"
        ]
        for output in outputs_to_clean:
            if output.exists():
                output.unlink()
                logging.info(f"Cleaned existing output: {output}")
    
    # Execute placement
    success = run_innovus(tcl_path, impl_dir, args.restore_enc, args.top_module)
    
    if not success:
        logging.error("Placement execution failed")
        sys.exit(1)
    
    # Verify outputs
    if not verify_outputs(impl_dir):
        logging.error("Output verification failed")
        sys.exit(1)
    
    logging.info("Placement execution completed successfully")
    sys.exit(0)

if __name__ == "__main__":
    main() 