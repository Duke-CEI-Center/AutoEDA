# MCP EDA Implementation Guide

## Overview

This project implements a comprehensive MCP (Model Context Protocol) EDA server system, providing a complete digital design flow from RTL to GDSII using a modern unified 4-server architecture. The implementation leverages Claude Desktop integration for natural language EDA tool interaction and uses the FastMCP framework for robust server development.

## Architecture Design

### Unified 4-Server Architecture
- **FastMCP Framework**: Uses the officially recommended FastMCP framework for robust MCP server development
- **Consolidated Microservices**: 4 unified servers handle complete EDA stages:
  - **SynthesisServer** (port 18001): Complete RTL-to-gate synthesis
  - **PlacementServer** (port 18002): Floorplan + power planning + placement
  - **CtsServer** (port 18003): Clock tree synthesis and optimization
  - **RoutingServer** (port 18004): Global/detailed routing + final save
- **Tool-based Design**: Each major EDA flow is encapsulated as an independent MCP tool with comprehensive parameter handling
- **Legacy Compatibility**: Backward compatibility mapping for legacy tool names

### Client Architecture
- **Claude Desktop Integration**: Direct integration with Claude Desktop for natural language interaction
- **Type Safety**: Complete type annotations with comprehensive error handling
- **Clean API**: Intuitive tool calling interface with natural language support
- **Session Management**: Context-aware tool execution with checkpoint management

## File Structure

```
src/
├── server/
│   ├── mcp/
│   │   ├── mcp_eda_server.py           # Main MCP server (4-server architecture)
│   │   ├── workflow_addition.py        # Additional workflow functions
│   │   ├── claude_desktop_config.json  # Claude Desktop configuration
│   │   ├── start_mcp_server.sh         # MCP server startup script
│   │   └── __pycache__/                # Python cache directory
│   ├── synthesis_server.py             # Synthesis server (port 18001)
│   ├── placement_server.py             # Placement server (port 18002)
│   ├── cts_server.py                   # Clock tree synthesis server (port 18003)
│   ├── routing_server.py               # Routing server (port 18004)
│   ├── base_server.py                  # Base server class (BaseServer)
│   ├── base_executor.py                # Base executor class
│   └── __init__.py                     # Package initialization
├── mcp_agent_client.py              # AI agent client
├── run_server.py                    # Server management script with port cleanup
├── scripts/                         # TCL template scripts
└── codebleu_tcl/                    # CodeBLEU evaluation

test_mcp_server.py                   # MCP server test script
MCP_IMPLEMENTATION.md                # This document
```

## Available MCP Tools (4-Server Architecture)

### 1. synthesis
- **Function**: Complete RTL-to-gate synthesis using Synopsys Design Compiler
- **Description**: Performs the complete synthesis flow including environment setup, RTL analysis, and gate-level compilation. Transforms RTL design into optimized gate-level netlist while meeting timing, area, and power constraints.
- **Parameters**: 
  - `design` (str, required): Design name (e.g., "b14", "leon2", "des")
  - `tech` (str, optional): Technology library (default: "FreePDK45")
  - `version_idx` (int, optional): Configuration version index (default: 0)
  - `force` (bool, optional): Force re-run even if output exists (default: False)
- **Returns**: JSON string with synthesis results, timing/area/power reports
- **Server**: SynthesisServer (port 18001)
- **Prerequisites**: 
  - Design RTL files must exist in designs/{design}/rtl/
  - Technology library must be available
  - Synthesis configuration files must be present

### 2. placement
- **Function**: Complete placement flow including floorplanning, power planning, and standard cell placement
- **Description**: Performs chip floorplanning and I/O placement, power grid planning and power mesh creation, and standard cell placement optimization using Cadence Innovus.
- **Parameters**:
  - `design` (str, required): Design name
  - `top_module` (str, required): Top-level module name from RTL design
  - `tech` (str, optional): Technology library (default: "FreePDK45")
  - `syn_ver` (str, optional): Synthesis version string (auto-detected if empty)
  - `g_idx` (int, optional): Global configuration index (default: 0)
  - `p_idx` (int, optional): Placement parameter index (default: 0)
  - `force` (bool, optional): Force re-run even if output exists (default: False)
  - `restore_enc` (str, optional): Path to restore checkpoint file
- **Returns**: JSON string with placement results, placement files, and checkpoint data
- **Server**: PlacementServer (port 18002)
- **Prerequisites**: 
  - synthesis must be completed successfully
  - Top module must be correctly identified
  - Implementation configuration files must be available

### 3. clock_tree_synthesis
- **Function**: Clock distribution network synthesis and optimization
- **Description**: Synthesizes the clock distribution network by inserting clock buffers and optimizing clock tree topology. Ensures balanced clock distribution while meeting clock skew and transition time requirements.
- **Parameters**:
  - `design` (str, required): Design name
  - `top_module` (str, required): Top-level module name from RTL design
  - `restore_enc` (str, required): Path to placement checkpoint file
  - `tech` (str, optional): Technology library (default: "FreePDK45")
  - `impl_ver` (str, optional): Implementation version (auto-generated if empty)
  - `force` (bool, optional): Force re-run even if output exists (default: False)
  - `g_idx` (int, optional): Global configuration index (default: 0)
  - `c_idx` (int, optional): Clock tree parameter index (default: 0)
- **Returns**: JSON string with clock tree synthesis results, clock tree files, and checkpoint data
- **Server**: CtsServer (port 18003)
- **Prerequisites**: 
  - placement must be completed successfully
  - Placement checkpoint file must be valid
  - Clock tree synthesis configuration must be available

### 4. routing
- **Function**: Complete routing and save flow including signal routing and final design save
- **Description**: Performs global and detailed signal routing, post-route optimization, final design verification, and output file generation. Routes all signal nets between placed cells while meeting timing requirements and generates all required output files including GDSII, DEF, netlist, and reports.
- **Parameters**:
  - `design` (str, required): Design name
  - `top_module` (str, required): Top-level module name from RTL design
  - `restore_enc` (str, required): Path to CTS checkpoint file
  - `tech` (str, optional): Technology library (default: "FreePDK45")
  - `impl_ver` (str, optional): Implementation version (auto-generated if empty)
  - `force` (bool, optional): Force re-run even if output exists (default: False)
  - `g_idx` (int, optional): Global configuration index (default: 0)
  - `p_idx` (int, optional): Placement parameter index (default: 0)
  - `r_idx` (int, optional): Routing parameter index (default: 0)
  - `archive` (bool, optional): Create archive of final results (default: True)
- **Returns**: JSON string with routing results, output files, and archive data
- **Server**: RoutingServer (port 18004)
- **Prerequisites**: 
  - clock_tree_synthesis must be completed successfully
  - CTS checkpoint file must be valid
  - Routing configuration must be available

### 5. complete_eda_flow
- **Function**: Execute the complete EDA flow from RTL to GDSII using 4-server architecture
- **Description**: Executes the complete digital design implementation flow automatically with proper checkpoint handling between stages.
- **Parameters**:
  - `design` (str, required): Design name
  - `top_module` (str, required): Top-level module name from RTL design
  - `tech` (str, optional): Technology library (default: "FreePDK45")
  - `force` (bool, optional): Force re-run even if output exists (default: False)
- **Returns**: JSON string with complete flow results and step-by-step status
- **Flow Steps**: 
  1. RTL synthesis (synthesis server)
  2. Placement: floorplan + power + placement (placement server)
  3. Clock tree synthesis (CTS server)
  4. Routing and save: routing + save (routing server)
- **Prerequisites**: 
  - Design RTL files must exist in designs/{design}/rtl/
  - Technology library must be available
  - All configuration files must be present

## Server Configuration

### EDA Server Ports (Unified 18001-18004)
```python
EDA_SERVERS = {
    "synthesis": {"port": 18001, "endpoint": "run"},
    "placement": {"port": 18002, "endpoint": "run"},
    "cts": {"port": 18003, "endpoint": "run"},
    "routing": {"port": 18004, "endpoint": "run"},
}
```

### Legacy Tool Mapping (Backward Compatibility)
```python
LEGACY_TOOL_MAPPING = {
    "synth_setup": "synthesis",
    "synth_compile": "synthesis", 
    "synth": "synthesis",
    "floorplan": "placement",
    "powerplan": "placement",
    "unified_placement": "placement",
    "route": "routing",
    "save": "routing",
    "unified_route_save": "routing",
}
```

## Installation and Configuration

### 1. Install Dependencies
```bash
# Core MCP dependencies
pip install mcp fastmcp requests

# Or install all project dependencies
pip install -r requirements.txt
```

### 2. Start EDA Servers
```bash
# Option 1: Start all servers with automatic port cleanup
python3 src/run_server.py --server all

# Option 2: Start individual servers
python3 src/run_server.py --server synthesis  # Port 18001
python3 src/run_server.py --server placement  # Port 18002
python3 src/run_server.py --server cts        # Port 18003
python3 src/run_server.py --server routing    # Port 18004

# Option 3: Direct server startup
python3 src/server/synthesis_server.py --port 18001 &
python3 src/server/placement_server.py --port 18002 &
python3 src/server/cts_server.py --port 18003 &
python3 src/server/routing_server.py --port 18004 &
```

### 3. Start MCP Server
```bash
# Option 1: Using startup script
cd src/server/mcp
./start_mcp_server.sh

# Option 2: Direct startup
cd src/server/mcp
python3 mcp_eda_server.py
```

### 4. Configure Claude Desktop
Add the following configuration to your Claude Desktop configuration file (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mcp-eda-server": {
      "command": "ssh",
      "args": [
        "yl996@hl279-cmp-00.egr.duke.edu",
        "cd /home/yl996/proj/mcp-eda-example/src/server/mcp && python3 mcp_eda_server.py"
      ],
      "env": {},
      "description": "MCP EDA Server with 4-server architecture (synthesis, placement, cts, routing)"
    }
  }
}
```

### 5. Test MCP Server
```bash
# Test MCP server functionality
cd src/server/mcp
python3 test_mcp_server.py

# Check server health
curl http://localhost:18001/docs  # Synthesis
curl http://localhost:18002/docs  # Placement
curl http://localhost:18003/docs  # CTS
curl http://localhost:18004/docs  # Routing
```

## Usage Examples

### Using Claude Desktop (Natural Language)
In Claude Desktop, you can directly use natural language to call the tools:

```
Please run the complete EDA flow for design "des" with top module "des3"
```

```
Run synthesis for design "b14" and then placement with top module "b14"
```

```
Execute clock tree synthesis for design "leon2" using the checkpoint from placement
```

### Direct MCP Tool Calls
```python
import asyncio
import json

# Example tool calls (as they would be made by Claude Desktop)

# 1. Run synthesis
synthesis_result = await synthesis(
    design="des",
    tech="FreePDK45",
    version_idx=0,
    force=False
)

# 2. Run placement
placement_result = await placement(
    design="des",
    top_module="des3",
    tech="FreePDK45",
    syn_ver="",  # Auto-detected
    g_idx=0,
    p_idx=0,
    force=False,
    restore_enc=""
)

# 3. Run complete flow
complete_flow_result = await complete_eda_flow(
    design="des",
    top_module="des3",
    tech="FreePDK45",
    force=False
)
```

## Technical Implementation Details

### 1. MCP Server Architecture
- **FastMCP Framework**: Uses the official FastMCP framework for robust MCP protocol implementation
- **Async/Await Pattern**: Full asyncio support for non-blocking operations
- **Type Safety**: Complete parameter type definitions with Pydantic-style validation
- **Error Handling**: Comprehensive error handling with detailed error messages

### 2. Server Communication
- **HTTP-based Communication**: All EDA servers expose REST APIs
- **JSON Protocol**: Standardized JSON payload format for all tool calls
- **Timeout Management**: 300-second timeout for long-running EDA operations
- **Connection Pooling**: Efficient connection reuse for better performance

### 3. Checkpoint Management
- **Automatic Version Detection**: Auto-detection of synthesis versions and implementation versions
- **Checkpoint Chaining**: Proper checkpoint file handling between EDA stages
- **Path Resolution**: Intelligent restore_enc path detection and management
- **State Validation**: Checkpoint file validation before stage execution

### 4. Legacy Compatibility Layer
- **Backward Compatibility**: Full support for legacy tool names through mapping
- **Graceful Migration**: Smooth transition from old to new tool names
- **Warning System**: Informative warnings when legacy tools are used
- **Documentation Updates**: Clear migration path documentation

## Advanced Features

### 1. Intelligent Auto-Detection
```python
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
```

### 2. Implementation Version Generation
```python
def make_implementation_version(syn_ver: str, g_idx: int = 0, p_idx: int = 0) -> str:
    """Generate implementation version name from synthesis version and indices"""
    return f"{syn_ver}__g{g_idx}_p{p_idx}"
```

### 3. EDA Server Communication
```python
def call_eda_server(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call EDA microservice with specified payload"""
    # Handle legacy tool names
    if tool_name in LEGACY_TOOL_MAPPING:
        actual_tool = LEGACY_TOOL_MAPPING[tool_name]
        print(f"[MCP] Legacy tool '{tool_name}' mapped to '{actual_tool}'")
        tool_name = actual_tool
    
    if tool_name not in EDA_SERVERS:
        return {"status": "error", "detail": f"Unknown tool: {tool_name}"}
    
    server_info = EDA_SERVERS[tool_name]
    url = f"http://localhost:{server_info['port']}/{server_info['endpoint']}"
    
    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"status": "error", "detail": f"Failed to call EDA server: {str(e)}"}
```

## Troubleshooting

### Common Issues

1. **MCP Server Connection Failures**
   ```bash
   # Check if MCP server is running
   cd src/server/mcp && python3 mcp_eda_server.py
   
   # Check if all 4 EDA servers are running
   python3 src/run_server.py --server all
   
   # Verify port availability
   netstat -tlnp | grep -E "(1800[1-4])"
   ```

2. **EDA Server Communication Errors**
   ```bash
   # Check server health
   curl http://localhost:18001/docs  # Synthesis
   curl http://localhost:18002/docs  # Placement
   curl http://localhost:18003/docs  # CTS
   curl http://localhost:18004/docs  # Routing
   
   # Check server processes
   ps aux | grep -E "(synthesis_server|placement_server|cts_server|routing_server)"
   ```

3. **Tool Call Failures**
   - Verify design files exist in `designs/{design}/rtl/`
   - Check configuration files in `config/` directory
   - Ensure proper checkpoint file paths for dependent stages
   - Verify synthesis completion before running placement

4. **Claude Desktop Integration Issues**
   - Verify `claude_desktop_config.json` configuration path
   - Check SSH connectivity to the server host
   - Ensure MCP server is accessible from Claude Desktop
   - Verify the working directory path in the configuration

### Debugging Methods

1. **Check All Services Status**
   ```bash
   # Check EDA servers
   for port in 18001 18002 18003 18004; do
     curl -s http://localhost:$port/docs >/dev/null && echo "Port $port: OK" || echo "Port $port: FAIL"
   done
   
   # Check MCP server
   cd src/server/mcp
   python3 -c "
   import sys
   sys.path.append('..')
   from mcp_eda_server import EDA_SERVERS
   print('EDA Servers:', list(EDA_SERVERS.keys()))
   "
   ```

2. **View Server Logs**
   ```bash
   # MCP server logs (stdout)
   cd src/server/mcp
   python3 mcp_eda_server.py
   
   # EDA server logs
   tail -f logs/synthesis/des_synthesis_*.log
   tail -f logs/placement/des_placement_*.log
   tail -f logs/cts/des_cts_*.log
   tail -f logs/routing/des_routing_*.log
   ```

3. **Test Individual Components**
   ```bash
   # Test direct server APIs
   curl -X POST http://localhost:18001/run \
     -H "Content-Type: application/json" \
     -d '{"design": "des", "tech": "FreePDK45"}'
   
   # Test MCP server compilation
   cd src/server/mcp
   python3 -c "
   import mcp_eda_server
   print('✓ MCP server imports OK')
   print('Available tools:', [f.__name__ for f in [
     mcp_eda_server.synthesis,
     mcp_eda_server.placement,
     mcp_eda_server.clock_tree_synthesis,
     mcp_eda_server.routing,
     mcp_eda_server.complete_eda_flow
   ]])
   "
   ```

4. **Check Dependencies**
   ```bash
   # Verify MCP installation
   python3 -c "import mcp.server.fastmcp; print('✓ FastMCP OK')"
   
   # Check all required packages
   python3 -c "import requests, json, pathlib; print('✓ All dependencies OK')"
   
   # Verify server classes
   python3 -c "
   import sys
   sys.path.append('src/server')
   from synthesis_server import SynthesisServer
   from placement_server import PlacementServer
   from cts_server import CtsServer
   from routing_server import RoutingServer
   print('✓ All server classes imported successfully')
   "
   ```

## Development Guide

### Adding New MCP Tools
1. Add new `@mcp.tool()` decorated function in `src/server/mcp/mcp_eda_server.py`:
   ```python
   @mcp.tool()
   async def new_tool_name(
       design: str,
       required_param: str,
       optional_param: str = "default"
   ) -> str:
       """
       Tool description with comprehensive docstring
       
       Args:
           design: Design name description
           required_param: Required parameter description
           optional_param: Optional parameter description
       
       Returns:
           JSON string containing tool results
       """
       payload = {
           "design": design, 
           "required_param": required_param,
           "optional_param": optional_param
       }
       result = call_eda_server("target_server", payload)
       return json.dumps(result, ensure_ascii=False, indent=2)
   ```

2. Update `EDA_SERVERS` mapping if targeting new server
3. Add to `LEGACY_TOOL_MAPPING` if replacing legacy tools
4. Update test scripts and documentation

### Modifying Existing Tools
1. Update the tool function parameters and logic in `mcp_eda_server.py`
2. Update corresponding server endpoint if needed
3. Test with MCP server compilation and functionality
4. Update documentation and examples

### Server Class Structure
All EDA servers inherit from the `BaseServer` class:
```python
from base_server import BaseServer

class NewServer(BaseServer):
    def __init__(self, default_port=18005):
        super().__init__(
            name="new_server",
            default_port=default_port
        )
    
    # Implement server-specific methods
```

## Performance Considerations

### 1. Port Management
- **Automatic Cleanup**: `run_server.py` includes automatic port cleanup using `lsof` and `kill`
- **Conflict Resolution**: Automatic termination of conflicting processes before server startup
- **Health Monitoring**: Built-in health checks and status monitoring

### 2. Memory Management
- **Checkpoint Efficiency**: Optimized checkpoint file handling and memory usage
- **Process Isolation**: Each EDA server runs in its own process space
- **Resource Cleanup**: Automatic cleanup of temporary files and processes

### 3. Scalability Features
- **Async Operations**: Non-blocking MCP tool execution
- **Connection Pooling**: Efficient HTTP connection reuse
- **Load Balancing**: Support for multiple server instances (future enhancement)

## Architecture Benefits

### Modern Unified Design
- **Simplified Architecture**: 4 unified servers with clear responsibilities
- **Reduced Complexity**: Fewer inter-service dependencies and communication overhead
- **Better Maintainability**: Consolidated functionality in logical groups
- **Enhanced Performance**: Optimized checkpoint handling and data flow

### Claude Desktop Integration
- **Natural Language Interface**: Direct integration for intuitive interaction
- **Context Awareness**: Intelligent parameter extraction and validation
- **Error Recovery**: Comprehensive error handling and user guidance
- **Session Management**: Persistent context across tool calls

### Production-Ready Features
- **Comprehensive Logging**: Detailed logs across all components with structured output
- **Health Monitoring**: Real-time service health checks and status reporting
- **Process Management**: Robust process lifecycle management with automatic cleanup
- **Legacy Compatibility**: Smooth migration path with backward compatibility

## Summary

This advanced MCP EDA implementation provides a modern, AI-powered framework for digital design automation:

### Key Achievements
- **Unified 4-Server Architecture**: Streamlined servers with ports 18001-18004
- **Complete EDA Flow Coverage**: From RTL to GDSII with intelligent checkpoint management
- **Claude Desktop Integration**: Natural language interaction for hardware design workflows
- **FastMCP Framework**: Modern, robust MCP protocol implementation
- **Production-Ready Deployment**: Process management, health monitoring, and comprehensive logging

### Impact
- **Improved Efficiency**: Reduced setup complexity and faster development cycles
- **Enhanced Usability**: Natural language interface lowers barriers to EDA tool usage
- **Better Maintainability**: Clean architecture with comprehensive documentation and testing
- **Scalable Design**: Extensible framework for adding new tools and capabilities

Through this implementation, hardware designers can leverage the power of AI and natural language processing to streamline their EDA workflows, significantly improving productivity and reducing the complexity of digital design implementation. The unified 4-server architecture with standardized ports (18001-18004) provides a robust foundation for scalable EDA automation.