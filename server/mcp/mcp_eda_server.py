#!/usr/bin/env python3
"""
MCP EDA Server - Complete RTL to GDSII Electronic Design Automation Flow
Provides comprehensive EDA tools for digital design implementation using Synopsys Design Compiler and Cadence Innovus
"""
import json
import os
import pathlib
import requests
import subprocess
import sys
from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP

# Project root directory
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

# EDA microservices configuration - Updated to 4-server architecture
EDA_SERVERS = {
    "synth": {"port": 13333, "endpoint": "run"},
    "unified_placement": {"port": 13340, "endpoint": "run"},
    "cts": {"port": 13338, "endpoint": "run"},
    "unified_route_save": {"port": 13341, "endpoint": "run"},
}

# Legacy mapping for backward compatibility
LEGACY_TOOL_MAPPING = {
    "synth_setup": "synth",
    "synth_compile": "synth", 
    "floorplan": "unified_placement",
    "powerplan": "unified_placement",
    "placement": "unified_placement",
    "route": "unified_route_save",
    "save": "unified_route_save",
}

# Create FastMCP instance
mcp = FastMCP("eda-server")

def call_eda_server(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call EDA microservice with specified payload"""
    # Handle legacy tool names
    if tool_name in LEGACY_TOOL_MAPPING:
        actual_tool = LEGACY_TOOL_MAPPING[tool_name]
        print(f"[MCP] Legacy tool '{tool_name}' mapped to '{actual_tool}'")
        tool_name = actual_tool
    
    if tool_name not in EDA_SERVERS:
        return {"status": "error", "detail": f"Unknown tool: {tool_name}. Available tools: {list(EDA_SERVERS.keys())}"}
    
    server_info = EDA_SERVERS[tool_name]
    url = f"http://localhost:{server_info['port']}/{server_info['endpoint']}"
    
    try:
        print(f"[MCP] Calling {tool_name} server at {url}")
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        result = response.json()
        print(f"[MCP] Server response status: {result.get('status', 'unknown')}")
        return result
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to call EDA server {tool_name}: {str(e)}"
        print(f"[MCP] Error: {error_msg}")
        return {"status": "error", "detail": error_msg}

def detect_synthesis_version(design: str) -> str:
    """Automatically detect the latest synthesis version for a design"""
    synth_dir = ROOT / "designs" / design / "FreePDK45" / "synthesis"
    if not synth_dir.exists():
        return ""
    
    subdirs = [d for d in synth_dir.iterdir() if d.is_dir()]
    if not subdirs:
        return ""
    
    # Return the most recent version directory
    return max(subdirs, key=lambda p: p.stat().st_mtime).name

def make_implementation_version(syn_ver: str, g_idx: int = 0, p_idx: int = 0) -> str:
    """Generate implementation version name from synthesis version and indices"""
    return f"{syn_ver}__g{g_idx}_p{p_idx}"

@mcp.tool()
async def synthesis(
    design: str,
    tech: str = "FreePDK45",
    version_idx: int = 0,
    force: bool = False
) -> str:
    """
    Perform complete RTL-to-gate synthesis using Synopsys Design Compiler
    
    This unified tool performs the complete synthesis flow including environment setup,
    RTL analysis, and gate-level compilation. It transforms RTL design into optimized 
    gate-level netlist while meeting timing, area, and power constraints. The tool 
    generates comprehensive timing reports, area reports, and power analysis results.
    
    Args:
        design: Design name (e.g., "b14", "leon2", "des"). Must exist in designs/ directory
        tech: Technology library name (default: "FreePDK45"). Currently supports FreePDK45
        version_idx: Configuration version index (default: 0). Used to select different synthesis configurations
        force: Force re-run even if output exists (default: False). Set to True to overwrite existing results
    
    Returns:
        JSON string containing synthesis results with status, log path, timing reports, area reports, and power reports
        
    Example:
        synthesis(design="b14", tech="FreePDK45", version_idx=0, force=False)
        
    Prerequisites:
        - Design RTL files must exist in designs/{design}/rtl/
        - Technology library must be available
        - Synthesis configuration files must be present in config/synthesis.csv
    """
    payload = {
        "design": design,
        "tech": tech,
        "version_idx": version_idx,
        "force": force
    }
    result = call_eda_server("synth", payload)
    return json.dumps(result, ensure_ascii=False, indent=2)

# synthesis_compile function removed - now integrated into unified synthesis() function

@mcp.tool()
async def unified_placement(
    design: str,
    top_module: str,
    tech: str = "FreePDK45",
    syn_ver: str = "",
    g_idx: int = 0,
    p_idx: int = 0,
    force: bool = False,
    restore_enc: str = ""
) -> str:
    """
    Perform unified placement flow: floorplanning, power planning, and standard cell placement
    
    This unified tool performs the complete placement flow including:
    1. Chip floorplanning and I/O placement
    2. Power grid planning and power mesh creation
    3. Standard cell placement optimization
    
    It creates the initial chip floorplan, sets up power distribution network,
    and places all standard cells while optimizing for timing, area, and power.
    The tool uses Cadence Innovus for the complete placement flow.
    
    Args:
        design: Design name (e.g., "b14", "leon2", "des"). Must have completed synthesis
        top_module: Top-level module name from RTL design (e.g., "b14", "leon2mp")
        tech: Technology library name (default: "FreePDK45"). Must match synthesis configuration
        syn_ver: Synthesis version string (auto-detected if empty). Format: "cpV1_clkP1_drcV1"
        g_idx: Global configuration index (default: 0). Used for implementation configuration selection
        p_idx: Placement parameter index (default: 0). Used for placement configuration selection
        force: Force re-run even if output exists (default: False). Set to True to overwrite existing results
        restore_enc: Path to restore checkpoint file (optional). Used to restore from previous stage
    
    Returns:
        JSON string containing unified placement results with status, log path, placement files, and checkpoint data
        
    Example:
        unified_placement(design="b14", top_module="b14", tech="FreePDK45", g_idx=0, p_idx=0)
        
    Prerequisites:
        - synthesis must be completed successfully
        - Top module must be correctly identified
        - Implementation configuration files must be available
    """
    if not syn_ver:
        syn_ver = detect_synthesis_version(design)
        if not syn_ver:
            return json.dumps({
                "status": "error",
                "detail": f"No synthesis version found for design {design}. Please run synthesis first."
            }, ensure_ascii=False, indent=2)
    
    payload = {
        "design": design,
        "top_module": top_module,
        "tech": tech,
        "syn_ver": syn_ver,
        "g_idx": g_idx,
        "p_idx": p_idx,
        "force": force,
        "restore_enc": restore_enc
    }
    result = call_eda_server("unified_placement", payload)
    return json.dumps(result, ensure_ascii=False, indent=2)

# power_planning function removed - now integrated into unified_placement() function

# placement function removed - now integrated into unified_placement() function

@mcp.tool()
async def clock_tree_synthesis(
    design: str,
    top_module: str,
    restore_enc: str,
    tech: str = "FreePDK45",
    impl_ver: str = "",
    force: bool = False,
    g_idx: int = 0,
    c_idx: int = 0
) -> str:
    """
    Perform clock tree synthesis and optimization
    
    This tool synthesizes the clock distribution network by inserting clock buffers
    and optimizing clock tree topology. It ensures balanced clock distribution
    while meeting clock skew and transition time requirements. The tool generates
    clock tree files and updated checkpoint data.
    
    Args:
        design: Design name (e.g., "b14", "leon2", "des"). Must have completed placement
        top_module: Top-level module name from RTL design (e.g., "b14", "leon2mp")
        restore_enc: Path to placement checkpoint file. Required to restore placement state
        tech: Technology library name (default: "FreePDK45"). Must match previous stages
        impl_ver: Implementation version string (auto-generated if empty). Format: "syn_ver__g{g_idx}_p{p_idx}"
        force: Force re-run even if output exists (default: False). Set to True to overwrite existing results
        g_idx: Global configuration index (default: 0). Used for CTS configuration
        c_idx: Clock tree parameter index (default: 0). Used for CTS optimization settings
    
    Returns:
        JSON string containing clock tree synthesis results with status, log path, clock tree files, and checkpoint data
        
    Example:
        clock_tree_synthesis(design="b14", top_module="b14", restore_enc="/path/to/placement.enc.dat", c_idx=0)
        
    Prerequisites:
        - unified_placement must be completed successfully
        - Unified placement checkpoint file must be valid
        - Clock tree synthesis configuration must be available
    """
    if not impl_ver:
        syn_ver = detect_synthesis_version(design)
        if not syn_ver:
            return json.dumps({
                "status": "error",
                "detail": f"No synthesis version found for design {design}. Please run synthesis first."
            }, ensure_ascii=False, indent=2)
        impl_ver = make_implementation_version(syn_ver, g_idx, 0)
    
    payload = {
        "design": design,
        "top_module": top_module,
        "tech": tech,
        "impl_ver": impl_ver,
        "restore_enc": restore_enc,
        "force": force,
        "g_idx": g_idx,
        "c_idx": c_idx
    }
    result = call_eda_server("cts", payload)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def unified_route_save(
    design: str,
    top_module: str,
    restore_enc: str,
    tech: str = "FreePDK45",
    impl_ver: str = "",
    force: bool = False,
    g_idx: int = 0,
    p_idx: int = 0,
    r_idx: int = 0,
    archive: bool = True
) -> str:
    """
    Perform unified routing and save flow: signal routing and final design save
    
    This unified tool performs the complete routing and save flow including:
    1. Global and detailed signal routing
    2. Post-route optimization
    3. Final design verification
    4. Output file generation and archiving
    
    It routes all signal nets between placed cells while meeting timing requirements,
    performs final optimization, and generates all required output files including
    GDSII, DEF, netlist, and reports.
    
    Args:
        design: Design name (e.g., "b14", "leon2", "des"). Must have completed CTS
        top_module: Top-level module name from RTL design (e.g., "b14", "leon2mp")
        restore_enc: Path to CTS checkpoint file. Required to restore CTS state
        tech: Technology library name (default: "FreePDK45"). Must match previous stages
        impl_ver: Implementation version string (auto-generated if empty). Format: "syn_ver__g{g_idx}_p{p_idx}"
        force: Force re-run even if output exists (default: False). Set to True to overwrite existing results
        g_idx: Global configuration index (default: 0). Used for routing configuration
        p_idx: Placement parameter index (default: 0). Must match placement configuration
        r_idx: Routing parameter index (default: 0). Used for routing optimization settings
        archive: Create archive of final results (default: True). Set to False to skip archiving
    
    Returns:
        JSON string containing unified route save results with status, log path, output files, and archive data
        
    Example:
        unified_route_save(design="b14", top_module="b14", restore_enc="/path/to/cts.enc.dat", archive=True)
        
    Prerequisites:
        - clock_tree_synthesis must be completed successfully
        - CTS checkpoint file must be valid
        - Routing configuration must be available
    """
    if not impl_ver:
        syn_ver = detect_synthesis_version(design)
        if not syn_ver:
            return json.dumps({
                "status": "error",
                "detail": f"No synthesis version found for design {design}. Please run synthesis first."
            }, ensure_ascii=False, indent=2)
        impl_ver = make_implementation_version(syn_ver, g_idx, p_idx)
    
    payload = {
        "design": design,
        "top_module": top_module,
        "tech": tech,
        "impl_ver": impl_ver,
        "restore_enc": restore_enc,
        "force": force,
        "g_idx": g_idx,
        "p_idx": p_idx,
        "r_idx": r_idx,
        "archive": archive
    }
    result = call_eda_server("unified_route_save", payload)
    return json.dumps(result, ensure_ascii=False, indent=2)

# Additional functions for updated MCP EDA Server

@mcp.tool()
async def complete_eda_flow(
    design: str,
    top_module: str,
    tech: str = "FreePDK45",
    force: bool = False
) -> str:
    """
    Execute the complete EDA flow from RTL to GDSII using unified servers
    
    This tool executes the complete digital design implementation flow using
    the updated 4-server architecture:
    1. RTL synthesis (synthesis server)
    2. Unified placement: floorplan + power + placement (unified_placement server)
    3. Clock tree synthesis (CTS server)
    4. Unified routing and save: routing + save (unified_route_save server)
    
    Args:
        design: Design name (e.g., "b14", "leon2", "des"). Must exist in designs/ directory
        top_module: Top-level module name from RTL design (e.g., "b14", "leon2mp")
        tech: Technology library name (default: "FreePDK45"). Currently supports FreePDK45
        force: Force re-run even if output exists (default: False). Set to True to overwrite existing results
    
    Returns:
        JSON string containing complete flow results with status and step-by-step results
        
    Example:
        complete_eda_flow(design="b14", top_module="b14", tech="FreePDK45", force=False)
        
    Prerequisites:
        - Design RTL files must exist in designs/{design}/rtl/
        - Technology library must be available
        - All configuration files must be present
    """
    print(f"=== Starting Complete EDA Flow for {design} ===")
    results = []
    
    try:
        # 1. Synthesis
        print("1. Executing synthesis...")
        synth_result = await synthesis(design, tech, 0, force)
        results.append({"step": "synthesis", "result": synth_result})
        
        # Check synthesis result
        synth_data = json.loads(synth_result)
        if synth_data.get("status") != "success":
            return json.dumps({
                "status": "error",
                "design": design,
                "failed_step": "synthesis",
                "error": synth_data.get("detail", "Synthesis failed"),
                "completed_steps": results
            }, ensure_ascii=False, indent=2)
        
        # 2. Unified Placement (Floorplan + Power + Placement)
        print("2. Executing unified placement (floorplan + power + placement)...")
        placement_result = await unified_placement(design, top_module, tech, "", 0, 0, force, "")
        results.append({"step": "unified_placement", "result": placement_result})
        
        # Check placement result
        placement_data = json.loads(placement_result)
        if placement_data.get("status") != "success":
            return json.dumps({
                "status": "error",
                "design": design,
                "failed_step": "unified_placement",
                "error": placement_data.get("detail", "Unified placement failed"),
                "completed_steps": results
            }, ensure_ascii=False, indent=2)
        
        # Get restore_enc from placement result for CTS
        placement_restore_enc = placement_data.get("restore_enc", "")
        
        # 3. Clock Tree Synthesis
        print("3. Executing clock tree synthesis...")
        cts_result = await clock_tree_synthesis(design, top_module, placement_restore_enc, tech, "", force, 0, 0)
        results.append({"step": "clock_tree_synthesis", "result": cts_result})
        
        # Check CTS result
        cts_data = json.loads(cts_result)
        if cts_data.get("status") != "success":
            return json.dumps({
                "status": "error",
                "design": design,
                "failed_step": "clock_tree_synthesis",
                "error": cts_data.get("detail", "Clock tree synthesis failed"),
                "completed_steps": results
            }, ensure_ascii=False, indent=2)
        
        # Get restore_enc from CTS result for routing
        cts_restore_enc = cts_data.get("restore_enc", "")
        
        # 4. Unified Route and Save (Routing + Save)
        print("4. Executing unified routing and save...")
        route_save_result = await unified_route_save(design, top_module, cts_restore_enc, tech, "", force, 0, 0, 0, True)
        results.append({"step": "unified_route_save", "result": route_save_result})
        
        # Check final result
        route_save_data = json.loads(route_save_result)
        if route_save_data.get("status") != "success":
            return json.dumps({
                "status": "error",
                "design": design,
                "failed_step": "unified_route_save",
                "error": route_save_data.get("detail", "Unified routing and save failed"),
                "completed_steps": results
            }, ensure_ascii=False, indent=2)
        
        print(f"=== Complete EDA Flow for {design} COMPLETED SUCCESSFULLY ===")
        
        return json.dumps({
            "status": "success",
            "design": design,
            "top_module": top_module,
            "tech": tech,
            "message": "Complete EDA flow executed successfully using unified 4-server architecture",
            "steps_completed": 4,
            "steps": results
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "design": design,
            "error": f"Complete EDA flow failed with exception: {str(e)}",
            "completed_steps": results
        }, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    print("=== MCP EDA Server Starting (Updated 4-Server Architecture) ===")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python version: {sys.version}")
    print("Available EDA servers:", list(EDA_SERVERS.keys()))
    print("Legacy tool mapping:", list(LEGACY_TOOL_MAPPING.keys()))
    print("Starting MCP server (stdio mode) - Waiting for Claude Desktop connection")
    print("Press Ctrl+C to stop server")
    
    try:
        mcp.run(transport='stdio')
    except KeyboardInterrupt:
        print("\n=== MCP EDA Server Stopped ===")
    except Exception as e:
        print(f"Server startup failed: {e}")
        sys.exit(1)