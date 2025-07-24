#!/usr/bin/env python3

import argparse
import pathlib
import subprocess
import os
import sys

def setup_eda_environment():
    """Add EDA tool paths to PATH environment variable"""
    eda_paths = [
        "/opt/cadence/innovus221/tools/bin",
        "/opt/cadence/genus172/bin", 
        "/opt/cadence/innovus191/bin"
    ]
    
    current_path = os.environ.get("PATH", "")
    new_path = ":".join(eda_paths + [current_path])
    os.environ["PATH"] = new_path
    
    print(f"✓ EDA environment setup completed")
    print(f"✓ PATH updated with: {', '.join(eda_paths)}")

def run_route_from_tcl(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, force: bool = False):
    """Execute route using the generated TCL file with Innovus"""
    
    # Setup EDA environment
    setup_eda_environment()
    
    print(f"=== Route Executor Started ===")
    print(f"TCL file: {tcl_file}")
    print(f"Workspace: {workspace_dir}")
    print(f"Force: {force}")
    
    # Change to workspace directory
    original_cwd = os.getcwd()
    os.chdir(str(workspace_dir))
    
    try:
        # Build innovus command
        files_list = [str(tcl_file)]
        files_arg = " ".join(files_list)
        innovus_cmd = (
            f'innovus -no_gui -batch '
            f'-files "{files_arg}"'
        )
        
        print(f"Executing command: {innovus_cmd}")
        
        # Execute Innovus
        result = subprocess.Popen(
            innovus_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            executable="/bin/tcsh"
        )
        
        # Stream output in real-time
        for line in result.stdout:
            print(line.rstrip())
        
        result.wait()
        
        if result.returncode != 0:
            print(f"❌ Innovus failed with return code: {result.returncode}")
            return False
        
        # Check for completion markers
        done_file = workspace_dir / "_Done_"
        route_enc = workspace_dir / "pnr_save" / "route_opt.enc.dat"
        
        if done_file.exists():
            print(f"✓ Route completion marker found: {done_file}")
        else:
            print(f"⚠️  Route completion marker not found: {done_file}")
        
        if route_enc.exists():
            print(f"✓ Route design saved: {route_enc}")
        else:
            print(f"⚠️  Route design save not found: {route_enc}")
        
        # List generated files
        print("=== Generated Files ===")
        reports_dir = workspace_dir / "pnr_reports"
        if reports_dir.exists():
            print(f"Reports directory: {reports_dir}")
            for report_file in sorted(reports_dir.glob("*")):
                size = report_file.stat().st_size if report_file.is_file() else "N/A"
                if report_file.is_file():
                    print(f"  📊 {report_file.name} ({size} bytes)")
                else:
                    print(f"  📁 {report_file.name}/")
        
        output_dir = workspace_dir / "pnr_out"
        if output_dir.exists():
            print(f"Output directory: {output_dir}")
            for output_file in sorted(output_dir.glob("*")):
                size = output_file.stat().st_size if output_file.is_file() else "N/A"
                if output_file.is_file():
                    print(f"  📄 {output_file.name} ({size} bytes)")
                else:
                    print(f"  📁 {output_file.name}/")
        
        save_dir = workspace_dir / "pnr_save"
        if save_dir.exists():
            print(f"Save directory: {save_dir}")
            for save_file in sorted(save_dir.glob("*")):
                size = save_file.stat().st_size if save_file.is_file() else "N/A"
                if save_file.is_file():
                    print(f"  💾 {save_file.name} ({size} bytes)")
                else:
                    print(f"  📁 {save_file.name}/")
        
        success = done_file.exists() or route_enc.exists()
        if success:
            print("✅ Route Completed Successfully")
        else:
            print("❌ Route may not have completed successfully")
        
        return success
        
    except Exception as e:
        print(f"❌ Error during route execution: {str(e)}")
        return False
    
    finally:
        # Restore original working directory
        os.chdir(original_cwd)

def main():
    parser = argparse.ArgumentParser(description="Route Executor - Execute route using generated TCL script")
    parser.add_argument("-mode", required=True, help="Execution mode (should be 'route')")
    parser.add_argument("-design", required=True, help="Design name")
    parser.add_argument("-technode", required=True, help="Technology node")
    parser.add_argument("-tcl", required=True, help="Path to TCL script")
    parser.add_argument("-workspace", required=True, help="Workspace directory")
    parser.add_argument("-force", action="store_true", help="Force overwrite existing files")
    
    args = parser.parse_args()
    
    if args.mode != "route":
        print(f"❌ Error: Unsupported mode '{args.mode}'. Expected 'route'.")
        sys.exit(1)
    
    tcl_file = pathlib.Path(args.tcl)
    workspace_dir = pathlib.Path(args.workspace)
    
    if not tcl_file.exists():
        print(f"❌ Error: TCL file not found: {tcl_file}")
        sys.exit(1)
    
    if not workspace_dir.exists():
        print(f"❌ Error: Workspace directory not found: {workspace_dir}")
        sys.exit(1)
    
    success = run_route_from_tcl(tcl_file, workspace_dir, args.force)
    
    if not success:
        print("❌ Route execution failed")
        sys.exit(1)
    
    print("✅ Route Executor completed successfully")

if __name__ == "__main__":
    main() 