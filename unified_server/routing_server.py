#!/usr/bin/env python3
"""
Routing Server Implementation

This module provides the UnifiedRoutingServer class for routing workflows.

Usage:
    python unified_server/routing_server.py 

API Endpoints:
    POST /run - Execute the routing workflow
    curl -X POST http://localhost:15336/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}'  | python -m json.tool
    curl -X POST http://localhost:15336/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45", "force": false}'  | python -m json.tool

"""

import argparse
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, List, Tuple

# Import the base class
from unified_server import UnifiedServerBase

# Add project root to Python path
ROOT = Path(__file__).resolve().parent.parent

class UnifiedRoutingServer(UnifiedServerBase):
    """
    Unified Routing Server implementation.
    
    Workspace Structure:
        designs/{design}/{tech}/implementation/{syn_ver}__{impl_ver}/
        ├── pnr_save/      
        ├── pnr_out/      
        └── pnr_reports/   
    
    TCL Scripts Used:
        - scripts/{tech}/backend/7_route.tcl
        - scripts/{tech}/backend/8_save_design.tcl
    
    Note: Auto-detects restore_enc from latest CTS run if restore_enc not specified.

    Files created:
        7_route.tcl 
        Reports:
          pnr_reports/route_timing.rpt.gz         
          pnr_reports/route_opt_timing.rpt.gz     
          pnr_reports/route_summary.rpt           
          pnr_reports/congestion.rpt              
          pnr_reports/postRoute_drc_max1M.rpt     
          pnr_reports/postOpt_drc_max1M.rpt       
          pnr_reports/route_opt_power/design.rpt.gz
          pnr_reports/route_opt_power/clock.rpt.gz 
        Output Files:
          pnr_out/route.def                       
          pnr_out/RC.spef.gz                      
        Design Saves:
          pnr_save/global_route.enc               
          pnr_save/detail_route.enc               
          pnr_save/route_opt.enc                  
        8_save_design.tcl 
        Output Files:
          pnr_out/${TOP_NAME}_pnr.lef             
          pnr_out/${TOP_NAME}_lib.lef             
          pnr_out/${TOP_NAME}_pnr.v               
          pnr_out/${TOP_NAME}_pnr.gds.gz          
    """
    
    def __init__(self):
        super().__init__(
            server_name="routing",
            log_dir_name="unified_routing",
            port_env="UNIFIED_ROUTING_PORT",
            default_port=13342
        )
    
    def get_request_model(self):
        """
        Define the request model for routing server.
        """
        class UnifiedRoutingReq(BaseModel):
            design: str
            tech: str = "FreePDK45"
            syn_ver: str = None
            impl_ver: str = None
            # restore_enc: str = None
            force: bool = True
            skip_execution: bool = False
        return UnifiedRoutingReq
    
    def get_response_model(self):
        """
        Define the response model for routing server.
        """
        class UnifiedRoutingResp(BaseModel):
            status: str
            log_path: str
            reports: dict
            tcl_path: str
        return UnifiedRoutingResp
    
    def get_workspace_setup_method(self):
        """Use custom workspace setup that preserves cts.enc"""
        return self.setup_workspace
    
    def get_executor_call_method(self):
        """Use standard executor calling"""
        return self.call_executor
    
    def get_report_files(self):
        """
        Define which reports to collect after routing.
        
        Returns list of (base_name, gz_name) pairs.
        The system will look for gz_name first, then base_name.
        """
        return [
            ("route_summary.rpt", "route_summary.rpt"),
            ("route_timing.rpt", "route_timing.rpt.gz"),
            ("route_opt_timing.rpt", "route_opt_timing.rpt.gz"),
            ("postRoute_drc_max1M.rpt", "postRoute_drc_max1M.rpt"),
            ("postOpt_drc_max1M.rpt", "postOpt_drc_max1M.rpt"),
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

        return "impl_ver"
    
    # def setup_workspace(self, req, log_file: Path) -> Tuple[bool, str, Path, Dict]:
    #     """
    #     Custom workspace setup for routing that preserves directory.
        
    #     This is needed because routing requires cts.enc from the previous CTS run,
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
    #                 # Force overwrite - remove only routing-specific files, preserve cts.enc
    #                 routing_files_to_remove = [
    #                     workspace_dir / "pnr_save" / "global_route.enc",
    #                     workspace_dir / "pnr_save" / "detail_route.enc",
    #                     workspace_dir / "pnr_save" / "route_opt.enc",
    #                     workspace_dir / "pnr_reports" / "route_summary.rpt",
    #                     workspace_dir / "pnr_reports" / "route_timing.rpt.gz",
    #                     workspace_dir / "pnr_reports" / "route_opt_timing.rpt.gz",
    #                     workspace_dir / "pnr_reports" / "congestion.rpt",
    #                     workspace_dir / "pnr_reports" / "postRoute_drc_max1M.rpt",
    #                     workspace_dir / "pnr_reports" / "postOpt_drc_max1M.rpt",
    #                     workspace_dir / "pnr_out" / "route.def",
    #                     workspace_dir / "pnr_out" / "RC.spef.gz",
    #                     workspace_dir / "pnr_out" / f"{req.design}_pnr.lef",
    #                     workspace_dir / "pnr_out" / f"{req.design}_lib.lef",
    #                     workspace_dir / "pnr_out" / f"{req.design}_pnr.v",
    #                     workspace_dir / "pnr_out" / f"{req.design}_pnr.gds.gz"
    #                 ]
                    
    #                 for file_path in routing_files_to_remove:
    #                     if file_path.exists():
    #                         file_path.unlink()
    #                         print(f"Removed existing routing file: {file_path}")
            
    #         # Create all necessary subdirectories
    #         workspace_dir.mkdir(parents=True, exist_ok=True)
    #         for subdir in self.get_output_directories():
    #             (workspace_dir / subdir).mkdir(exist_ok=True)
            
    #         with log_file.open("w") as lf:
    #             lf.write(f"=== {self.server_name} Workspace Setup ===\n")
    #             lf.write(f"Workspace Directory: {workspace_dir}\n")
    #             lf.write("Workspace setup completed successfully (preserved cts.enc).\n")

    #         return True, "workspace created", workspace_dir, {}

    #     except Exception as e:
    #         return False, f"error: {e}", None, {}
    
    def _find_latest_cts_enc(self, design: str, tech: str, syn_ver: str, impl_ver: str) -> str:
        """
        Find the latest cts.enc file for a given design and technology.
            
        Returns:
            Path to the latest cts.enc file
        """
        return super()._find_latest_enc_file(design, tech, syn_ver, impl_ver, "cts")

    def get_tcl_script_config(self, req) -> Dict:
        """
        Configure TCL script generation for routing.
        
        This defines:
        - Which TCL scripts to combine
        - What title and version info to include
        - What footer content to add
        - Output filename
        """
        return {
            'title': 'Complete Unified Routing TCL Script (Route + Save)',
            'version_info': f'Implementation Version: {req.impl_ver}',
            'script_paths': [
                ROOT / "scripts" / req.tech / "backend" / "7_route.tcl",
                ROOT / "scripts" / req.tech / "backend" / "8_save_design.tcl"
            ],
            'script_section_title': 'Backend Scripts',
            'footer_title': 'Routing completed',
            'output_filename': 'complete_unified_routing.tcl'
        }
    
    def get_output_directories(self) -> List[str]:
        """Define output directories for routing workflow"""
        return ["pnr_save", "pnr_out", "pnr_reports"]
    
    def get_reports_directory(self) -> str:
        """Define reports directory for routing workflow"""
        return "pnr_reports"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Routing Server Implementation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
- python unified_server/routing_server.py --port 13342      

API Usage:
curl -X POST http://localhost:13342/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}'
        """
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Listen port (overrides environment variable and default)",
    )
    args = parser.parse_args()

    print("Starting routing server...")
    server = UnifiedRoutingServer()
    server.run_server(args.port) 