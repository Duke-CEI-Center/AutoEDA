#!/usr/bin/env python3
"""
Usage: python3 synth_Executor.py -mode synthesis -design <design_name> -technode <technology_node> -tcl <tcl_file> -workspace <workspace_dir>
"""

import argparse
from pathlib import Path
import time
import subprocess
import sys
import os

# Load environment variables from .env file at project root
from dotenv import load_dotenv

# Add project root to Python path
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT / ".env")
# sys.path.append(str(ROOT))

def setup_eda_environment():
    """Setup EDA tools environment from .env file"""
    
    # Read EDA paths from environment variables
    synopsys_path = os.getenv("EDA_SYNOPSYS_PATH", "/opt/synopsys/syn/V-2023.12-SP2/bin")
    cadence_path = os.getenv("EDA_CADENCE_PATH", "/tools/cadence/innovus191/bin")
    
    # Build list of EDA paths, filtering out empty ones
    eda_paths = [synopsys_path, cadence_path]
    
    current_path = os.environ.get("PATH", "")
    new_path = ":".join(eda_paths) + ":" + current_path
    os.environ["PATH"] = new_path
    
    print(f"EDA environment setup completed")
    print(f"Added to PATH: {':'.join(eda_paths)}")
 
def run_synthesis_from_tcl(tcl_file: Path, workspace_dir: Path):
    """Execute synthesis using a complete TCL file"""
    
    print(f"=== Synthesis Executor ===")
    print(f"TCL File: {tcl_file}")
    print(f"Workspace: {workspace_dir}")
    
    if not tcl_file.exists():
        raise FileNotFoundError(f"TCL file not found: {tcl_file}")
    
    if not workspace_dir.exists():
        raise FileNotFoundError(f"Workspace directory not found: {workspace_dir}")
    
    # Setup EDA environment
    setup_eda_environment()
    
    # Build dc_shell command to execute the TCL file
    cmd = f'dc_shell -no_home_init -output_log_file console.log -x "source -e -v {tcl_file}"'
    
    print(f"Executing command: {cmd}")
    print(f"Working directory: {workspace_dir}")
    
    # Execute dc_shell in the workspace directory
    start_time = time.time()
    
    try:
        # Use tcsh for license environment compatibility
        process = subprocess.Popen(
            cmd,
            cwd=str(workspace_dir),
            shell=True,
            executable="/bin/tcsh",
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        
        # Stream output in real-time
        for line in process.stdout:
            print(line.rstrip())
        
        process.wait()
        
        if process.returncode != 0:
            raise RuntimeError(f"dc_shell failed with return code {process.returncode}")
        
        # Check for completion marker
        done_file = workspace_dir / "_Finished_"
        if not done_file.exists():
            raise RuntimeError("Synthesis did not complete successfully (_Finished_ file not found)")
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        print(f"\n=== Synthesis Completed Successfully ===")
        print(f"Elapsed time: {elapsed:.1f} seconds")
        
        # Report generated files
        reports_dir = workspace_dir / "reports"
        results_dir = workspace_dir / "results"
        
        if reports_dir.exists():
            report_files = list(reports_dir.glob("*.rpt"))
            print(f"Generated {len(report_files)} report files:")
            for rpt in sorted(report_files):
                print(f"  - {rpt.name}")
        
        if results_dir.exists():
            result_files = list(results_dir.glob("*"))
            print(f"Generated {len(result_files)} result files:")
            for res in sorted(result_files):
                print(f"  - {res.name}")
        
        return True
        
    except Exception as e:
        print(f"Error during synthesis: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="MCP EDA Synthesis Executor")
    parser.add_argument("-mode", type=str, required=True, 
                       help="Execution mode (synthesis, placement, routing)")
    parser.add_argument("-design", type=str, required=True,
                       help="Design name")
    parser.add_argument("-technode", type=str, required=True,
                       help="Technology node")
    parser.add_argument("-tcl", type=str, required=True,
                       help="Complete TCL file to execute")
    parser.add_argument("-workspace", type=str, required=True,
                       help="Workspace directory for execution")
    
    args = parser.parse_args()
    
    # Convert paths
    tcl_file = Path(args.tcl)
    workspace_dir = Path(args.workspace)
    
    print(f"MCP EDA Executor starting...")
    print(f"Mode: {args.mode}")
    print(f"Design: {args.design}")
    print(f"Technology: {args.technode}")
    
    success = False
    
    if args.mode == "synthesis":
        success = run_synthesis_from_tcl(tcl_file, workspace_dir)
    else:
        print(f"Error: Unsupported mode '{args.mode}'")
        print("Supported modes: synthesis")
        return 1
    
    if success:
        print("Executor completed successfully")
        return 0
    else:
        print("Executor failed")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 