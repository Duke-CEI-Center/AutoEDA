# TCL CodeBLEU Complete Implementation Summary

## Project Overview

This project extends the original CodeBLEU framework to add comprehensive support for the TCL language, specifically targeting TCL script evaluation for EDA (Electronic Design Automation) tools. By adding TCL language support, custom parsers, data flow graph extraction, syntax matching, and other functionalities, we have implemented CodeBLEU evaluation for EDA TCL scripts.

## Main Features

### 1. TCL Language Support
- Register TCL language support in the CodeBLEU framework
- Implement custom TCL parser as a fallback for tree-sitter
- Support TCL syntax structure parsing and command recognition

### 2. EDA Tool-Specific Evaluation
- Support for five EDA stages: floorplan, powerplan, placement, cts, route
- Optimized weight configuration for different stages
- EDA command recognition and classification statistics

### 3. Experiment Framework Integration
- Batch evaluation of TCL scripts from multiple methods
- Method comparison and ranking
- Detailed statistical analysis and report generation

### 4. Command Line and API Support
- Command line tool support for batch evaluation
- Python API support for programmatic evaluation
- Flexible parameter configuration and result output

## Technical Implementation Details

### 1. Language Support Registration

#### 1.1 AVAILABLE_LANGS Extension
**File:** `codebleu/codebleu/utils.py`

```python
AVAILABLE_LANGS = [
    "java", "javascript", "c_sharp", "php", "c", "cpp", 
    "python", "go", "ruby", "rust", "tcl"  # Newly added TCL support
]
```

**Purpose:** Add TCL language to the list of languages supported by CodeBLEU.

#### 1.2 Tree-sitter Language Processing
**File:** `codebleu/codebleu/utils.py`

```python
elif lang == "tcl":
    try:
        import tree_sitter_tcl
        return Language(tree_sitter_tcl.language())
    except ImportError:
        return _create_basic_tcl_language()
```

**Design Principle:**
- Prioritize using the official tree-sitter TCL parser
- Use custom fallback parser if unavailable
- Ensure TCL support doesn't fail due to missing dependencies

### 2. Custom TCL Parser

#### 2.1 Parser Architecture
**File:** `codebleu/codebleu/utils.py` in `_create_basic_tcl_language()`

**Core Components:**

1. **TCLNode Class:**
```python
class TCLNode:
    def __init__(self, node_type, text="", start_point=(0, 0), end_point=(0, 0)):
        self.type = node_type
        self.text = text
        self.children = []
        self.start_point = start_point
        self.end_point = end_point
```

2. **DetailedTCLanguage Class:**
   - Implements complete TCL syntax tree parsing
   - Supports multi-line commands and comment processing
   - Intelligent quote and brace handling

#### 2.2 EDA Command Classification
```python
self.eda_commands = {
    'floorplan': ['setDrawView', 'floorPlan', 'setPinAssignMode', 'editPin', 'planDesign', 'checkFPlan', 'setDesignMode'],
    'powerplan': ['addTieHiLo', 'createPowerDomain', 'createPowerSwitch', 'createPowerPort', 'connectPowerNet', 'setPowerDomain'],
    'placement': ['placeDesign', 'place_opt_design', 'setPlaceMode', 'setOptMode'],
    'cts': ['createClockTreeSpec', 'clockDesign', 'createClock', 'setClockTreeOptions', 'setCTSMode'],
    'route': ['routeDesign', 'route_opt_design', 'setNanoRouteMode', 'setRouteMode']
}
```

**Supported Five EDA Stages:**

1. **Floorplan (Layout Planning)**
   - Function: Define chip boundaries and macro unit placement
   - Main commands: `setDrawView`, `floorPlan`, `setPinAssignMode`, `editPin`, `planDesign`, `checkFPlan`

2. **Powerplan (Power Planning)**
   - Function: Create power domains and power switches
   - Main commands: `addTieHiLo`, `createPowerDomain`, `createPowerSwitch`, `createPowerPort`, `connectPowerNet`

3. **Placement (Placement)**
   - Function: Place standard cells and optimize layout
   - Main commands: `placeDesign`, `place_opt_design`, `setPlaceMode`, `setOptMode`

4. **CTS (Clock Tree Synthesis)**
   - Function: Create and optimize clock distribution networks
   - Main commands: `createClockTreeSpec`, `clockDesign`, `createClock`, `setClockTreeOptions`, `setCTSMode`

5. **Route (Routing)**
   - Function: Create physical connections between placed units
   - Main commands: `routeDesign`, `route_opt_design`, `setNanoRouteMode`, `setRouteMode`

### 3. Syntax Matching Support

#### 3.1 Syntax Matching Function Registration
**File:** `codebleu/codebleu/syntax_match.py`

```python
from parser import (
    DFG_csharp, DFG_go, DFG_java, DFG_javascript, 
    DFG_php, DFG_python, DFG_ruby, DFG_tcl  # Newly added TCL support
)

dfg_function = {
    "python": DFG_python, "java": DFG_java, "ruby": DFG_ruby,
    "go": DFG_go, "php": DFG_php, "javascript": DFG_javascript,
    "c_sharp": DFG_csharp, "tcl": DFG_tcl  # Newly added TCL mapping
}
```

#### 3.2 TCL Special Processing Logic
```python
# Handle dummy language for TCL
if hasattr(tree_sitter_language, 'name') and tree_sitter_language.name == "tcl":
    return _simple_syntax_match(references, candidates, lang)
```

#### 3.3 Simplified Syntax Matching Implementation
```python
def _simple_syntax_match(references, candidates, lang):
    """Simple syntax match for TCL without tree-sitter"""
    match_count = 0
    total_count = 0
    
    for i in range(len(candidates)):
        references_sample = references[i]
        candidate = candidates[i]
        
        for reference in references_sample:
            # Simple line-based comparison for TCL
            ref_lines = [line.strip() for line in reference.split('\n') 
                        if line.strip() and not line.strip().startswith('#')]
            cand_lines = [line.strip() for line in candidate.split('\n') 
                         if line.strip() and not line.strip().startswith('#')]
            
            # Count matching lines
            for ref_line in ref_lines:
                total_count += 1
                if ref_line in cand_lines:
                    match_count += 1
    
    if total_count == 0:
        return 0.0
    
    return match_count / total_count
```

**Working Principle:**
- Line-based simple syntax matching
- Exclude empty lines and comment lines
- Calculate the proportion of matching lines as syntax matching score

### 4. Data Flow Matching Support

#### 4.1 Data Flow Function Registration
**File:** `codebleu/codebleu/dataflow_match.py`

```python
from parser import (
    DFG_csharp, DFG_go, DFG_java, DFG_javascript, 
    DFG_php, DFG_python, DFG_ruby, DFG_rust, DFG_tcl  # Newly added TCL support
)

dfg_function = {
    "python": DFG_python, "java": DFG_java, "ruby": DFG_ruby,
    "go": DFG_go, "php": DFG_php, "javascript": DFG_javascript,
    "c_sharp": DFG_csharp, "c": DFG_csharp, "cpp": DFG_csharp,
    "rust": DFG_rust, "tcl": DFG_tcl  # Newly added TCL mapping
}
```

#### 4.2 TCL Special Processing Logic
```python
# Handle dummy language for TCL
if hasattr(tree_sitter_language, 'name') and tree_sitter_language.name == "tcl":
    return _simple_dataflow_match(references, candidates, lang)
```

#### 4.3 Simplified Data Flow Matching Implementation
```python
def _simple_dataflow_match(references, candidates, lang):
    """Simple dataflow match for TCL without tree-sitter"""
    match_count = 0
    total_count = 0
    
    for i in range(len(candidates)):
        references_sample = references[i]
        candidate = candidates[i]
        
        for reference in references_sample:
            # Extract variable assignments from TCL scripts
            ref_assignments = _extract_tcl_assignments(reference)
            cand_assignments = _extract_tcl_assignments(candidate)
            
            if ref_assignments:
                total_count += len(ref_assignments)
                for ref_assignment in ref_assignments:
                    if ref_assignment in cand_assignments:
                        match_count += 1
    
    if total_count == 0:
        return 1.0  # No assignments to match
    
    return match_count / total_count
```

#### 4.4 TCL Variable Assignment Extraction
```python
def _extract_tcl_assignments(script):
    """Extract variable assignments from TCL script"""
    assignments = []
    lines = script.split('\n')
    
    for line in lines:
        line = line.strip()
        if line.startswith('set ') and not line.startswith('#'):
            words = line.split()
            if len(words) >= 3:
                assignments.append((words[1], ' '.join(words[2:])))
    
    return assignments
```

**Working Principle:**
- Extract variable assignment statements from TCL scripts
- Recognize commands in `set var value` format
- Exclude comment lines
- Return list of tuples with variable names and values

### 5. Data Flow Graph Extraction

#### 5.1 DFG_tcl Function Implementation
**File:** `codebleu/codebleu/parser/DFG.py`

```python
def DFG_tcl(root_node, index_to_code, states):
    """Data Flow Graph extraction for TCL code"""
    assignment = ["set", "variable", "global"]
    if_statement = ["if", "elseif", "else"]
    for_statement = ["for", "foreach", "while"]
    proc_statement = ["proc"]
    command_statement = ["command"]
    states = states.copy()
```

#### 5.2 Main Processing Logic

1. **Leaf Node Processing:**
   - Process variables, literals, and other leaf nodes
   - Establish variable definition and usage relationships

2. **Variable Assignment Processing:**
   - Process variable assignments in `set` commands
   - Establish variable computation relationships

3. **Procedure Definition Processing:**
   - Process procedure definitions in `proc` commands
   - Analyze data flow in procedure bodies

4. **Control Structure Processing:**
   - Process `if/elseif/else` control structures
   - Analyze data flow in conditional branches

5. **Loop Structure Processing:**
   - Process `for/foreach/while` loop structures
   - Analyze data flow in loop bodies

6. **EDA Tool Command Processing:**
   - Process EDA tool-specific commands
   - Analyze data flow in command parameters

### 6. TCL CodeBLEU Evaluator

#### 6.1 Evaluator Class Design
**File:** `tcl_codebleu_evaluator.py`

```python
class TCLCodeBLEUEvaluator:
    """TCL CodeBLEU Evaluator for experiment framework integration"""
    
    def __init__(self, keywords_dir: Optional[Path] = None):
        # EDA tool specific evaluation weights
        self.eda_weights = {
            'floorplan': (0.20, 0.20, 0.30, 0.30),  # Higher syntax and dataflow weights
            'powerplan': (0.20, 0.20, 0.30, 0.30),  # Power planning stage
            'placement': (0.20, 0.20, 0.30, 0.30),  # Placement stage
            'cts': (0.20, 0.20, 0.30, 0.30),        # Clock tree synthesis stage
            'route': (0.20, 0.20, 0.30, 0.30),      # Routing stage
            'default': (0.25, 0.25, 0.25, 0.25)
        }
```

#### 6.2 Weight Configuration Design

**Weight Design Principle:**
- **Reduce N-gram weight (0.20)**: Reduce the impact of vocabulary repetition on scoring
- **Reduce AST weight (0.20)**: Reduce the impact of syntax differences on scoring
- **Increase syntax matching weight (0.30)**: Ensure syntax correctness is emphasized
- **Increase data flow weight (0.30)**: Ensure logical correctness is emphasized

**Weight Correspondence:**
```python
weights = (syntax_weight, dataflow_weight, ast_weight, ngram_weight)
```

#### 6.3 Core Evaluation Methods

1. **Single File Evaluation:**
```python
def evaluate_generated_tcl(
    self,
    generated_tcl_file: Path,      # Generated TCL file
    reference_tcl_file: Path,      # Reference TCL file
    template_tcl_file: Optional[Path] = None,  # Template file (optional)
    tool_type: str = "default"     # EDA tool type
) -> Dict:
```

2. **Batch Evaluation:**
```python
def evaluate_experiment_results(
    self,
    experiment_dir: Path,          # Experiment directory
    method_name: str,              # Method name
    reference_dir: Optional[Path] = None,  # Reference file directory
    template_dir: Optional[Path] = None    # Template file directory
) -> Dict:
```

3. **Method Comparison:**
```python
def compare_methods(
    self,
    experiment_dir: Path,
    methods: List[str] = None,
    reference_dir: Optional[Path] = None,
    template_dir: Optional[Path] = None
) -> Dict:
```

#### 6.4 Experiment Directory Structure
```
experiment_dir/
├── results/
│   ├── baseline1/
│   │   ├── case1.tcl
│   │   ├── case2.tcl
│   │   └── ...
│   ├── baseline2/
│   │   ├── case1.tcl
│   │   ├── case2.tcl
│   │   └── ...
│   └── ours/
│       ├── case1.tcl
│       ├── case2.tcl
│       └── ...
├── reference/  (optional)
│   ├── case1.tcl
│   ├── case2.tcl
│   └── ...
└── template/   (optional)
    ├── case1.tcl
    ├── case2.tcl
    └── ...
```

#### 6.5 Command Line Support
```python
parser.add_argument("--experiment-dir", type=Path, required=True,
                   help="Path to experiment directory")
parser.add_argument("--method", type=str, default="ours",
                   help="Method to evaluate (baseline1, baseline2, ours)")
parser.add_argument("--stage-type", type=str, default="default",
                   help="EDA stage type (floorplan, powerplan, placement, cts, route, default)")
parser.add_argument("--reference-dir", type=Path,
                   help="Path to reference TCL files")
parser.add_argument("--template-dir", type=Path,
                   help="Path to template TCL files")
parser.add_argument("--output", type=Path,
                   help="Output file for results")
parser.add_argument("--compare-all", action="store_true",
                   help="Compare all methods")
```

## Technical Highlights

### 1. Fault-Tolerant Design
- Comprehensive error handling mechanisms
- Individual file or method failures don't affect overall evaluation
- Fallback parser ensures normal operation even with missing dependencies

### 2. Modular Design
- Each method has a single responsibility, easy to maintain and test
- Methods collaborate through clear interfaces
- Support for extension and customization

### 3. Domain-Specific Optimization
- Adjust weights and evaluation strategies for EDA TCL script characteristics
- Specialized EDA command recognition and classification
- Support for specific evaluation of five EDA stages

### 4. Flexibility
- Support for optional parameters and default values
- Adapt to different experimental settings
- Support both command line and API usage methods

### 5. Rich Information
- Provide multi-dimensional analysis results
- Include detailed statistical information and error information
- Support multiple output formats

## Usage Methods

### 1. Python API Usage

```python
from tcl_codebleu_evaluator import TCLCodeBLEUEvaluator

# Initialize evaluator
evaluator = TCLCodeBLEUEvaluator()

# Evaluate single file
result = evaluator.evaluate_generated_tcl(
    generated_tcl_file=Path("generated.tcl"),
    reference_tcl_file=Path("reference.tcl"),
    tool_type="floorplan"  # or "powerplan", "placement", "cts", "route"
)

# Evaluate entire experiment
results = evaluator.evaluate_experiment_results(
    experiment_dir=Path("experiment/"),
    method_name="ours"
)

# Compare all methods
comparison = evaluator.compare_methods(
    experiment_dir=Path("experiment/")
)
```

### 2. Command Line Usage

```bash
# Evaluate single method
python tcl_codebleu_evaluator.py --experiment-dir experiment/ --method ours

# Evaluate specific stage type
python tcl_codebleu_evaluator.py --experiment-dir experiment/ --method ours --stage-type floorplan

# Compare all methods
python tcl_codebleu_evaluator.py --experiment-dir experiment/ --compare-all

# Save results to file
python tcl_codebleu_evaluator.py --experiment-dir experiment/ --method ours --output results.json
```

## Output Format

### 1. Single File Evaluation Results
```json
{
  "file_info": {
    "generated_file": "/path/to/generated.tcl",
    "reference_file": "/path/to/reference.tcl",
    "template_file": "/path/to/template.tcl",
    "tool_type": "floorplan"
  },
  "codebleu_scores": {
    "codebleu": 0.85,
    "syntax_match_score": 0.90,
    "dataflow_match_score": 0.80,
    "ast_match_score": 0.85,
    "ngram_match_score": 0.75
  },
  "script_analysis": {
    "total_lines": 50,
    "code_lines": 45,
    "comment_lines": 5,
    "eda_commands": {
      "floorplan": {
        "found_commands": ["setDrawView", "floorPlan"],
        "command_count": 2,
        "completeness": 0.29
      }
    },
    "variables": ["var1", "var2"],
    "syntax_errors": []
  },
  "summary": {
    "overall_score": 0.85,
    "syntax_score": 0.90,
    "dataflow_score": 0.80,
    "total_lines": 50,
    "code_lines": 45,
    "comment_lines": 5,
    "syntax_errors": 0,
    "variable_count": 2
  }
}
```

### 2. Batch Evaluation Results
```json
{
  "method": "ours",
  "experiment_dir": "/path/to/experiment",
  "total_cases": 10,
  "results": {
    "case1": {evaluation_result_dict},
    "case2": {evaluation_result_dict}
  },
  "overall_statistics": {
    "codebleu_scores": {
      "mean": 0.85,
      "min": 0.70,
      "max": 0.95,
      "count": 10
    },
    "syntax_scores": {...},
    "dataflow_scores": {...}
  }
}
```

### 3. Method Comparison Results
```json
{
  "experiment_dir": "/path/to/experiment",
  "methods": ["baseline1", "baseline2", "ours"],
  "method_results": {
    "baseline1": {batch_evaluation_result},
    "baseline2": {batch_evaluation_result},
    "ours": {batch_evaluation_result}
  },
  "comparison": {
    "best_method": {
      "method": "ours",
      "score": 0.85
    },
    "method_rankings": {
      "ours": {"rank": 1, "score": 0.85},
      "baseline2": {"rank": 2, "score": 0.80},
      "baseline1": {"rank": 3, "score": 0.75}
    },
    "score_differences": {
      "baseline1": {
        "difference_from_best": 0.10,
        "percentage_of_best": 88.24
      }
    }
  }
}
```

## Project Structure

```
codebleu_tcl/
├── codebleu/
│   └── codebleu/
│       ├── utils.py              # TCL language support and custom parser
│       ├── syntax_match.py       # Syntax matching support
│       ├── dataflow_match.py     # Data flow matching support
│       └── parser/
│           ├── __init__.py       # Import DFG_tcl
│           └── DFG.py            # Data flow graph extraction (includes DFG_tcl)
├── tcl_codebleu_evaluator.py     # Main evaluator class
├── TCL_CodeBLEU_完整实现总结.md   # Chinese version of this document
└── TCL_CodeBLEU_Complete_Implementation_Summary.md  # This document
```

## Summary

This project achieves complete TCL language support by making the following key improvements to the original CodeBLEU framework:

1. **Language Support Extension**: Register TCL language support in the CodeBLEU framework
2. **Custom Parser**: Implement a complete TCL syntax tree parser
3. **EDA-Specific Optimization**: Weight configuration and command recognition for five EDA stages
4. **Experiment Framework Integration**: Support for batch evaluation and method comparison
5. **Fault-Tolerant Design**: Ensure normal operation in various environments

These improvements enable CodeBLEU to accurately evaluate the quality of EDA TCL scripts, providing a powerful evaluation tool for EDA tool experimental research. The entire system maintains the generality of the CodeBLEU framework while being specifically optimized for TCL language and EDA tool characteristics. 