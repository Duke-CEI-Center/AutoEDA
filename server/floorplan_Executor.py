#!/usr/bin/env python3

import argparse
import pathlib
import time
import subprocess
import sys
import os

# Add project root to Python path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

def setup_eda_environment():
    """Setup EDA tools environment - mirror original working setup"""
    # Use the exact same PATH setup as the original working floorplan server
    eda_path_setup = (
        "/opt/cadence/innovus221/tools/bin:"
        "/opt/cadence/genus172/bin:"
        + os.environ.get("PATH", "")
    )
    os.environ["PATH"] = eda_path_setup
    
    print(f"EDA environment setup completed")
    print(f"PATH = {os.environ.get('PATH', '')[:200]}...")
    
    # Check if innovus is accessible
    try:
        result = subprocess.run(["which", "innovus"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Found innovus at: {result.stdout.strip()}")
        else:
            print("Warning: innovus not found in PATH")
    except Exception as e:
        print(f"Error checking innovus: {e}")

def run_floorplan_from_tcl(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, force: bool = False):
    """Execute floorplan using a complete TCL file"""
    
    print(f"=== Floorplan Executor ===")
    print(f"TCL File: {tcl_file}")
    print(f"Workspace: {workspace_dir}")
    print(f"Force: {force}")
    
    if not tcl_file.exists():
        raise FileNotFoundError(f"TCL file not found: {tcl_file}")
    
    if not workspace_dir.exists():
        raise FileNotFoundError(f"Workspace directory not found: {workspace_dir}")
    
    # Setup EDA environment
    setup_eda_environment()
    
    # Use the original style command - this matches the working original code
    files_list = [str(tcl_file)]
    files_arg = " ".join(files_list)
    
    # Build innovus command like the original working version
    innovus_cmd = (
        f'innovus -no_gui -batch '
        f'-files "{files_arg}"'
    )
    
    print(f"Executing command: {innovus_cmd}")
    print(f"Working directory: {workspace_dir}")
    
    # Execute innovus in the workspace directory
    start_time = time.time()
    
    try:
        # Use tcsh for license compatibility (like synthesis)
        process = subprocess.Popen(
            innovus_cmd,
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
            raise RuntimeError(f"innovus failed with return code {process.returncode}")
        
        # Check for completion marker
        done_file = workspace_dir / "_Done_"
        if not done_file.exists():
            raise RuntimeError("Floorplan did not complete successfully (_Done_ file not found)")
        
        # Check for expected output file
        enc_path = workspace_dir / "pnr_save" / "floorplan.enc.dat"
        if not enc_path.exists():
            raise RuntimeError("Floorplan did not produce floorplan.enc.dat")
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        print(f"\n=== Floorplan Completed Successfully ===")
        print(f"Elapsed time: {elapsed:.1f} seconds")
        
        # Report generated files
        pnr_reports_dir = workspace_dir / "pnr_reports"
        pnr_out_dir = workspace_dir / "pnr_out"
        pnr_save_dir = workspace_dir / "pnr_save"
        
        if pnr_reports_dir.exists():
            report_files = list(pnr_reports_dir.glob("*"))
            print(f"Generated {len(report_files)} report files:")
            for rpt in sorted(report_files):
                print(f"  - {rpt.name}")
        
        if pnr_out_dir.exists():
            output_files = list(pnr_out_dir.glob("*"))
            print(f"Generated {len(output_files)} output files:")
            for out in sorted(output_files):
                print(f"  - {out.name}")
        
        if pnr_save_dir.exists():
            save_files = list(pnr_save_dir.glob("*"))
            print(f"Generated {len(save_files)} save files:")
            for save in sorted(save_files):
                print(f"  - {save.name}")
        
        return True
        
    except Exception as e:
        print(f"Error during floorplan: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="MCP EDA Floorplan Executor")
    parser.add_argument("-mode", type=str, required=True, 
                       help="Execution mode (floorplan, placement, routing)")
    parser.add_argument("-design", type=str, required=True,
                       help="Design name")
    parser.add_argument("-technode", type=str, required=True,
                       help="Technology node")
    parser.add_argument("-tcl", type=str, required=True,
                       help="Complete TCL file to execute")
    parser.add_argument("-workspace", type=str, required=True,
                       help="Workspace directory for execution")
    parser.add_argument("-force", action="store_true",
                       help="Force overwrite existing results")
    
    args = parser.parse_args()
    
    # Convert paths
    tcl_file = pathlib.Path(args.tcl)
    workspace_dir = pathlib.Path(args.workspace)
    
    print(f"MCP EDA Floorplan Executor starting...")
    print(f"Mode: {args.mode}")
    print(f"Design: {args.design}")
    print(f"Technology: {args.technode}")
    
    success = False
    
    if args.mode == "floorplan":
        success = run_floorplan_from_tcl(tcl_file, workspace_dir, args.force)
    else:
        print(f"Error: Unsupported mode '{args.mode}'")
        print("Supported modes: floorplan")
        return 1
    
    if success:
        print("Executor completed successfully")
        return 0
    else:
        print("Executor failed")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 