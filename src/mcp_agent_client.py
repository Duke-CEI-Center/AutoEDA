#!/usr/bin/env python3

import os
import json
import requests
import re
import pathlib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, asdict
import datetime

def load_env():
    load_dotenv()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "http://localhost")
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set in .env")
    return OPENAI_API_KEY, MCP_SERVER_HOST

OPENAI_API_KEY, MCP_SERVER_HOST = load_env()

client = OpenAI(api_key=OPENAI_API_KEY)
app = FastAPI(title="Enhanced Intelligent MCP EDA Agent Client")

@dataclass
class UserSession:
    """User session context"""
    last_parameters: Optional[Dict[str, Any]] = None
    last_tool: str = ""
    preferences: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, Any]]] = None
    
    def __post_init__(self):
        if self.history is None:
            self.history = []
        if self.preferences is None:
            self.preferences = {}

# Global session storage (should use database in production)
user_sessions: Dict[str, UserSession] = {}

class Instruction(BaseModel):
    user_query: str
    session_id: str = "default"  # Remove Optional, provide default value

class AgentResponse(BaseModel):
    tool_called: str
    tool_input: dict
    tool_output: dict
    ai_reasoning: str
    conflicts_detected: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None

# Enhanced parameter extractor
class EnhancedParameterExtractor:
    """Enhanced parameter extractor"""
    
    def __init__(self):
        # Extended parameter mappings
        self.parameter_patterns = {
            # Numerical parameters
            "target_util": [
                r'utilization.*?([0-9.]+)',
                r'density.*?([0-9.]+)',
                r'fill.*?([0-9.]+)',
                r'occupancy.*?([0-9.]+)'
            ],
            "version_idx": [
                r'version.*?index.*?([0-9]+)',
                r'config.*?version.*?([0-9]+)',
                r'synthesis.*?version.*?([0-9]+)',
                r'version.*?([0-9]+)'
            ],
            "clk_period": [
                r'clock.*?period.*?([0-9.]+)\s*ns',
                r'period.*?([0-9.]+)\s*ns'
            ],
            "ASPECT_RATIO": [
                r'aspect.*?ratio.*?([0-9.]+)',
                r'width.*?height.*?ratio.*?([0-9.]+)',
                r'length.*?width.*?ratio.*?([0-9.]+)'
            ]
        }
        
        # Relative change patterns
        self.relative_patterns = {
            "increase": [r'(increase|higher|larger).*?([0-9.]+)?', 1.2],
            "decrease": [r'(decrease|lower|smaller).*?([0-9.]+)?', 0.8],
            "slight_increase": [r'(slightly|slight).*?(increase|higher)', 1.1],
            "slight_decrease": [r'(slightly|slight).*?(decrease|lower)', 0.9],
            "significant_increase": [r'(significantly|significant|obviously).*?(increase|higher)', 1.5],
            "significant_decrease": [r'(significantly|significant|obviously).*?(decrease|lower)', 0.6]
        }
        
        # Descriptive parameter mappings
        self.descriptive_mapping = {
            "utilization": {
                "low": 0.5, "medium": 0.7, "high": 0.85, "very_high": 0.9,
                "sparse": 0.4, "tight": 0.8, "dense": 0.9
            },
            "clock_frequency": {
                "low_freq": 20.0, "medium_freq": 10.0, "high_freq": 5.0, "ultra_high_freq": 2.0
            }
        }
        
        # Frequency to period conversion
        self.frequency_pattern = r'frequency.*?([0-9.]+)\s*MHz'
    
    def extract_parameters(self, query: str, previous_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Enhanced parameter extraction"""
        extracted = {}
        query_lower = query.lower()
        
        # 1. Basic numerical parameter extraction
        for param, patterns in self.parameter_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, query_lower)
                if match:
                    try:
                        if param == "version_idx":
                            extracted[param] = int(match.group(1))
                        else:
                            extracted[param] = float(match.group(1))
                        break
                    except (ValueError, IndexError):
                        continue
        
        # 2. Frequency to period conversion
        freq_match = re.search(self.frequency_pattern, query_lower)
        if freq_match:
            try:
                freq_mhz = float(freq_match.group(1))
                extracted["clk_period"] = 1000.0 / freq_mhz  # MHz to ns
            except (ValueError, IndexError):
                pass
        
        # 3. Descriptive parameter mapping
        for param_type, mapping in self.descriptive_mapping.items():
            for desc, value in mapping.items():
                if desc in query_lower:
                    if param_type == "utilization":
                        extracted["target_util"] = value
                    elif param_type == "clock_frequency":
                        extracted["clk_period"] = value
                    break
        
        # Handle boolean force parameter
        force_patterns = [
            r'force',
            r'overwrite',
            r'force.*?overwrite',
            r'force.*?re.*?run',
            r'ignore.*?existing'
        ]
        
        for pattern in force_patterns:
            if re.search(pattern, query_lower):
                extracted["force"] = True
                break
        
        # 4. Relative change processing
        if previous_params:
            for change_type, (pattern, multiplier) in self.relative_patterns.items():
                if re.search(pattern, query_lower):
                    for param in ["target_util", "clk_period", "ASPECT_RATIO"]:
                        if param in previous_params:
                            extracted[param] = previous_params[param] * multiplier
                    # Handle version_idx separately (integer increment/decrement)
                    if "version_idx" in previous_params:
                        if "increase" in change_type:
                            extracted["version_idx"] = previous_params["version_idx"] + 1
                        elif "decrease" in change_type:
                            extracted["version_idx"] = max(0, previous_params["version_idx"] - 1)
                    break
        
        # 5. Context reference processing
        context_patterns = [
            r'same.*?(as|like).*?(before|previous|last)',
            r'use.*?(before|previous|last).*?settings',
            r'keep.*?(before|previous|last)',
            r'run.*?again',
            r'do.*?again',
            r're.*?run',
            r'continue.*?running'
        ]
        
        for pattern in context_patterns:
            if re.search(pattern, query_lower) and previous_params:
                # Reuse previous settings
                for key, value in previous_params.items():
                    if key not in extracted:
                        extracted[key] = value
                break
        
        # 6. Auto-inherit base parameters (if not specified in query and available in session)
        # Note: Only inherit non-critical parameters to avoid cross-design contamination
        if previous_params:
            # Only inherit safe parameters, not design-specific ones like 'design', 'top_module'
            safe_inherited_params = ["tech", "version_idx", "force"]
            for param in safe_inherited_params:
                if param not in extracted and param in previous_params:
                    extracted[param] = previous_params[param]
            
            # For syn_ver and impl_ver, only inherit if the design name is explicitly the same
            design_in_query = self.extract_design_from_query(query)
            previous_design = previous_params.get("design")
            
            if design_in_query and previous_design and design_in_query == previous_design:
                # Same design, can inherit version parameters
                version_params = ["syn_ver", "impl_ver"]
                for param in version_params:
                    if param not in extracted and param in previous_params:
                        extracted[param] = previous_params[param]
        
        return extracted
    
    def extract_design_from_query(self, query: str) -> Optional[str]:
        """Extract design name from user query"""
        query_lower = query.lower()
        
        # Common design name patterns
        design_patterns = [
            r'design\s+(\w+)',
            r'run\s+(\w+)',
            r'execute\s+(\w+)',
            r'process\s+(\w+)',
            r'synthesis\s+for\s+(\w+)',
            r'synthesis\s+(\w+)',
            r'(\w+)\s+synthesis',
            r'compile\s+(\w+)',
            r'(\w+)\s+compile',
            r'(\w+)\s+design',
            # Direct design name patterns
            r'\b(des|b14|aes|riscv|cpu|gpu|soc)\b'
        ]
        
        for pattern in design_patterns:
            match = re.search(pattern, query_lower)
            if match:
                design_name = match.group(1)
                # Filter out common non-design words
                if design_name not in ['the', 'and', 'for', 'with', 'using', 'run', 'execute', 'process']:
                    return design_name
        
        return None

# Conflict detector
class ConflictDetector:
    """Conflict requirement detector"""
    
    def __init__(self):
        self.conflicts = {
            ("power", "performance"): "Low power usually means performance may be limited",
            ("area", "performance"): "Small area design may affect timing performance",
            ("speed", "quality"): "Fast flow may affect design quality",
            ("utilization", "timing"): "High utilization may cause timing issues"
        }
    
    def detect_conflicts(self, query: str, strategy: str) -> List[str]:
        """Detect conflicting requirements"""
        detected = []
        query_lower = query.lower()
        
        # Detect power vs performance conflict
        if ("power" in query_lower or "low_power" in query_lower) and \
           ("performance" in query_lower or "high_performance" in query_lower):
            detected.append("Power and performance requirements may conflict")
        
        # Detect area vs performance conflict
        if ("area" in query_lower or "small_area" in query_lower) and \
           ("performance" in query_lower or "high_performance" in query_lower):
            detected.append("Area and performance requirements may conflict")
        
        # Detect speed vs quality conflict
        if ("fast" in query_lower or "speed" in query_lower) and \
           ("quality" in query_lower or "best_quality" in query_lower):
            detected.append("Speed and quality requirements may conflict")
        
        return detected

# Strategy parameter mappings
STRATEGY_PARAMS = {
    "fast": {
        "design_flow_effort": "express",
        "design_power_effort": "none",
        "target_util": 0.5,
        "ASPECT_RATIO": 1.0,
        "clk_period": 15.0
    },
    "performance": {
        "design_flow_effort": "standard",
        "design_power_effort": "medium",
        "target_util": 0.85,
        "ASPECT_RATIO": 1.0,
        "clk_period": 5.0
    },
    "power": {
        "design_flow_effort": "standard",
        "design_power_effort": "high",
        "target_util": 0.7,
        "ASPECT_RATIO": 1.2,
        "clk_period": 10.0
    },
    "area": {
        "design_flow_effort": "standard",
        "design_power_effort": "medium",
        "target_util": 0.9,
        "ASPECT_RATIO": 1.2,
        "clk_period": 8.0
    }
}

def get_session(session_id: str) -> UserSession:
    """Get or create user session"""
    if session_id not in user_sessions:
        user_sessions[session_id] = UserSession()
    return user_sessions[session_id]

def update_session(session_id: str, tool: str, params: Dict[str, Any], strategy: str):
    """Update user session"""
    session = get_session(session_id)
    session.last_tool = tool
    session.last_parameters = params.copy()
    
    # Ensure preferences is not None
    if session.preferences is None:
        session.preferences = {}
    session.preferences[f"preferred_strategy"] = strategy
    
    # Ensure history is not None
    if session.history is None:
        session.history = []
    session.history.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "tool": tool,
        "parameters": params,
        "strategy": strategy
    })
    
    # Keep only recent 10 history entries
    if len(session.history) > 10:
        session.history = session.history[-10:]

def find_exact_enc(design: str, impl_ver: str, stage: str) -> str:
    """Find the exact .enc.dat file for a specific stage and implementation version"""
    base_path = pathlib.Path(f"designs/{design}/FreePDK45/implementation/{impl_ver}/pnr_save")
    enc_file = base_path / f"{stage}.enc.dat"
    
    if enc_file.exists():
        return str(enc_file)
    return ""

async def execute_multi_stage_flow(flow_name: str, params: Dict[str, Any], strategy: str, session_id: str) -> AgentResponse:
    """Execute multi-stage EDA flows with stage-specific requirements"""
    
    # Extract stage-specific requirements if provided
    stage_requirements = params.get("stage_requirements", {})
    
    # Define flow stages for each flow type
    flow_definitions = {
        "synth": [
            ("synth", {"design": params.get("design", ""), "tech": params.get("tech", "FreePDK45"), "version_idx": params.get("version_idx", 0), "force": params.get("force", False)})
        ],
        "pnr": [
            ("unified_placement", {"design": params.get("design", ""), "top_module": params.get("top_module", ""), "syn_ver": params.get("syn_ver", "cpV1_clkP1_drcV1")}),
            ("cts", {"design": params.get("design", ""), "top_module": params.get("top_module", ""), "impl_ver": params.get("impl_ver", "cpV1_clkP1_drcV1__g0_p0")}),
            ("unified_route_save", {"design": params.get("design", ""), "top_module": params.get("top_module", ""), "impl_ver": params.get("impl_ver", "cpV1_clkP1_drcV1__g0_p0")})
        ],
        "full_flow": [
            ("synth", {"design": params.get("design", ""), "tech": params.get("tech", "FreePDK45"), "version_idx": params.get("version_idx", 0), "force": params.get("force", False)}),
            ("unified_placement", {"design": params.get("design", ""), "top_module": params.get("top_module", ""), "syn_ver": params.get("syn_ver", "cpV1_clkP1_drcV1")}),
            ("cts", {"design": params.get("design", ""), "top_module": params.get("top_module", ""), "impl_ver": params.get("impl_ver", "cpV1_clkP1_drcV1__g0_p0")}),
            ("unified_route_save", {"design": params.get("design", ""), "top_module": params.get("top_module", ""), "impl_ver": params.get("impl_ver", "cpV1_clkP1_drcV1__g0_p0")})
        ]
    }
    
    if flow_name not in flow_definitions:
        raise HTTPException(status_code=400, detail=f"Unknown flow: {flow_name}")
    
    stages = flow_definitions[flow_name]
    results = []
    
    for stage_name, base_stage_params in stages:
        # Create a copy of base parameters
        stage_params = base_stage_params.copy()
        
        # Add strategy to all stages
        stage_params["strategy"] = strategy
        
        # Apply stage-specific requirements if available
        if stage_name in stage_requirements:
            stage_req = stage_requirements[stage_name]
            
            # Add requirements text to stage parameters
            if "requirements" in stage_req:
                stage_params["requirements"] = stage_req["requirements"]
            
            # Add specific parameters for this stage
            if "parameters" in stage_req:
                stage_params.update(stage_req["parameters"])
        
        # Auto-add restore_enc parameter for stages that need previous stage output
        if stage_name in ["cts", "unified_route_save"]:
            impl_ver = stage_params.get("impl_ver", "cpV1_clkP1_drcV1__g0_p0")
            design = stage_params.get("design", "")
            
            if design:  # Only proceed if design is specified
                # Define which previous stage each stage depends on
                previous_stage_map = {
                    "cts": "unified_placement",
                    "unified_route_save": "cts"
                }
                
                previous_stage = previous_stage_map[stage_name]
                # For unified stages, look for the composite output file
                if previous_stage == "unified_placement":
                    restore_enc_path = find_exact_enc(design, impl_ver, "placement")
                else:
                    restore_enc_path = find_exact_enc(design, impl_ver, previous_stage)
                
                if restore_enc_path:
                    stage_params["restore_enc"] = restore_enc_path
                else:
                    # If no restore_enc found, use a default path pattern
                    if previous_stage == "unified_placement":
                        default_path = f"designs/{design}/FreePDK45/implementation/{impl_ver}/pnr_save/placement.enc.dat"
                    else:
                        default_path = f"designs/{design}/FreePDK45/implementation/{impl_ver}/pnr_save/{previous_stage}.enc.dat"
                    stage_params["restore_enc"] = default_path
        
        # Call the stage
        if stage_name not in TOOLS:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {stage_name}")
        
        info = TOOLS[stage_name]
        url = f"http://localhost:{info['port']}{info['path']}"
        
        try:
            print(f"Executing stage: {stage_name} with parameters: {stage_params}")
            response = requests.post(url, json=stage_params, timeout=300)
            response.raise_for_status()
            stage_output = response.json()
            results.append({
                "stage": stage_name,
                "params": stage_params,
                "output": stage_output
            })
            
            # Update session after each stage
            update_session(session_id, stage_name, stage_params, strategy)
            
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Stage {stage_name} execution failed: {str(e)}")
    
    # Generate summary for multi-stage execution
    summary = f"Successfully executed {flow_name} flow with {len(stages)} stages:\\n"
    for result in results:
        summary += f"- {result['stage']}: {result['output'].get('message', 'Completed')}\\n"
    
    return AgentResponse(
        tool_called=flow_name,
        tool_input=params,
        tool_output={"stages": results, "flow_type": flow_name},
        ai_reasoning=f"Successfully executed {flow_name} flow with {strategy} strategy. Completed {len(stages)} stages: {', '.join([stage[0] for stage in stages])}",
        conflicts_detected=None,
        suggestions=[f"{flow_name} flow completed with {strategy} optimization"]
    )

# Required parameters for each tool
REQUIRED_PARAMS = {
    "synth": ["design"],
    "unified_placement": ["design", "top_module", "syn_ver"],
    "cts": ["design", "top_module", "impl_ver", "restore_enc"],
    "unified_route_save": ["design", "top_module", "impl_ver", "restore_enc"]
}

# EDA tool server endpoints
TOOLS = {
    "synth": {"port": 18001, "path": "/run"},
    "unified_placement": {"port": 18002, "path": "/run"},
    "cts": {"port": 18003, "path": "/run"},
    "unified_route_save": {"port": 18004, "path": "/run"}
}

async def intelligent_agent(instruction: Instruction) -> AgentResponse:
    """Enhanced intelligent agent with GPT-4 integration"""
    
    # Get user session
    session = get_session(instruction.session_id)
    
    # Initialize extractors
    extractor = EnhancedParameterExtractor()
    conflict_detector = ConflictDetector()
    
    # Step 1: AI tool selection and base parameter extraction
    TOOL_SELECTION_PROMPT = f"""
You are an intelligent EDA tool selector. Analyze the user query and select the appropriate EDA tool(s) and extract basic parameters.

IMPORTANT: Provide all responses in English only, regardless of the input language.

Available tools:
- synth: Complete RTL-to-gate synthesis (setup + compile)
- unified_placement: Unified placement flow (floorplan + powerplan + placement)
- cts: Clock tree synthesis
- unified_route_save: Unified routing and save flow (routing + save design)
- pnr: Complete P&R flow (unified_placement + cts + unified_route_save)
- full_flow: Complete EDA flow (all stages)

Required parameters:
- design: Design name
- tech: Technology library (optional, default: FreePDK45)
- version_idx: Synthesis configuration version index (optional, default: 0)
- top_module: Top module name (required for physical design stages)
- syn_ver: Synthesis version (optional, default: cpV1_clkP1_drcV1)
- impl_ver: Implementation version (optional, default: cpV1_clkP1_drcV1__g0_p0)
- force: Force overwrite existing results (optional, default: false)

Stage-specific requirements (for multi-stage flows):
If user mentions specific requirements for stages like "unified_placement requirements: area optimization", 
"cts requirements: low power", "unified_route_save requirements: timing optimization", extract them.

User query: "{instruction.user_query}"

Return JSON response:
{{
    "tool": "selected_tool_name",
    "tool_input": {{
        "design": "extracted_design",
        "top_module": "extracted_top_module",
        "syn_ver": "extracted_or_default",
        "impl_ver": "extracted_or_default",
        "stage_requirements": {{
            "unified_placement": {{"requirements": "extracted_text", "parameters": {{}}}},
            "cts": {{"requirements": "extracted_text", "parameters": {{}}}},
            "unified_route_save": {{"requirements": "extracted_text", "parameters": {{}}}}
        }}
    }}
}}

Only include stages in stage_requirements that have specific requirements mentioned by the user.
"""

    tool_response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": TOOL_SELECTION_PROMPT}],
        temperature=0.1
    )
    
    # Parse tool selection result
    try:
        raw_response = tool_response.choices[0].message.content
        # Try direct JSON parsing first
        try:
            tool_data = json.loads(raw_response)
        except json.JSONDecodeError:
            # If direct parsing fails, try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                tool_data = json.loads(json_str)
            else:
                raise json.JSONDecodeError("No JSON found in response", raw_response, 0)
        
        tool_name = tool_data["tool"]
        base_params = tool_data["tool_input"]
    except (json.JSONDecodeError, KeyError) as e:
        raise HTTPException(status_code=400, detail="AI tool selection failed")
    
    # Step 2: Intelligent strategy recommendation
    STRATEGY_PROMPT = f"""
Analyze user requirements and recommend the most suitable optimization strategy. Return JSON format: {{"strategy": "strategy_name", "reasoning": "reasoning_process"}}

IMPORTANT: Provide reasoning in English only, regardless of the input language.

Available strategies:
- fast: Fast flow, short optimization time, suitable for prototype verification
- performance: High performance optimization, highest quality, suitable for final products
- power: Power optimization, reduce power consumption, suitable for mobile devices
- area: Area optimization, reduce chip area, suitable for cost-sensitive applications

Strategy selection rules:
- If user mentions "fast", "quick", "save time" -> fast
- If user mentions "performance", "high performance", "best quality" -> performance
- If user mentions "power", "low power", "energy saving" -> power
- If user mentions "area", "small area", "cost" -> area
- Default: fast (for quick verification)

User request: {instruction.user_query}
"""

    strategy_response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": STRATEGY_PROMPT}],
        temperature=0.1
    )
    
    try:
        raw_strategy_response = strategy_response.choices[0].message.content
        # Try direct JSON parsing first
        try:
            strategy_data = json.loads(raw_strategy_response)
        except json.JSONDecodeError:
            # If direct parsing fails, try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', raw_strategy_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                strategy_data = json.loads(json_str)
            else:
                raise json.JSONDecodeError("No JSON found in strategy response", raw_strategy_response, 0)
        
        strategy = strategy_data["strategy"]
        reasoning = strategy_data["reasoning"]
    except (json.JSONDecodeError, KeyError):
        strategy = "fast"
        reasoning = "Default to fast strategy for quick verification"
    
    # Step 3: Enhanced parameter extraction
    extracted_params = extractor.extract_parameters(instruction.user_query, session.last_parameters)
    
    # Step 4: Conflict detection
    conflicts = conflict_detector.detect_conflicts(instruction.user_query, strategy)
    
    # Step 5: Build final parameters
    final_params = base_params.copy()
    
    # Apply strategy parameters
    if strategy in STRATEGY_PARAMS:
        for key, value in STRATEGY_PARAMS[strategy].items():
            if key not in final_params:
                final_params[key] = value
    
    # Apply extracted parameters (override strategy parameters)
    final_params.update(extracted_params)
    
    # Apply user preferences
    if session.preferences:
        for key, value in session.preferences.items():
            if key.startswith('default_') and key[8:] not in final_params:
                final_params[key[8:]] = value
    
    # Step 6: Check for multi-stage flows and execute if needed
    multi_stage_flows = ["pnr", "full_flow"]
    
    # Step 7: Auto-complete file paths (using user-specified exact version)
    if tool_name in ["cts", "unified_route_save"] and "restore_enc" not in final_params:
        impl_ver = final_params.get("impl_ver", "")
        if not impl_ver:
            raise HTTPException(status_code=400, detail=f"{tool_name} stage requires impl_ver parameter")
        
        # Determine required previous stage
        previous_stage = {"cts": "placement", "unified_route_save": "cts"}[tool_name]
        
        # Find user-specified version's previous stage output
        restore_enc = find_exact_enc(final_params["design"], impl_ver, previous_stage)
        
        if restore_enc:
            final_params["restore_enc"] = restore_enc
        else:
            # EDA flow order prompt
            flow_order = ["synth", "unified_placement", "cts", "unified_route_save"]
            current_index = flow_order.index(tool_name)
            required_stages = " → ".join(flow_order[:current_index])
            
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot find {previous_stage} stage output file ({impl_ver}).\n"
                       f"EDA flow must be executed in order: {required_stages}\n"
                       f"Please run {previous_stage} stage first to generate necessary input files."
            )

    # Step 8: Validate required parameters
    required = REQUIRED_PARAMS.get(tool_name, [])
    missing = [param for param in required if param not in final_params]
    
    if missing:
        error_msg = f"Missing required parameters: {', '.join(missing)}. Please provide these parameters."
        if conflicts:
            error_msg += f"\nAdditionally detected potential conflicts: {'; '.join(conflicts)}"
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Skip multi-stage flow check as it was already handled above
    if tool_name in multi_stage_flows:
        return await execute_multi_stage_flow(tool_name, final_params, strategy, instruction.session_id)
    
    # Step 9: Call EDA tool
    if tool_name not in TOOLS:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")
    
    info = TOOLS[tool_name]
    url = f"{MCP_SERVER_HOST}:{info['port']}{info['path']}"
    
    try:
        response = requests.post(url, json=final_params, timeout=300)
        response.raise_for_status()
        tool_output = response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")
    
    # Step 10: Update session
    update_session(instruction.session_id, tool_name, final_params, strategy)
    
    # Step 11: Generate suggestions
    suggestions = []
    if strategy == "fast":
        suggestions.append("After fast flow completion, recommend running performance optimization version")
    elif strategy == "performance":
        suggestions.append("Performance optimization completed, consider power analysis if needed")
    elif strategy == "power":
        suggestions.append("Power optimization completed, verify timing constraints")
    elif strategy == "area":
        suggestions.append("Area optimization completed, check timing and power impact")
    
    return AgentResponse(
        tool_called=tool_name,
        tool_input=final_params,
        tool_output=tool_output,
        ai_reasoning=reasoning,
        conflicts_detected=conflicts if conflicts else None,
        suggestions=suggestions
    )

@app.post("/agent", response_model=AgentResponse)
async def agent_endpoint(instruction: Instruction):
    """Enhanced intelligent agent endpoint"""
    return await intelligent_agent(instruction)

@app.get("/session/{session_id}/history")
async def get_session_history(session_id: str):
    """Get session history"""
    session = get_session(session_id)
    return {
        "session_id": session_id,
        "history": session.history,
        "last_parameters": session.last_parameters,
        "preferences": session.preferences
    }

@app.post("/session/{session_id}/preferences")
async def update_preferences(session_id: str, preferences: Dict[str, Any]):
    """Update session preferences"""
    session = get_session(session_id)
    if session.preferences is None:
        session.preferences = {}
    session.preferences.update(preferences)
    return {"status": "success", "message": "Preferences updated"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
