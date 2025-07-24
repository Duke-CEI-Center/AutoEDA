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

def run_save_from_tcl(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, force: bool = False):
    """Execute save using the generated TCL file with Innovus"""
    
    # Setup EDA environment
    setup_eda_environment()
    
    print(f"=== Save Executor Started ===")
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
        finished_file = workspace_dir / "_Finished_"
        
        if done_file.exists():
            print(f"✓ Save completion marker found: {done_file}")
        elif finished_file.exists():
            print(f"✓ Save completion marker found: {finished_file}")
        else:
            print(f"⚠️  Save completion marker not found: {done_file} or {finished_file}")
        
        # List generated files
        print("=== Generated Files ===")
        output_dir = workspace_dir / "pnr_out"
        if output_dir.exists():
            print(f"Output directory: {output_dir}")
            for output_file in sorted(output_dir.glob("*")):
                size = output_file.stat().st_size if output_file.is_file() else "N/A"
                if output_file.is_file():
                    print(f"  📄 {output_file.name} ({size} bytes)")
                else:
                    print(f"  📁 {output_file.name}/")
        
        # Check for key artifacts
        expected_artifacts = [
            "*.gds",
            "*.gds.gz", 
            "*_pnr.lef",
            "*_lib.lef",
            "*_pnr.v"
        ]
        
        found_artifacts = []
        for pattern in expected_artifacts:
            matches = list(output_dir.glob(pattern))
            if matches:
                found_artifacts.extend([m.name for m in matches])
        
        if found_artifacts:
            print(f"✓ Key artifacts found: {', '.join(found_artifacts)}")
        else:
            print(f"⚠️  No key artifacts found in {output_dir}")
        
        success = done_file.exists() or finished_file.exists() or bool(found_artifacts)
        if success:
            print("✅ Save Completed Successfully")
        else:
            print("❌ Save may not have completed successfully")
        
        return success
        
    except Exception as e:
        print(f"❌ Error during save execution: {str(e)}")
        return False
    
    finally:
        # Restore original working directory
        os.chdir(original_cwd)

def main():
    parser = argparse.ArgumentParser(description="Save Executor - Execute save using generated TCL script")
    parser.add_argument("-mode", required=True, help="Execution mode (should be 'save')")
    parser.add_argument("-design", required=True, help="Design name")
    parser.add_argument("-technode", required=True, help="Technology node")
    parser.add_argument("-tcl", required=True, help="Path to TCL script")
    parser.add_argument("-workspace", required=True, help="Workspace directory")
    parser.add_argument("-force", action="store_true", help="Force overwrite existing files")
    
    args = parser.parse_args()
    
    if args.mode != "save":
        print(f"❌ Error: Unsupported mode '{args.mode}'. Expected 'save'.")
        sys.exit(1)
    
    tcl_file = pathlib.Path(args.tcl)
    workspace_dir = pathlib.Path(args.workspace)
    
    if not tcl_file.exists():
        print(f"❌ Error: TCL file not found: {tcl_file}")
        sys.exit(1)
    
    if not workspace_dir.exists():
        print(f"❌ Error: Workspace directory not found: {workspace_dir}")
        sys.exit(1)
    
    success = run_save_from_tcl(tcl_file, workspace_dir, args.force)
    
    if not success:
        print("❌ Save execution failed")
        sys.exit(1)
    
    print("✅ Save Executor completed successfully")

if __name__ == "__main__":
    main() 