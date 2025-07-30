#!/usr/bin/env python3
"""
CTS (Clock Tree Synthesis) Server Implementation

This module provides the UnifiedCtsServer class for CTS workflows.

Usage:
    python unified_server/cts_server.py

API Endpoints:
    POST /run - Execute the CTS workflow
    curl -X POST http://localhost:15335/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}'
    curl -X POST http://localhost:15335/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45", "force": false}'
"""

import argparse
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, List, Tuple

# Import the base class
from unified_server import UnifiedServerBase

# Add project root to Python path
ROOT = Path(__file__).resolve().parent.parent

class UnifiedCtsServer(UnifiedServerBase):
    """
    Unified CTS Server implementation.
    
    Workspace Structure:
        designs/{design}/{tech}/implementation/{syn_ver}__{impl_ver}/
        ├── pnr_save/      
        ├── pnr_out/      
        └── pnr_reports/   
    
    TCL Scripts Used:
        - scripts/{tech}/backend/5_cts.tcl
    
    Note: Auto-detects placement.enc from latest placement run if restore_enc not specified.
    
    Files created:
        5_cts.tcl 
        Reports:
          pnr_reports/cts_opt_timing.rpt.gz  
          pnr_reports/ccopt.txt               
        Output Files:
          pnr_out/clock.def                  
          pnr_out/${TOP_NAME}_cts.v           
          pnr_out/RC_cts.spef.gz              
          pnr_out/${TOP_NAME}_cts.gds.gz      
        Design Saves:
          pnr_save/cts.enc                    
    """
    
    def __init__(self):
        super().__init__(
            server_name="cts",
            log_dir_name="unified_cts",
            port_env="UNIFIED_CTS_PORT",
            default_port=13341
        )
    
    def get_request_model(self):
        """
        Define the request model for CTS server.
        """
        class UnifiedCtsReq(BaseModel):
            design: str
            tech: str = "FreePDK45"
            syn_ver: str = None
            impl_ver: str = None
            restore_enc: str = None
            force: bool = True
            skip_execution: bool = False
            # 5_cts.tcl
            cell_density: float = 0.5
            clock_gate_buffering_location: str = "below"
            clone_clock_gates: str = "true"
            maxDensity: float = 0.8
            powerEffort: str = "low"
            reclaimArea: str = "default"
            fixFanoutLoad: str = "true"
        return UnifiedCtsReq
    
    def get_response_model(self):
        """
        Define the response model for CTS server.
        
        Returns:
        - status: Execution status
        - log_path: Path to log file
        - reports: Dictionary of report files
        - tcl_path: Path to generated TCL script
        """
        class UnifiedCtsResp(BaseModel):
            status: str
            log_path: str
            reports: dict
            tcl_path: str
        return UnifiedCtsResp
    
    def get_workspace_setup_method(self):
        """Use standard workspace setup"""

        return self.setup_workspace
    
    def get_executor_call_method(self):
        """Use standard executor calling"""
        return self.call_executor
    
    def get_report_files(self):
        """
        Define which reports to collect after CTS.
        
        Returns list of (base_name, gz_name) pairs.
        The system will look for gz_name first, then base_name.
        """
        return [
            ("cts_opt_timing.rpt", "cts_opt_timing.rpt.gz"),
        ]
    
    def get_workspace_directory(self, req):
        """
        Define workspace directory structure.
        
        Format: designs/{design}/{tech}/implementation/{syn_ver}__{impl_ver}
        """
        return ROOT / "designs" / req.design / req.tech / "implementation" / f"{req.syn_ver}__{req.impl_ver}"
    
    def get_auto_version_field(self, req):
        """Auto-version the impl_ver field if None"""
        # Auto-version syn_ver if not set
        if req.syn_ver is None:
            req.syn_ver = self._find_latest_synthesis_version(req.design, req.tech)
        
        # Auto-version impl_ver if not set
        if req.impl_ver is None:
            req.impl_ver = self._find_latest_implementation_version(req.design, req.tech, req.syn_ver)

        # Auto-detect placement.enc if not provided
        if req.restore_enc is None:
            if req.skip_execution is False:
                req.restore_enc = self._find_latest_enc_file(req.design, req.tech, req.syn_ver, req.impl_ver, "placement")
            else:
                req.restore_enc = None

        return "impl_ver"
    
    # def setup_workspace(self, req, log_file: Path) -> Tuple[bool, str, Path, Dict]:
    #     """
    #     Custom workspace setup for CTS that preserves directory.
        
    #     This is needed because CTS requires placement.enc from the previous placement run,
    #     but the standard setup would delete pnr_save when force=True.
    #     """
    #     try:
    #         workspace_dir = self.get_workspace_directory(req)
            
    #         # Check if directories exist
    #         if workspace_dir.exists():
    #             if not getattr(req, 'force', True):
    #                 # Collect existing reports to return last call response
    #                 reports = self._collect_existing_reports(workspace_dir)
                    
    #                 with log_file.open("w") as lf:
    #                     lf.write(f"=== {self.server_name} Workspace Setup ===\n")
    #                     lf.write(f"[Warning] {workspace_dir} already exists! Skipped...\n")
    #                     lf.write(f"Returning last call response.\n")
                    
    #                 return True, "workspace created (already existed)", workspace_dir, reports
    #             else:
    #                 # Force overwrite - remove only CTS-specific files, preserve placement.enc
    #                 cts_files_to_remove = [
    #                     workspace_dir / "pnr_save" / "cts.enc",
    #                     workspace_dir / "pnr_reports" / "cts_summary.rpt",
    #                     workspace_dir / "pnr_reports" / "postcts_opt_max_density.rpt",
    #                     workspace_dir / "pnr_reports" / "ccopt.txt"
    #                 ]
                    
    #                 for file_path in cts_files_to_remove:
    #                     if file_path.exists():
    #                         file_path.unlink()
    #                         print(f"Removed existing CTS file: {file_path}")
            
    #         # Create all necessary subdirectories
    #         workspace_dir.mkdir(parents=True, exist_ok=True)
    #         for subdir in self.get_output_directories():
    #             (workspace_dir / subdir).mkdir(exist_ok=True)
            
    #         with log_file.open("w") as lf:
    #             lf.write(f"=== {self.server_name} Workspace Setup ===\n")
    #             lf.write(f"Workspace Directory: {workspace_dir}\n")
    #             lf.write("Workspace setup completed successfully (preserved pnr_save).\n")

    #         return True, "workspace created", workspace_dir, {}

    #     except Exception as e:
    #         return False, f"error: {e}", None, {}
    
    def get_tcl_script_config(self, req) -> Dict:
        """
        Configure TCL script generation for CTS.
        
        This defines:
        - Which TCL scripts to combine
        - What title and version info to include
        - What footer content to add
        - Output filename
        """
        return {
            'title': 'Complete Unified CTS TCL Script',
            'version_info': f'Implementation Version: {req.impl_ver}',
            'script_paths': [
                ROOT / "scripts" / req.tech / "backend" / "5_cts.tcl"
            ],
            'script_section_title': 'Backend Scripts',
            'footer_title': 'CTS completed',
            'output_filename': 'complete_unified_cts.tcl'
        }
    
    def get_output_directories(self) -> List[str]:
        """Define output directories for CTS workflow"""
        return ["pnr_save", "pnr_out", "pnr_reports"]
    
    def get_reports_directory(self) -> str:
        """Define reports directory for CTS workflow"""
        return "pnr_reports"


if __name__ == "__main__":
    """
    Main execution block for CTS server.
    
    Usage:
    - python unified_server/cts_server.py --port 13341           # CTS server
    
    API Usage:
    curl -X POST http://localhost:13341/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}'
    """
    parser = argparse.ArgumentParser(
        description="CTS Server Implementation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
- python unified_server/cts_server.py --port 13341           # CTS server

API Usage:
curl -X POST http://localhost:13341/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}'
        """
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Listen port (overrides environment variable and default)",
    )
    args = parser.parse_args()

    print("Starting CTS server...")
    server = UnifiedCtsServer()
    server.run_server(args.port) 