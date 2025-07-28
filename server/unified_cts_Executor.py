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
        "/opt/cadence/innovus191/bin:"
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

def run_unified_route_save_from_tcl(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, force: bool = False):
    """Execute unified route+save (routing + final save) using a complete TCL file"""
    
    print(f"=== Unified Route+Save Executor ===")
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
        
        # Stream output in real-time (same setup as working route/save executors)
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
        
        # Stream output in real-time (same as working route/save executors)
        for line in process.stdout:
            print(line.rstrip())
        
        process.wait()
        
        print(f"\nInnovus execution completed with return code: {process.returncode}")
        
        if process.returncode != 0:
            raise RuntimeError(f"Innovus failed with return code {process.returncode}")
        
        # Check for completion markers
        done_file = workspace_dir / "_Done_"
        finished_file = workspace_dir / "_Finished_"
        if done_file.exists():
            print("✓ Unified route+save completion marker found (_Done_)")
        elif finished_file.exists():
            print("✓ Unified route+save completion marker found (_Finished_)")
        else:
            print("⚠ Warning: Completion marker not found")
        
        # Check for route output files (from 7_route.tcl)
        print("\n=== Route Stage Output Files ===")
        route_files = [
            "pnr_save/global_route.enc",
            "pnr_save/detail_route.enc", 
            "pnr_save/route_opt.enc",
            "pnr_out/route.def",
            "pnr_out/RC.spef.gz",
            "pnr_reports/route_summary.rpt",
            "pnr_reports/congestion.rpt",
            "pnr_reports/postRoute_drc_max1M.rpt",
            "pnr_reports/postOpt_drc_max1M.rpt",
        ]
        
        for route_file in route_files:
            file_path = workspace_dir / route_file
            if file_path.exists():
                print(f"  ✓ {route_file} ({file_path.stat().st_size} bytes)")
            else:
                print(f"  ✗ {route_file} (missing)")
        
        # Check for save output files (from 8_save_design.tcl)
        print("\n=== Save Stage Output Files ===")
        save_patterns = [
            "*_pnr.lef",
            "*_lib.lef", 
            "*_pnr.v",
            "*_pnr.gds.gz"
        ]
        
        save_files_found = []
        out_dir = workspace_dir / "pnr_out"
        for pattern in save_patterns:
            matches = list(out_dir.glob(pattern))
            if matches:
                for match in matches:
                    save_files_found.append(match.name)
                    print(f"  ✓ {match.name} ({match.stat().st_size} bytes)")
            else:
                print(f"  ✗ {pattern} (missing)")
        
        # Check for GDS file specifically (use glob pattern to find *_pnr.gds.gz)
        gds_files = list((workspace_dir / "pnr_out").glob("*_pnr.gds.gz"))
        if gds_files:
            print(f"✓ GDS file found: {gds_files[0].name}")
        else:
            print(f"⚠ Warning: GDS file (*_pnr.gds.gz) not found in pnr_out/")
        
        # List all files in output directories for debugging
        print("\n=== Generated Files Summary ===")
        for output_dir in ["pnr_out", "pnr_reports", "pnr_save"]:
            dir_path = workspace_dir / output_dir
            if dir_path.exists():
                print(f"{output_dir.upper()} directory:")
                for file_path in sorted(dir_path.iterdir()):
                    if file_path.is_file():
                        print(f"  📄 {file_path.name} ({file_path.stat().st_size} bytes)")
                    else:
                        print(f"  📁 {file_path.name}/")
        
        # Check for key artifacts from both stages
        key_files = [
            workspace_dir / "pnr_save" / "route_opt.enc",
            workspace_dir / "pnr_out" / "route.def",
            workspace_dir / "pnr_out" / "RC.spef.gz"
        ]
        
        # Add save artifacts to key files check
        if gds_files:
            key_files.append(gds_files[0])
        if save_files_found:
            # Find verilog file
            verilog_files = list((workspace_dir / "pnr_out").glob("*_pnr.v"))
            if verilog_files:
                key_files.append(verilog_files[0])
        
        missing_files = [f for f in key_files if not f.exists()]
        if missing_files:
            print(f"\n⚠ Warning: Some output files missing: {[str(f.name) for f in missing_files]}")
        else:
            print(f"\n✓ All key artifacts found")
        
        success = (done_file.exists() or finished_file.exists()) and bool(gds_files) and bool(save_files_found)
        if success:
            print("Unified Route+Save Completed Successfully")
        else:
            print("Unified Route+Save may not have completed successfully")
        
        return success
        
    except Exception as e:
        print(f"Unified route+save execution failed: {e}")
        raise
    finally:
        # Restore original working directory
        os.chdir(original_cwd)

def main():
    parser = argparse.ArgumentParser(description="Unified Route+Save Executor (Routing + Final Save)")
    parser.add_argument("-design", required=True, help="Design name")
    parser.add_argument("-technode", required=True, help="Technology node")
    parser.add_argument("-tcl", required=True, help="Complete TCL file path")
    parser.add_argument("-workspace", required=True, help="Workspace directory")
    parser.add_argument("-force", action="store_true", help="Force overwrite existing results")
    
    args = parser.parse_args()
    
    tcl_file = pathlib.Path(args.tcl)
    workspace_dir = pathlib.Path(args.workspace)
    
    print(f"=== Unified Route+Save Executor Started ===")
    print(f"Design: {args.design}")
    print(f"Technology: {args.technode}")
    print(f"TCL File: {tcl_file}")
    print(f"Workspace: {workspace_dir}")
    print(f"Force: {args.force}")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        success = run_unified_route_save_from_tcl(tcl_file, workspace_dir, args.force)
        if success:
            print(f"\nUnified Route+Save Executor completed successfully")
            print(f"=== Unified Route+Save Executor completed with return code: 0 ===")
            return 0
        else:
            print(f"\nUnified Route+Save Executor completed with warnings")
            print(f"=== Unified Route+Save Executor completed with return code: 0 ===")
            return 0  # Still return 0 for now, let server decide based on file checks
        
    except Exception as e:
        print(f"\nUnified Route+Save Executor failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 
