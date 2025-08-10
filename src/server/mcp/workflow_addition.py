# Additional functions for updated MCP EDA Server

@mcp.tool()
async def complete_eda_flow(
    design: str,
    top_module: str,
    tech: str = "FreePDK45",
    force: bool = False
) -> str:
    """
    Execute the complete EDA flow from RTL to GDSII using 4-server architecture
    
    This tool executes the complete digital design implementation flow using
    the updated 4-server architecture:
    1. RTL synthesis (synthesis server)
    2. Placement: floorplan + power + placement (placement server)
    3. Clock tree synthesis (CTS server)
    4. Routing and save: routing + save (routing server)
    
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
        
        # 2. Placement (Floorplan + Power + Placement)
        print("2. Executing placement (floorplan + power + placement)...")
        placement_result = await placement(design, top_module, tech, "", 0, 0, force, "")
        results.append({"step": "placement", "result": placement_result})
        
        # Check placement result
        placement_data = json.loads(placement_result)
        if placement_data.get("status") != "success":
            return json.dumps({
                "status": "error",
                "design": design,
                "failed_step": "placement",
                "error": placement_data.get("detail", "Placement failed"),
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
        
        # 4. Route and Save (Routing + Save)
        print("4. Executing routing and save...")
        route_save_result = await routing(design, top_module, cts_restore_enc, tech, "", force, 0, 0, 0, True)
        results.append({"step": "routing", "result": route_save_result})
        
        # Check final result
        route_save_data = json.loads(route_save_result)
        if route_save_data.get("status") != "success":
            return json.dumps({
                "status": "error",
                "design": design,
                "failed_step": "routing",
                "error": route_save_data.get("detail", "Routing and save failed"),
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