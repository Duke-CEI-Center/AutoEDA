#!/usr/bin/env python3
"""
Simple MCP Client
Simplified MCP client for testing token counts, supporting 4 core EDA servers:
1. synth - synthesis
2. placement - unified placement (including floorplan, powerplan, placement)  
3. cts - clock tree synthesis
4. route - unified routing and save (including route, save)
"""

import requests
import json
import re
from typing import Dict, Optional, Any
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Server configurations
SERVER_CONFIGS = {
    "synth": {
        "port": 13333,  
        "endpoint": "/run",
        "description": "Synthesis service - Convert RTL code to gate-level netlist"
    },
    "placement": {
        "port": 13340,  
        "endpoint": "/run", 
        "description": "Unified placement service - Including floorplan, powerplan, placement"
    },
    "cts": {
        "port": 13338,  
        "endpoint": "/run",
        "description": "Clock tree synthesis service - Generate clock distribution network"
    },
    "route": {
        "port": 13341,  
        "endpoint": "/run",
        "description": "Unified routing service - Including route and save"
    }
}

# Default parameters for each server
DEFAULT_PARAMS = {
    "synth": {
        "design": "des",
        "tech": "FreePDK45", 
        "version_idx": 0,
        "force": True,
        "auto_timestamp": True,
        "syn_version": "cpV1_clkP1_drcV1",
        "clk_period": 1.0,
        "DRC_max_fanout": 10,
        "DRC_max_transition": 0.5,
        "DRC_max_capacitance": 5,
        "DRC_high_fanout_net_threshold": 10,
        "DRC_high_fanout_pin_capacitance": 0.01,
        "compile_cmd": "compile",
        "power_effort": "high",
        "area_effort": "high", 
        "map_effort": "high",
        "set_dyn_opt": True,
        "set_lea_opt": True
    },
    "placement": {
        "design": "des",
        "tech": "FreePDK45",
        "syn_ver": "cpV1_clkP1_drcV1",  
        "force": True,
        "top_module": "des3",
        "design_flow_effort": "standard",
        "design_power_effort": "none", 
        "ASPECT_RATIO": 1.0,
        "target_util": 0.7,
        "clock_name": "clk",
        "clock_period": 1.0,
        "place_global_timing_effort": "medium",
        "place_global_cong_effort": "medium",
        "place_detail_wire_length_opt_effort": "medium",
        "place_global_max_density": 0.9,
        "place_activity_power_driven": False,
        "prects_opt_max_density": 0.8,
        "prects_opt_power_effort": "low", 
        "prects_opt_reclaim_area": False,
        "prects_fix_fanout_load": False
    },
    "cts": {
        "design": "des",
        "tech": "FreePDK45",
        "impl_ver": "cpV1_clkP1_drcV1__g0_p0",  
        "force": True,
        "restore_enc": "/home/yl996/proj/mcp-eda-example/designs/des/FreePDK45/implementation/cpV1_clkP1_drcV1__g0_p0/pnr_save/placement.enc.dat",
        "top_module": "des3",
        "design_flow_effort": "standard",
        "design_power_effort": "none",
        "target_util": 0.7,
        "cts_cell_density": 0.5,
        "cts_clock_gate_buffering_location": "below",
        "cts_clone_clock_gates": True,
        "postcts_opt_max_density": 0.8,
        "postcts_opt_power_effort": "low",
        "postcts_opt_reclaim_area": False,
        "postcts_fix_fanout_load": False
    },
    "route": {
        "design": "des",
        "tech": "FreePDK45", 
        "impl_ver": "cpV1_clkP1_drcV1__g0_p0",  
        "restore_enc": "/home/yl996/proj/mcp-eda-example/designs/des/FreePDK45/implementation/cpV1_clkP1_drcV1__g0_p0/pnr_save/cts.enc.dat",
        "force": True,
        "top_module": "des3",
        "archive": True,
        "design_flow_effort": "standard",
        "design_power_effort": "none",
        "target_util": 0.7,
        "place_global_timing_effort": "medium",
        "place_global_cong_effort": "medium", 
        "place_detail_wire_length_opt_effort": "medium",
        "place_global_max_density": 0.9,
        "place_activity_power_driven": False,
        "prects_opt_max_density": 0.8,
        "prects_opt_power_effort": "low",
        "prects_opt_reclaim_area": False,
        "prects_fix_fanout_load": False,
        "cts_cell_density": 0.5,
        "cts_clock_gate_buffering_location": "below",
        "cts_clone_clock_gates": True,
        "postcts_opt_max_density": 0.8,
        "postcts_opt_power_effort": "low",
        "cts_opt_reclaim_area": False,
        "cts_fix_fanout_load": False
    }
}

class SimpleClientRequest(BaseModel):
    user_input: str
    server_type: Optional[str] = None  
    custom_params: Optional[Dict[str, Any]] = {}  

class SimpleClientResponse(BaseModel):
    status: str
    server_used: str
    final_params: Dict[str, Any]
    server_response: Dict[str, Any]
    message: str

class SimpleMCPClient:
    def __init__(self):
        self.app = FastAPI(title="Simple MCP Client")
        self._setup_routes()
        
    def _setup_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def home():
            """Main page showing available services and examples"""
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Simple MCP Client</title>
                <style>
                    body { font-family: Arial; margin: 40px; }
                    .server { margin: 20px 0; padding: 15px; border: 1px solid #ddd; }
                    .example { background: #f5f5f5; padding: 10px; margin: 10px 0; }
                    code { background: #f0f0f0; padding: 2px 4px; }
                </style>
            </head>
            <body>
                <h1>Simple MCP Client</h1>
                <p>Simplified MCP client supporting 4 core EDA services:</p>
                
                <div class="server">
                    <h3>Available Services</h3>
                    <ul>
                        <li><strong>synth</strong> (port 13333) - Synthesis service</li>
                        <li><strong>placement</strong> (port 13340) - Unified placement service</li>
                        <li><strong>cts</strong> (port 13338) - Clock tree synthesis service</li>
                        <li><strong>route</strong> (port 13341) - Unified routing service</li>
                    </ul>
                </div>
                
                <div class="server">
                    <h3>Usage</h3>
                    <p>POST request to <code>/run</code> endpoint:</p>
                    <div class="example">
                        <strong>Example 1: Auto-detect service type</strong><br>
                        <code>{"user_input": "run synthesis"}</code>
                    </div>
                    <div class="example">
                        <strong>Example 2: Specify service type</strong><br>
                        <code>{"user_input": "start placement", "server_type": "placement"}</code>
                    </div>
                    <div class="example">
                        <strong>Example 3: Custom parameters</strong><br>
                        <code>{"user_input": "run CTS", "custom_params": {"clk_period": 2.0}}</code>
                    </div>
                </div>
            </body>
            </html>
            """
            return html_content
            
        @self.app.post("/run", response_model=SimpleClientResponse)
        async def run_eda_task(request: SimpleClientRequest):
            """Run EDA task"""
            return await self._process_request(request)
    
    async def _process_request(self, request: SimpleClientRequest) -> SimpleClientResponse:
        """Process user request"""
        try:
            # 1. Determine server type
            server_type = request.server_type or self._identify_server_type(request.user_input)
            
            if not server_type:
                return SimpleClientResponse(
                    status="error",
                    server_used="none",
                    final_params={},
                    server_response={},
                    message="Unable to identify server type, please specify server_type or use clear keywords"
                )
            
            # 2. Prepare parameters
            final_params = DEFAULT_PARAMS[server_type].copy()
            
            # 3. Apply custom parameters
            if request.custom_params:
                final_params.update(request.custom_params)
            
            # 4. Call corresponding server
            server_response = await self._call_server(server_type, final_params)
            
            return SimpleClientResponse(
                status="success",
                server_used=server_type,
                final_params=final_params,
                server_response=server_response,
                message=f"Successfully called {server_type} server"
            )
            
        except Exception as e:
            return SimpleClientResponse(
                status="error",
                server_used=server_type if 'server_type' in locals() else "unknown",
                final_params={},
                server_response={},
                message=f"Error processing request: {str(e)}"
            )
    
    def _identify_server_type(self, user_input: str) -> Optional[str]:
        """Identify server type based on user input"""
        user_input_lower = user_input.lower()
        
        # Synthesis keywords
        synth_keywords = ["synthesis", "synth", "compile", "rtl", "gate", "综合", "门级"]
        if any(keyword in user_input_lower for keyword in synth_keywords):
            return "synth"
        
        # Placement keywords  
        placement_keywords = ["placement", "place", "floorplan", "powerplan", "floor", "power", "布局"]
        if any(keyword in user_input_lower for keyword in placement_keywords):
            return "placement"
        
        # CTS keywords
        cts_keywords = ["cts", "clock", "tree", "clock tree", "时钟", "时钟树"]
        if any(keyword in user_input_lower for keyword in cts_keywords):
            return "cts"
        
        # Routing keywords
        route_keywords = ["route", "routing", "wire", "save", "布线", "连线", "保存"]
        if any(keyword in user_input_lower for keyword in route_keywords):
            return "route"
        
        return None
    
    async def _call_server(self, server_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call specified server"""
        config = SERVER_CONFIGS[server_type]
        url = f"http://localhost:{config['port']}{config['endpoint']}"
        
        try:
            response = requests.post(url, json=params, timeout=300)  # 5 minutes timeout
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "error": f"Failed to call {server_type} server: {str(e)}",
                "url": url,
                "params": params
            }

def main():
    """Main function"""
    client = SimpleMCPClient()
    
    print("Starting Simple MCP Client...")
    print("Supported services: synth, placement, cts, route")
    print("Web interface: http://localhost:8888")
    print("API endpoint: http://localhost:8888/run")
    
    uvicorn.run(client.app, host="0.0.0.0", port=8888)

if __name__ == "__main__":
    main() 