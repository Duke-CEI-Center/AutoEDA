# Unified EDA Servers

This directory contains individual server implementations for different EDA workflows, all using the unified executor:

## Server Files

- **`synthesis_server.py`** - Synthesis server (port 18001)
- **`placement_server.py`** - Placement server (port 18002)  
- **`cts_server.py`** - Clock Tree Synthesis server (port 18003)
- **`routing_server.py`** - Routing server (port 18004)

## Unified Executor

All servers now use the **`unified_executor.py`** which combines all EDA tool execution into a single script:

- **Synthesis**: Uses `dc_shell` for synthesis
- **Placement**: Uses `innovus` for floorplan + powerplan + placement
- **CTS**: Uses `innovus` for clock tree synthesis
- **Routing**: Uses `innovus` for routing + final save

## Usage

### Individual Server Files

Each server can be run directly:

```bash
# Synthesis server
python unified_server/synthesis_server.py --port 18001

# Placement server
python unified_server/placement_server.py --port 18002

# CTS server
python unified_server/cts_server.py --port 18003

# Routing server
python unified_server/routing_server.py --port 18004
```

### Using the Launcher Script

Or use the main launcher script from the project root:

```bash
# Synthesis server
python run_server.py --server synthesis --port 18001

# Placement server
python run_server.py --server placement --port 18002

# CTS server
python run_server.py --server cts --port 18003

# Routing server
python run_server.py --server routing --port 18004
```

## API Endpoints

All servers provide the same REST API endpoint:

```
POST /run
```

### Example Requests

```bash
# Synthesis
curl -X POST http://localhost:18001/run \
  -H "Content-Type: application/json" \
  -d '{"design": "des", "tech": "FreePDK45"}'

# Placement
curl -X POST http://localhost:18002/run \
  -H "Content-Type: application/json" \
  -d '{"design": "des", "tech": "FreePDK45"}'

# CTS
curl -X POST http://localhost:18003/run \
  -H "Content-Type: application/json" \
  -d '{"design": "des", "tech": "FreePDK45"}'

# Routing
curl -X POST http://localhost:18004/run \
  -H "Content-Type: application/json" \
  -d '{"design": "des", "tech": "FreePDK45"}'
```

### Example Response

```json
{
  "status": "execution_completed",
  "log_path": "/path/to/log/file",
  "reports": {
    "timing.rpt": "/path/to/timing.rpt",
    "area.rpt": "/path/to/area.rpt"
  },
  "tcl_path": "/path/to/generated.tcl"
}
```

## Environment Variables

You can use these env variables to customize your server:

- `UNIFIED_SYNTHESIS_PORT` (default: 18001)
- `UNIFIED_PLACEMENT_PORT` (default: 18002)
- `UNIFIED_CTS_PORT` (default: 18003)
- `UNIFIED_ROUTING_PORT` (default: 18004)

