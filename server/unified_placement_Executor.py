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
    """Setup EDA tools environment for Cadence Innovus"""
    # Use the exact same PATH setup as the original working servers
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

def run_unified_placement_from_tcl(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, force: bool = False):
    """Execute unified placement (floorplan + powerplan + placement) using a complete TCL file"""
    
    print(f"=== Unified Placement Executor ===")
    print(f"TCL File: {tcl_file}")
    print(f"Workspace: {workspace_dir}")
    print(f"Force: {force}")
    
    if not tcl_file.exists():
        raise FileNotFoundError(f"TCL file not found: {tcl_file}")
    
    if not workspace_dir.exists():
        raise FileNotFoundError(f"Workspace directory not found: {workspace_dir}")
    
    # Create necessary subdirectories if they don't exist
    (workspace_dir / "pnr_save").mkdir(exist_ok=True)
    (workspace_dir / "pnr_out").mkdir(exist_ok=True)
    (workspace_dir / "pnr_reports").mkdir(exist_ok=True)
    
    # Setup EDA environment
    setup_eda_environment()
    
    # Change to workspace directory
    original_cwd = pathlib.Path.cwd()
    os.chdir(workspace_dir)
    
    try:
        # Execute innovus with the TCL file
        print(f"Starting Innovus execution...")
        
        # Build innovus command like the original working version
        innovus_cmd = f'innovus -no_gui -batch -files "{tcl_file}"'
        print(f"Command: {innovus_cmd}")
        
        # Use tcsh for license compatibility (similar to synthesis)
        env = os.environ.copy()
        
        # Stream output in real-time (same setup as working floorplan executor)
        process = subprocess.Popen(
            innovus_cmd,
            cwd=str(workspace_dir),
            shell=True,
            executable="/bin/tcsh",
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        
        print(f"Innovus process started with PID: {process.pid}")
        
        # Stream output in real-time (same as working floorplan executor)
        for line in process.stdout:
            print(line.rstrip())
        
        process.wait()
        
        print(f"\nInnovus execution completed with return code: {process.returncode}")
        
        if process.returncode != 0:
            raise RuntimeError(f"Innovus failed with return code {process.returncode}")
        
        # Check for completion marker
        done_file = workspace_dir / "_Done_"
        if done_file.exists():
            print("✓ Unified placement completion marker found")
        else:
            print("⚠ Warning: Completion marker not found")
        
        # Check for output files
        print("\n=== Generated Files ===")
        output_files = [
            "pnr_save/floorplan.enc",
            "pnr_save/powerplan.enc", 
            "pnr_save/placement.enc",
            "pnr_out/init.def",
            "pnr_out/place.def",
            "pnr_reports/floorplan_summary.rpt",
            "pnr_reports/check_place.out",
        ]
        
        for output_file in output_files:
            file_path = workspace_dir / output_file
            if file_path.exists():
                print(f"  ✓ {output_file} ({file_path.stat().st_size} bytes)")
            else:
                print(f"  ✗ {output_file} (missing)")
        
        # List all files in output directories for debugging
        for output_dir in ["pnr_out", "pnr_reports", "pnr_save"]:
            dir_path = workspace_dir / output_dir
            if dir_path.exists():
                print(f"\nContents of {output_dir}:")
                for file_path in sorted(dir_path.iterdir()):
                    if file_path.is_file():
                        print(f"{file_path.name} ({file_path.stat().st_size} bytes)")
        
        # Check for key artifacts
        key_files = [
            workspace_dir / "pnr_save" / "placement.enc",
            workspace_dir / "pnr_out" / "place.def"
        ]
        
        missing_files = [f for f in key_files if not f.exists()]
        if missing_files:
            print(f"\n⚠ Warning: Key output files missing: {[str(f) for f in missing_files]}")
        else:
            print(f"\n✓ All key artifacts found")
        
        print("Unified Placement Completed Successfully")
        
    except Exception as e:
        print(f"Unified placement execution failed: {e}")
        raise
    finally:
        # Restore original working directory
        os.chdir(original_cwd)

def main():
    parser = argparse.ArgumentParser(description="Unified Placement Executor (Floorplan + Powerplan + Placement)")
    parser.add_argument("-design", required=True, help="Design name")
    parser.add_argument("-technode", required=True, help="Technology node")
    parser.add_argument("-tcl", required=True, help="Complete TCL file path")
    parser.add_argument("-workspace", required=True, help="Workspace directory")
    parser.add_argument("-force", action="store_true", help="Force overwrite existing results")
    
    args = parser.parse_args()
    
    tcl_file = pathlib.Path(args.tcl)
    workspace_dir = pathlib.Path(args.workspace)
    
    print(f"=== Unified Placement Executor Started ===")
    print(f"Design: {args.design}")
    print(f"Technology: {args.technode}")
    print(f"TCL File: {tcl_file}")
    print(f"Workspace: {workspace_dir}")
    print(f"Force: {args.force}")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        run_unified_placement_from_tcl(tcl_file, workspace_dir, args.force)
        print(f"\n=== Unified Placement Executor completed with return code: 0 ===")
        return 0
        
    except Exception as e:
        print(f"\n Unified Placement Executor failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 