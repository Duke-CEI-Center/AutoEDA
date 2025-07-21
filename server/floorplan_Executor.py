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
    
    # Build Innovus command
    innovus_cmd_parts = [
        "innovus",
        "-no_gui",
        "-batch"
    ]
    
    # Add restore command if restore_enc is provided
    if restore_enc and restore_enc != "":
        restore_abs = pathlib.Path(restore_enc).resolve()
        if restore_abs.exists():
            exec_cmd = f'restoreDesign "{restore_abs}" {top_module}; source "{tcl_path}"'
            innovus_cmd_parts.extend(["-execute", exec_cmd])
        else:
            logging.warning(f"Restore file not found: {restore_enc}, proceeding without restore")
            innovus_cmd_parts.extend(["-files", str(tcl_path)])
    else:
        innovus_cmd_parts.extend(["-files", str(tcl_path)])
    
    # Copy required files to implementation directory
    copy_required_files(impl_dir)
    
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

def copy_required_files(impl_dir: pathlib.Path):
    """Copy required files (config.tcl, tech.tcl) to implementation directory if they don't exist"""
    
    # These files should already be copied by the server, but let's verify
    required_files = ["config.tcl", "tech.tcl"]
    
    for file_name in required_files:
        file_path = impl_dir / file_name
        if not file_path.exists():
            logging.warning(f"Required file {file_name} not found in {impl_dir}")

def verify_outputs(impl_dir: pathlib.Path):
    """Verify that required output files are generated"""
    
    required_outputs = [
        "pnr_save/floorplan.enc.dat",
        "pnr_reports/floorplan_summary.rpt"
    ]
    
    missing_outputs = []
    for output in required_outputs:
        output_path = impl_dir / output
        if not output_path.exists():
            # Check for gzipped version
            gz_path = pathlib.Path(str(output_path) + ".gz")
            if not gz_path.exists():
                missing_outputs.append(output)
    
    if missing_outputs:
        logging.warning(f"Missing expected outputs: {missing_outputs}")
        return False
    else:
        logging.info("All expected outputs generated successfully")
        return True

def main():
    parser = argparse.ArgumentParser(description="Floorplan Executor - Execute floorplan TCL scripts")
    parser.add_argument("-design", required=True, help="Design name")
    parser.add_argument("-technode", required=True, help="Technology node")
    parser.add_argument("-tcl", required=True, help="Path to TCL script")
    parser.add_argument("-impl_dir", required=True, help="Implementation directory")
    parser.add_argument("-restore_enc", default="", help="Path to restore .enc file")
    parser.add_argument("-top_module", required=True, help="Top module name")
    parser.add_argument("-force", action="store_true", help="Force overwrite existing results")
    
    args = parser.parse_args()
    
    setup_logging()
    
    # Convert string paths to Path objects
    tcl_path = pathlib.Path(args.tcl)
    impl_dir = pathlib.Path(args.impl_dir)
    
    # Validate inputs
    if not tcl_path.exists():
        logging.error(f"TCL script not found: {tcl_path}")
        sys.exit(1)
    
    if not impl_dir.exists():
        logging.error(f"Implementation directory not found: {impl_dir}")
        sys.exit(1)
    
    logging.info(f"Starting floorplan execution for design: {args.design}")
    logging.info(f"Technology: {args.technode}")
    logging.info(f"TCL script: {tcl_path}")
    logging.info(f"Implementation directory: {impl_dir}")
    logging.info(f"Top module: {args.top_module}")
    
    if args.restore_enc:
        logging.info(f"Restore file: {args.restore_enc}")
    
    # Clean existing results if force is specified
    if args.force:
        outputs_to_clean = [
            impl_dir / "pnr_save" / "floorplan.enc.dat",
            impl_dir / "pnr_reports" / "floorplan_summary.rpt",
            impl_dir / "pnr_reports" / "floorplan_summary.rpt.gz"
        ]
        for output in outputs_to_clean:
            if output.exists():
                output.unlink()
                logging.info(f"Cleaned existing output: {output}")
    
    # Execute floorplan
    success = run_innovus(tcl_path, impl_dir, args.restore_enc, args.top_module)
    
    if not success:
        logging.error("Floorplan execution failed")
        sys.exit(1)
    
    # Verify outputs
    if not verify_outputs(impl_dir):
        logging.error("Output verification failed")
        sys.exit(1)
    
    logging.info("Floorplan execution completed successfully")
    sys.exit(0)

if __name__ == "__main__":
    main() 