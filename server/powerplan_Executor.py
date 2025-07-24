#!/usr/bin/env python3

import os
import sys
import pathlib
import subprocess
import argparse
import logging

def setup_eda_environment():
    """Setup EDA tool paths in environment"""
    eda_tool_paths = [
        "/opt/cadence/innovus221/tools/bin",
        "/opt/cadence/genus172/bin"
    ]
    
    current_path = os.environ.get("PATH", "")
    new_path = ":".join(eda_tool_paths + [current_path])
    os.environ["PATH"] = new_path
    
    print(f"Updated PATH: {new_path}")

def run_powerplan_from_tcl(tcl_file: pathlib.Path, workspace_dir: pathlib.Path, force: bool = False):
    """Execute powerplan using the generated TCL file"""
    
    print(f"Starting powerplan execution...")
    print(f"TCL file: {tcl_file}")
    print(f"Workspace: {workspace_dir}")
    print(f"Force: {force}")
    
    # Setup EDA environment
    setup_eda_environment()
    
    # Change to workspace directory
    original_cwd = pathlib.Path.cwd()
    os.chdir(workspace_dir)
    
    try:
        # Check if TCL file exists
        if not tcl_file.exists():
            raise FileNotFoundError(f"TCL file not found: {tcl_file}")
        
        # Build innovus command
        files_list = [str(tcl_file)]
        files_arg = " ".join(files_list)
        innovus_cmd = (
            f'innovus -no_gui -batch '
            f'-files "{files_arg}"'
        )
        
        print(f"Executing command: {innovus_cmd}")
        
        # Execute innovus with tcsh for license compatibility
        process = subprocess.Popen(
            innovus_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            executable="/bin/tcsh",  # Use tcsh for license compatibility
            cwd=workspace_dir
        )
        
        # Stream output
        for line in process.stdout:
            print(line.rstrip())
        
        process.wait()
        
        if process.returncode != 0:
            raise RuntimeError(f"innovus failed with return code {process.returncode}")
        
        # Check for completion marker
        done_file = workspace_dir / "_Done_"
        if not done_file.exists():
            raise RuntimeError("Powerplan did not complete successfully (_Done_ file not found)")
        
        # Check for powerplan.enc.dat
        powerplan_enc = workspace_dir / "pnr_save" / "powerplan.enc.dat"
        if powerplan_enc.exists():
            print(f"✓ Powerplan design saved: {powerplan_enc}")
        else:
            powerplan_enc_file = workspace_dir / "pnr_save" / "powerplan.enc"
            if powerplan_enc_file.exists():
                print(f"✓ Powerplan design saved: {powerplan_enc_file}")
            else:
                print("⚠ Warning: powerplan.enc(.dat) not found")
        
        # List generated files
        print("\n=== Generated Files ===")
        
        # Reports
        reports_dir = workspace_dir / "pnr_reports"
        if reports_dir.exists():
            print(f"Reports directory: {reports_dir}")
            for rpt_file in reports_dir.glob("*"):
                if rpt_file.is_file():
                    size = rpt_file.stat().st_size
                    print(f"  📊 {rpt_file.name} ({size} bytes)")
        
        # Output files
        output_dir = workspace_dir / "pnr_out"
        if output_dir.exists():
            print(f"Output directory: {output_dir}")
            for out_file in output_dir.glob("*"):
                if out_file.is_file():
                    size = out_file.stat().st_size
                    print(f"  📄 {out_file.name} ({size} bytes)")
        
        # Save files
        save_dir = workspace_dir / "pnr_save"
        if save_dir.exists():
            print(f"Save directory: {save_dir}")
            for save_file in save_dir.glob("*"):
                if save_file.is_file():
                    size = save_file.stat().st_size
                    print(f"  💾 {save_file.name} ({size} bytes)")
                elif save_file.is_dir():
                    print(f"  📁 {save_file.name}/")
        
        print("✅ Powerplan Completed Successfully")
        
    finally:
        # Restore original working directory
        os.chdir(original_cwd)

def main():
    parser = argparse.ArgumentParser(description="MCP EDA Powerplan Executor")
    parser.add_argument("-mode", required=True, help="Execution mode (powerplan)")
    parser.add_argument("-design", required=True, help="Design name")
    parser.add_argument("-technode", required=True, help="Technology node")
    parser.add_argument("-tcl", required=True, help="TCL file to execute")
    parser.add_argument("-workspace", required=True, help="Workspace directory")
    parser.add_argument("-force", action="store_true", help="Force overwrite existing files")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    print("=" * 60)
    print("MCP EDA Powerplan Executor")
    print("=" * 60)
    print(f"Mode: {args.mode}")
    print(f"Design: {args.design}")
    print(f"Technology: {args.technode}")
    print(f"TCL file: {args.tcl}")
    print(f"Workspace: {args.workspace}")
    print(f"Force: {args.force}")
    print("=" * 60)
    
    try:
        if args.mode == "powerplan":
            tcl_file = pathlib.Path(args.tcl)
            workspace_dir = pathlib.Path(args.workspace)
            
            run_powerplan_from_tcl(tcl_file, workspace_dir, args.force)
        else:
            print(f"❌ Unknown mode: {args.mode}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 