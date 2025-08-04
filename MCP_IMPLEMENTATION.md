# MCP EDA Implementation Guide

## Overview

This project implements a comprehensive MCP (Model Context Protocol) EDA server and client system, providing a complete digital design flow from RTL to GDSII using a modern unified 4-server architecture. The implementation leverages Claude Desktop integration for natural language EDA tool interaction.

## Architecture Design

### Unified 4-Server Architecture
- **FastMCP Framework**: Uses the officially recommended FastMCP framework for robust MCP server development
- **Unified Microservices**: 4 consolidated servers handle complete EDA stages (synthesis, unified placement, CTS, unified route+save)
- **Tool-based Design**: Each major EDA flow is encapsulated as an independent MCP tool with comprehensive parameter handling
- **Legacy Compatibility**: Backward compatibility mapping for legacy tool names

### Client Architecture
- **Asynchronous Design**: Full asyncio support for non-blocking EDA operations
- **Type Safety**: Complete type annotations with comprehensive error handling
- **Clean API**: Intuitive tool calling interface with natural language support
- **Session Management**: User session context and parameter persistence

## File Structure

```
server/mcp/
├── mcp_eda_server.py           # Main MCP server (unified 4-server architecture)
├── claude_desktop_config.json  # Claude Desktop configuration
└── test_mcp_server.py          # MCP server test script

server/
├── synth_server.py             # Synthesis server (port 13333)
├── unified_placement_server.py # Unified placement server (port 13340)
├── cts_server.py               # Clock tree synthesis server (port 13338)
├── unified_route_save_server.py # Unified route+save server (port 13341)
├── synth_Executor.py           # Synthesis executor
├── unified_placement_Executor.py # Unified placement executor
├── cts_Executor.py             # CTS executor
└── unified_route_save_Executor.py # Unified route+save executor

mcp_agent_client.py             # AI-powered HTTP agent client
simple_mcp_client.py            # Simple MCP client for testing
restart_servers.sh              # Server management script
MCP_IMPLEMENTATION.md           # This document
```

## Available MCP Tools (Unified 4-Server Architecture)

### 1. synthesis
- **Function**: Complete RTL-to-gate synthesis (setup + compile)
- **Parameters**: 
  - `design` (str, required): Design name (e.g., "b14", "leon2", "des")
  - `tech` (str, optional): Technology library (default: "FreePDK45")
  - `version_idx` (int, optional): Configuration version index (default: 0)
  - `force` (bool, optional): Force re-run (default: False)
- **Returns**: JSON string with synthesis results, timing/area/power reports
- **Server**: synth_server.py (port 13333)

### 2. unified_placement
- **Function**: Unified placement flow (floorplan + powerplan + placement)
- **Parameters**:
  - `design` (str, required): Design name
  - `top_module` (str, required): Top-level module name
  - `tech` (str, optional): Technology library (default: "FreePDK45")
  - `syn_ver` (str, optional): Synthesis version (auto-detected if empty)
  - `g_idx` (int, optional): Global configuration index (default: 0)
  - `p_idx` (int, optional): Placement parameter index (default: 0)
  - `force` (bool, optional): Force re-run (default: False)
  - `restore_enc` (str, optional): Restore checkpoint file path
- **Returns**: JSON string with unified placement results and checkpoint data
- **Server**: unified_placement_server.py (port 13340)

### 3. clock_tree_synthesis
- **Function**: Clock distribution network synthesis
- **Parameters**:
  - `design` (str, required): Design name
  - `top_module` (str, required): Top-level module name
  - `restore_enc` (str, required): Placement checkpoint file path
  - `tech` (str, optional): Technology library (default: "FreePDK45")
  - `impl_ver` (str, optional): Implementation version (auto-generated if empty)
  - `force` (bool, optional): Force re-run (default: False)
  - `g_idx` (int, optional): Global configuration index (default: 0)
  - `c_idx` (int, optional): Clock tree parameter index (default: 0)
- **Returns**: JSON string with CTS results and checkpoint data
- **Server**: cts_server.py (port 13338)

### 4. unified_route_save
- **Function**: Unified routing and save flow (routing + final save)
- **Parameters**:
  - `design` (str, required): Design name
  - `top_module` (str, required): Top-level module name
  - `restore_enc` (str, required): CTS checkpoint file path
  - `tech` (str, optional): Technology library (default: "FreePDK45")
  - `impl_ver` (str, optional): Implementation version (auto-generated if empty)
  - `force` (bool, optional): Force re-run (default: False)
  - `g_idx` (int, optional): Global configuration index (default: 0)
  - `p_idx` (int, optional): Placement parameter index (default: 0)
  - `r_idx` (int, optional): Routing parameter index (default: 0)
  - `archive` (bool, optional): Create archive of results (default: True)
- **Returns**: JSON string with routing results and final deliverables
- **Server**: unified_route_save_server.py (port 13341)

### 5. complete_eda_flow
- **Function**: Complete RTL to GDSII flow using unified 4-server architecture
- **Parameters**:
  - `design` (str, required): Design name
  - `top_module` (str, required): Top-level module name
  - `tech` (str, optional): Technology library (default: "FreePDK45")
  - `force` (bool, optional): Force re-run (default: False)
- **Returns**: JSON string with complete flow results and step-by-step status
- **Flow**: Automatically executes all 4 stages with proper checkpoint handling

## Installation and Configuration

### 1. Install Dependencies
```bash
# Core MCP dependencies
pip install mcp>=1.0.0 fastmcp requests

# Or install all project dependencies
pip install -r requirements.txt
```

### 2. Start EDA Servers
```bash
# Option 1: Use restart script (recommended)
./restart_servers.sh

# Option 2: Manual startup
python3 server/synth_server.py &
python3 server/unified_placement_server.py &
python3 server/cts_server.py &
python3 server/unified_route_save_server.py &
```

### 3. Start MCP Server
```bash
cd server/mcp
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
        "cd /home/yl996/proj/mcp-eda-example/server/mcp && python3 mcp_eda_server.py"
      ],
      "env": {},
      "description": "MCP EDA Server with 4-server architecture (synthesis, unified_placement, cts, unified_route_save)"
    }
  }
}
```

### 5. Test MCP Server
```bash
# Test MCP server functionality
cd server/mcp
python3 test_mcp_server.py


### 6. Start AI Agent (Optional)
```bash
# Start the intelligent HTTP agent client
python3 mcp_agent_client.py
```

## Usage Examples

### Using MCP Client API
```python
import asyncio
from simple_mcp_client import SimpleMCPClient

async def main():
    client = SimpleMCPClient()
    
    # Connect to MCP server
    await client.connect()
    
    # Run complete synthesis (setup + compile)
    result = await client.call_tool("synthesis", {
        "design": "des",
        "tech": "FreePDK45",
        "version_idx": 0,
        "force": False
    })
    print("Synthesis result:", result)
    
    # Run unified placement (floorplan + power + placement)
    result = await client.call_tool("unified_placement", {
        "design": "des",
        "top_module": "des3",
        "tech": "FreePDK45",
        "syn_ver": "cpV1_clkP1_drcV1"
    })
    print("Unified placement result:", result)
    
    # Run complete EDA flow
    result = await client.call_tool("complete_eda_flow", {
        "design": "des",
        "top_module": "des3",
        "tech": "FreePDK45",
        "force": False
    })
    print("Complete flow result:", result)
    
    # Disconnect
    await client.disconnect()

asyncio.run(main())
```

### Using Claude Desktop
In Claude Desktop, you can directly use natural language to call the unified tools:

```
Please run the complete EDA flow for design "des" with top module "des3" using the unified 4-server architecture
```

```
Run synthesis for design "b14" and then unified placement with top module "b14"
```

```
Execute clock tree synthesis for design "leon2" using the checkpoint from unified placement
```

### Using HTTP Agent Client
```bash
# Start the AI agent
python3 mcp_agent_client.py

# In another terminal, call the agent
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"user_query":"Run complete EDA flow for design des with top module des3"}'
```

## Technical Features

### 1. Unified 4-Server Architecture
- **Consolidated Services**: 4 unified servers replace 8 individual stage servers
- **Complete Flows**: Each server handles complete sub-flows (e.g., unified_placement = floorplan + power + placement)
- **Efficient Communication**: Reduced inter-service communication overhead
- **Checkpoint Management**: Automatic checkpoint file handling between stages

### 2. Advanced MCP Implementation
- **FastMCP Framework**: Uses officially recommended FastMCP for robust server development
- **Legacy Compatibility**: Backward compatibility mapping for legacy tool names
- **Type Safety**: Complete parameter type definitions and comprehensive validation
- **Error Handling**: Detailed error messages with context and debugging information

### 3. AI-Powered Orchestration
- **Natural Language Processing**: GPT-4 integration for intelligent tool selection
- **Parameter Extraction**: Automatic parameter extraction from natural language queries
- **Strategy Recommendation**: AI-driven optimization strategy suggestions
- **Session Management**: User session context and parameter persistence

### 4. Enhanced Features
- **Auto-detection**: Automatically detect synthesis versions and implementation versions
- **Multi-Stage Flows**: Support for `pnr` and `full_flow` abstractions
- **Intelligent Routing**: Automatic restore_enc path detection and management
- **Comprehensive Logging**: Detailed logging across all servers and stages

### 5. Integration Capabilities
- **Claude Desktop**: Direct integration with Claude Desktop for natural language interaction
- **HTTP API**: RESTful API through mcp_agent_client.py for programmatic access
- **Health Monitoring**: Comprehensive health checks and monitoring tools

## Troubleshooting

### Common Issues

1. **MCP Server Connection Failures**
   - Ensure MCP server is running: `cd server/mcp && python3 mcp_eda_server.py`
   - Check if all 4 EDA servers are running: `./restart_servers.sh`
   - Verify port availability: `netstat -tlnp | grep -E "(13333|13338|13340|13341)"`

2. **EDA Server Communication Errors**
   - Verify server processes: `ps aux | grep -E "(synth_server|unified_placement_server|cts_server|unified_route_save_server)"`
   - Check server logs in `logs/` directory

3. **Tool Call Failures**
   - Verify design files exist in `designs/{design}/rtl/`
   - Check configuration files in `config/` directory
   - Ensure proper checkpoint file paths for dependent stages

4. **Claude Desktop Integration Issues**
   - Verify `claude_desktop_config.json` configuration
   - Check SSH connectivity to the server host
   - Ensure MCP server is accessible from Claude Desktop

### Debugging Methods

1. **Check All Services Status**
   ```bash
   
   # Check MCP server
   cd server/mcp
   python3 test_mcp_server.py
   ```

2. **View Server Logs**
   ```bash
   # MCP server logs
   cd server/mcp
   python3 mcp_eda_server.py
   
   # EDA server logs
   tail -f logs/synthesis/des_synthesis_*.log
   tail -f logs/unified_placement/des_unified_placement_*.log
   tail -f logs/cts/des_cts_*.log
   tail -f logs/unified_route_save/des_unified_route_save_*.log
   ```

3. **Test Individual Components**
   ```bash
   # Test MCP tools
   python3 -c "
   import asyncio
   from simple_mcp_client import SimpleMCPClient
   
   async def test():
       client = SimpleMCPClient()
       await client.connect()
       tools = await client.list_tools()
       print('Available tools:', [t['name'] for t in tools])
       await client.disconnect()
   
   asyncio.run(test())
   "
   
   # Test direct server APIs
   curl -X GET http://localhost:13333/docs
   curl -X GET http://localhost:13340/docs
   curl -X GET http://localhost:13338/docs
   curl -X GET http://localhost:13341/docs
   ```

4. **Check Dependencies**
   ```bash
   # Verify MCP installation
   python3 -c "import mcp.server.fastmcp; print('FastMCP OK')"
   
   # Check all required packages
   pip check
   
   # Verify EDA tools (if available)
   which dc_shell
   which innovus
   ```

## Development Guide

### Adding New MCP Tools
1. Add new `@mcp.tool()` decorated function in `server/mcp/mcp_eda_server.py`
   ```python
   @mcp.tool()
   async def new_tool_name(
       design: str,
       required_param: str,
       optional_param: str = "default"
   ) -> str:
       """Tool description with comprehensive docstring"""
       payload = {"design": design, "required_param": required_param}
       result = call_eda_server("target_server", payload)
       return json.dumps(result, ensure_ascii=False, indent=2)
   ```

2. Update `EDA_SERVERS` mapping if targeting new server
3. Add to `LEGACY_TOOL_MAPPING` if replacing legacy tools
4. Update test scripts and documentation

### Modifying Existing Tools
1. Update the tool function parameters and logic in `mcp_eda_server.py`
2. Update corresponding server endpoint if needed
3. Test with `python3 server/mcp/test_mcp_server.py`
4. Update documentation and examples

### Adding New EDA Servers
1. Create new server file (e.g., `server/new_server.py`)
2. Add corresponding executor (e.g., `server/new_Executor.py`)
3. Update `EDA_SERVERS` configuration in `mcp_eda_server.py`
4. Update `restart_servers.sh` script

### Testing New Features
1. **Unit Testing**: Test individual MCP tools
   ```bash
   cd server/mcp
   python3 test_mcp_server.py
   ```

3. **End-to-End Testing**: Test complete flows
   ```bash
   python3 mcp_agent_client.py  # Start agent
   # Test via HTTP API or Claude Desktop
   ```

### Extending AI Agent Capabilities
1. Update `TOOLS` mapping in `mcp_agent_client.py`
2. Add new flow definitions in `flow_definitions`
3. Update parameter extraction and validation logic
4. Test natural language understanding with GPT-4

## Architecture Benefits

### Modern Unified Design
- **Simplified Architecture**: 4 unified servers vs. 8 individual stage servers
- **Reduced Complexity**: Fewer inter-service dependencies and communication overhead
- **Better Maintainability**: Consolidated functionality in logical groups
- **Enhanced Performance**: Optimized checkpoint handling and data flow

### AI-First Approach
- **Natural Language Interface**: Direct Claude Desktop integration for intuitive interaction
- **Intelligent Orchestration**: GPT-4 powered tool selection and parameter extraction
- **Context Awareness**: Session management and parameter persistence
- **Error Recovery**: Intelligent error handling and user guidance

### Production-Ready Features
- **Comprehensive Logging**: Detailed logs across all components
- **Health Monitoring**: Real-time service health checks and monitoring
- **Legacy Compatibility**: Smooth migration path from older implementations

## Summary

This advanced MCP EDA implementation provides a modern, AI-powered framework for digital design automation:

### Key Achievements
- **Unified 4-Server Architecture**: Streamlined from 8 individual servers to 4 consolidated services
- **Complete EDA Flow Coverage**: From RTL to GDSII with intelligent checkpoint management
- **Claude Desktop Integration**: Natural language interaction for hardware design workflows
- **AI-Powered Orchestration**: GPT-4 integration for intelligent tool selection and parameter extraction

### Impact
- **Improved Efficiency**: Reduced setup complexity and faster development cycles
- **Enhanced Usability**: Natural language interface lowers barriers to EDA tool usage
- **Better Maintainability**: Clean architecture and comprehensive documentation
- **Scalable Design**: Extensible framework for adding new tools and capabilities

Through this implementation, hardware designers can leverage the power of AI and natural language processing to streamline their EDA workflows, significantly improving productivity and reducing the complexity of digital design implementation. 
