# MCP EDA Quick Start Guide

## Prerequisites

Before starting, ensure you have the following installed:

- **Python 3.9+**
- **Synopsys Design Compiler** (for synthesis)
- **Cadence Innovus** (for physical implementation)
- **FreePDK45** technology library (included)
- **OpenAI API Key** (for GPT-4 integration)

## Step 1: Environment Setup

### 1.1 Clone and Setup Repository

```bash
# Clone the repository
git clone https://github.com/your-org/mcp-eda-example.git
cd mcp-eda-example

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 1.2 Configure Environment Variables

Create a `.env` file in the project root:

```bash
# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Server Configuration (optional)
MCP_SERVER_HOST=http://localhost
LOG_ROOT=./logs

# EDA Tool Paths (adjust to your installation)
SYNOPSYS_ROOT=/opt/synopsys
CADENCE_ROOT=/opt/cadence
```

### 1.3 Verify EDA Tools

```bash
# Check Design Compiler
dc_shell -version

# Check Innovus
innovus -version

# Check license servers
lmstat -a

# Verify FreePDK45 library
ls libraries/FreePDK45/
```

## Step 2: Start the Services

### 2.1 Start All Microservices

```bash
# Start all four microservices
python run_server.py
```

This script starts:
- **Synthesis Service** (port 13333)
- **Unified Placement Service** (port 13340) - includes floorplan, powerplan, and placement
- **CTS Service** (port 13338)
- **Unified Route & Save Service** (port 13341) - includes routing and final save

**Alternative: Start servers individually**

```bash
# Start each service individually
python3 server/synth_server.py --port 13333 &
python3 server/unified_placement_server.py --port 13340 &
python3 server/cts_server.py --port 13338 &
python3 server/unified_route_save_server.py --port 13341 &
```

### 2.2 Start AI Agent Client

```bash
# Start the intelligent agent (GPT-4 powered)
python3 mcp_agent_client.py

# Or using uvicorn for production
uvicorn mcp_agent_client:app --host 0.0.0.0 --port 8000
```

### 2.3 Verify Services are Running

```bash
# Check if all ports are listening
netstat -tlnp | grep -E "(8000|13333|13338|13340|13341)"

# Expected output:
# tcp6       0      0 :::8000     :::*        LISTEN      [PID]/python3  (Agent)
# tcp6       0      0 :::13333    :::*        LISTEN      [PID]/python3  (Synthesis)
# tcp6       0      0 :::13338    :::*        LISTEN      [PID]/python3  (CTS)
# tcp6       0      0 :::13340    :::*        LISTEN      [PID]/python3  (Placement)
# tcp6       0      0 :::13341    :::*        LISTEN      [PID]/python3  (Route & Save)

# Check service health and API documentation
curl http://localhost:13333/docs  # Synthesis API docs
curl http://localhost:13340/docs  # Placement API docs
curl http://localhost:13338/docs  # CTS API docs
curl http://localhost:13341/docs  # Route & Save API docs
```

## Step 3: Your First Design

### 3.1 Using Natural Language Interface (AI Agent)

The easiest way to run designs is through the AI-powered natural language interface:

```bash
# Test synthesis for a design
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"user_query":"Run synthesis for design aes with high performance", "session_id":"demo"}'
```

**Expected Response:**
```json
{
  "tool_called": "synth",
  "tool_input": {
    "design": "aes",
    "tech": "FreePDK45",
    "clk_period": 5.0,
    "force": false,
    "syn_version": "cpV1_clkP1_drcV1"
  },
  "tool_output": {
    "status": "ok",
    "log_path": "/home/yl996/proj/mcp-eda-example/logs/synthesis/aes_synthesis_20241201_143022.log",
    "reports": {...},
    "tcl_path": "/home/yl996/proj/mcp-eda-example/result/aes/FreePDK45/complete_synthesis.tcl"
  },
  "ai_reasoning": "Selected synthesis with performance optimization strategy",
  "suggestions": ["Consider running placement after synthesis completion"]
}
```

### 3.2 Complete RTL-to-GDSII Flow

Run a complete design flow using natural language:

```bash
# Complete flow for AES design
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"user_query":"Run complete full_flow for design aes with performance optimization", "session_id":"demo"}'
```

This will automatically execute:
1. **Synthesis** - RTL to gate-level netlist
2. **Unified Placement** - Floorplan + Powerplan + Placement
3. **CTS** - Clock tree synthesis and optimization
4. **Unified Route & Save** - Global/detail routing + final GDS generation

### 3.3 Multi-Stage Flow Control

You can also run specific flow stages:

```bash
# Just the physical design flow (P&R)
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"user_query":"Run pnr flow for design aes using synthesis version cpV1_clkP1_drcV1_20241201_143022", "session_id":"demo"}'

# Individual stages
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"user_query":"Run placement for design aes with target utilization 0.8", "session_id":"demo"}'
```

### 3.4 Session Management

The AI agent remembers your previous parameters and preferences:

```bash
# First request - specify full parameters
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"user_query":"Run synthesis for design aes with 500MHz clock", "session_id":"my_session"}'

# Follow-up request - agent remembers design and parameters
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"user_query":"Now run placement with high utilization", "session_id":"my_session"}'

# Check session history
curl -X GET http://localhost:8000/session/my_session/history
```

### 3.5 Strategy-Based Optimization

The system supports different optimization strategies:

```bash
# Fast flow (for quick verification)
curl -X POST http://localhost:8000/agent \
  -d '{"user_query":"Run fast synthesis for design aes", "session_id":"demo"}'

# Performance optimization
curl -X POST http://localhost:8000/agent \
  -d '{"user_query":"Run high performance full_flow for design aes", "session_id":"demo"}'

# Power optimization
curl -X POST http://localhost:8000/agent \
  -d '{"user_query":"Run low power placement for design aes", "session_id":"demo"}'

# Area optimization
curl -X POST http://localhost:8000/agent \
  -d '{"user_query":"Run small area routing for design aes", "session_id":"demo"}'
```

## Step 4: Direct Service API Usage

### 4.1 Synthesis Service (Port 13333)

```bash
curl -X POST http://localhost:13333/run \
  -H "Content-Type: application/json" \
  -d '{
    "design": "aes",
    "tech": "FreePDK45",
    "clk_period": 5.0,
    "syn_version": "cpV1_clkP1_drcV1",
    "force": true
  }'
```

### 4.2 Unified Placement Service (Port 13340)

```bash
curl -X POST http://localhost:13340/run \
  -H "Content-Type: application/json" \
  -d '{
    "design": "aes",
    "tech": "FreePDK45",
    "syn_ver": "cpV1_clkP1_drcV1_20241201_143022",
    "top_module": "aes_cipher_top",
    "target_util": 0.8,
    "ASPECT_RATIO": 1.0,
    "force": true
  }'
```

### 4.3 CTS Service (Port 13338)

```bash
curl -X POST http://localhost:13338/run \
  -H "Content-Type: application/json" \
  -d '{
    "design": "aes",
    "tech": "FreePDK45",
    "impl_ver": "cpV1_clkP1_drcV1_20241201_143022__g0_p0",
    "top_module": "aes_cipher_top",
    "restore_enc": "/path/to/placement.enc.dat",
    "force": true
  }'
```

### 4.4 Unified Route & Save Service (Port 13341)

```bash
curl -X POST http://localhost:13341/run \
  -H "Content-Type: application/json" \
  -d '{
    "design": "aes",
    "tech": "FreePDK45",
    "impl_ver": "cpV1_clkP1_drcV1_20241201_143022__g0_p0",
    "top_module": "aes_cipher_top",
    "restore_enc": "/path/to/cts.enc.dat",
    "archive": true,
    "force": true
  }'
```

## Step 5: Experimental Framework

### 5.1 Running CodeBLEU Evaluation Experiments

The project includes a comprehensive experimental framework for evaluating TCL generation quality:

```bash
# Navigate to experiment directory
cd exp_v1/experiment

# Run complete experiment for specific designs
python3 run_experiment.py --designs aes,des --methods baseline1,baseline2,ours

# Run evaluation on existing results
python3 evaluate/tcl_evaluator.py --results_dir results --timestamp 20241201_143022 --summary

# Clean previous results and run fresh
python3 run_experiment.py --clean --full
```

### 5.2 Evaluation Methods

The framework compares three TCL generation approaches:

1. **Baseline1**: Simple template-based generation
2. **Baseline2**: Enhanced template with parameter optimization
3. **Ours**: AI-powered agent with GPT-4 integration

### 5.3 Viewing Results

```bash
# Check generation results
ls results/
ls results/baseline1/
ls results/ours/

# Check evaluation results
ls evaluation_results/
cat evaluation_results/latest/tcl_codebleu_evaluation.json

# View summary statistics
python3 evaluate/tcl_evaluator.py --results_dir results --summary
```

### 5.4 Evaluation Metrics

The framework uses CodeBLEU metrics:
- **CodeBLEU Score**: Overall semantic similarity
- **Syntax Match**: TCL syntax correctness
- **Dataflow Analysis**: Logic flow preservation
- **N-gram Matching**: Token-level similarity

## Step 6: Testing and Validation

### 6.1 Service Health Checks

```bash
# Check all services are responsive
curl http://localhost:13333/docs  # Synthesis service
curl http://localhost:13340/docs  # Unified placement service
curl http://localhost:13338/docs  # CTS service
curl http://localhost:13341/docs  # Route & save service
curl http://localhost:8000/docs   # AI agent

# Check agent functionality
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"user_query":"test connection", "session_id":"test"}'
```

### 6.2 Test Different Designs

Available designs in the system:

```bash
# List available designs
ls designs/

# Test with AES design
curl -X POST http://localhost:8000/agent \
  -d '{"user_query":"Run synthesis for design aes", "session_id":"test"}'

# Test with DES design  
curl -X POST http://localhost:8000/agent \
  -d '{"user_query":"Run synthesis for design des", "session_id":"test"}'

# Test with B14 benchmark
curl -X POST http://localhost:8000/agent \
  -d '{"user_query":"Run synthesis for design b14", "session_id":"test"}'
```

## Step 7: Working with Different Designs

### 7.1 Design Configuration

Each design has a configuration file that defines key parameters:

```bash
# Check AES configuration
cat designs/aes/config.tcl

# Check DES configuration  
cat designs/des/config.tcl

# Check B14 configuration (VHDL design)
cat designs/b14/config.tcl
```

### 7.2 Design-Specific Parameters

Different designs may require different parameters:

```bash
# AES design with specific clock frequency
curl -X POST http://localhost:8000/agent \
  -d '{"user_query":"Run synthesis for design aes with 1GHz clock frequency", "session_id":"demo"}'

# DES design with power optimization
curl -X POST http://localhost:8000/agent \
  -d '{"user_query":"Run low power full_flow for design des", "session_id":"demo"}'

# B14 design (VHDL) with area optimization
curl -X POST http://localhost:8000/agent \
  -d '{"user_query":"Run small area synthesis for design b14", "session_id":"demo"}'
```

### 7.3 Adding New Designs

To add a new design:

1. Create design directory structure:
```bash
mkdir -p designs/your_design/rtl
mkdir -p designs/your_design/FreePDK45/{synthesis,implementation}
```

2. Add RTL files to `designs/your_design/rtl/`

3. Create configuration file `designs/your_design/config.tcl`:
```tcl
set TOP_NAME "your_module_name"
set FILE_FORMAT "verilog"  # or "vhdl"
set CLOCK_NAME "clk"       # must match RTL port name
set clk_period 10.0        # default clock period in ns
```

4. Test the new design:
```bash
curl -X POST http://localhost:8000/agent \
  -d '{"user_query":"Run synthesis for design your_design", "session_id":"test"}'
```

## Step 8: Monitoring and Debugging

### 8.1 Check Logs

All services generate detailed logs:

```bash
# Monitor synthesis logs
tail -f logs/synthesis/aes_synthesis_*.log

# Monitor placement logs
tail -f logs/unified_placement/aes_unified_placement_*.log

# Monitor CTS logs
tail -f logs/cts/aes_cts_*.log

# Monitor routing logs
tail -f logs/unified_route_save/aes_unified_route_save_*.log
```

### 8.2 Check Design Status

```bash
# List available designs
ls designs/

# Check design results
ls designs/aes/FreePDK45/synthesis/
ls designs/aes/FreePDK45/implementation/

# Check generated TCL scripts
ls result/aes/FreePDK45/

# Check final deliverables
ls deliverables/
```

### 8.3 Debug Common Issues

#### Service Connection Issues
```bash
# Check if services are running
ps aux | grep -E "(synth_server|unified_placement_server|cts_server|unified_route_save_server)"

# Restart services if needed
python run_server.py

# Check specific service
curl http://localhost:13333/docs
```

#### AI Agent Issues
```bash
# Check OpenAI API key
echo $OPENAI_API_KEY

# Test agent connectivity
curl -X POST http://localhost:8000/agent \
  -d '{"user_query":"test", "session_id":"debug"}'
```

#### EDA Tool Issues
```bash
# Check tool installation
which dc_shell
which innovus

# Set up environment variables
export SNPSLMD_LICENSE_FILE=/path/to/synopsys/license
export CDS_LIC_FILE=/path/to/cadence/license

# Check license servers
lmstat -a
```

#### Clock Port Mismatch
```bash
# Check RTL clock port name
grep -r "input.*clk" designs/aes/rtl/
grep -r "input.*clock" designs/b14/rtl/

# Update config.tcl to match RTL
nano designs/your_design/config.tcl
```

#### File Path Issues
```bash
# Check if required files exist
ls designs/aes/FreePDK45/synthesis/*/results/
ls designs/aes/FreePDK45/implementation/*/pnr_save/

# Check restore_enc file paths in logs
grep "restore_enc" logs/cts/aes_cts_*.log
```

## Step 9: Advanced Usage

### 9.1 Batch Processing Multiple Designs

Create a script for batch processing:

```bash
#!/bin/bash
# batch_process.sh

DESIGNS=("aes" "des" "b14")

for design in "${DESIGNS[@]}"; do
    echo "Processing design: $design"
    
    # Run complete flow
    curl -X POST http://localhost:8000/agent \
      -H "Content-Type: application/json" \
      -d "{\"user_query\":\"Run full_flow for design $design with performance optimization\", \"session_id\":\"batch_$design\"}"
    
    echo "Completed flow for $design"
    sleep 10  # Wait between designs
done
```

### 9.2 Custom Parameter Control

Use specific parameters for fine-tuned control:

```bash
# Synthesis with custom clock period
curl -X POST http://localhost:13333/run \
  -H "Content-Type: application/json" \
  -d '{
    "design": "aes",
    "clk_period": 2.0,
    "DRC_max_fanout": 15,
    "power_effort": "high",
    "force": true
  }'

# Placement with custom utilization
curl -X POST http://localhost:13340/run \
  -H "Content-Type: application/json" \
  -d '{
    "design": "aes",
    "syn_ver": "cpV1_clkP1_drcV1_20241201_143022",
    "target_util": 0.85,
    "ASPECT_RATIO": 1.2,
    "force": true
  }'
```


## Step 10: Results and Deliverables

### 10.1 Check Final Results

```bash
# List deliverables (if archive option was used)
ls deliverables/

# Extract and view tarball contents
tar -tzf deliverables/aes_*_route_save_*.tgz

# Check final GDS files
ls designs/aes/FreePDK45/implementation/*/pnr_out/*.gds*

# Check generated TCL scripts
ls result/aes/FreePDK45/
```

### 10.2 Performance Analysis

```bash
# Check synthesis reports
ls designs/aes/FreePDK45/synthesis/*/reports/
cat designs/aes/FreePDK45/synthesis/*/reports/qor.rpt

# Check implementation reports
ls designs/aes/FreePDK45/implementation/*/pnr_reports/
cat designs/aes/FreePDK45/implementation/*/pnr_reports/route_summary.rpt

# Check timing analysis
cat designs/aes/FreePDK45/implementation/*/pnr_reports/route_timing.rpt.gz | gunzip
```

### 10.3 Session History and Analysis

```bash
# View session history
curl -X GET http://localhost:8000/session/demo/history

# Check agent reasoning and suggestions
curl -X POST http://localhost:8000/agent \
  -d '{"user_query":"analyze the results for design aes", "session_id":"demo"}'
```

## Next Steps

1. **Explore Different Designs**: Try running the system with different designs (aes, des, b14)
2. **Experiment with Strategies**: Test different optimization strategies (fast, performance, power, area)
3. **Run Experiments**: Use the CodeBLEU experimental framework to evaluate generation quality
4. **Add Your Own Designs**: Create new designs following the existing structure
5. **Customize Parameters**: Fine-tune synthesis and implementation parameters
6. **Session Management**: Leverage the AI agent's memory for complex multi-stage workflows
7. **Integration**: Integrate with your existing EDA toolchain and CI/CD pipeline

## Getting Help

- **API Documentation**: Check `/docs` endpoint on each service for detailed API reference
- **Service Health**: Use the health check endpoints to monitor system status
- **Logs**: Check service logs in the `logs/` directory for detailed execution information
- **GitHub Issues**: Report problems and request features
- **Natural Language**: Use the AI agent to ask questions about the system itself

---

**Congratulations!** You've successfully set up and run your first design through the MCP EDA system. The AI-powered agent provides intelligent orchestration while the microservice architecture ensures scalability and maintainability. 
