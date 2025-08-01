# TCL CodeBLEU Evaluator

A specialized CodeBLEU implementation for evaluating TCL code quality in Electronic Design Automation (EDA) workflows. This module provides objective, academic-grade evaluation of generated TCL scripts against reference implementations.

## Overview

This CodeBLEU implementation is specifically adapted for the **4-Server EDA Architecture**:
- **Synthesis Server**: RTL-to-gate synthesis
- **Unified Placement Server**: Floorplan + Powerplan + Placement  
- **CTS Server**: Clock Tree Synthesis
- **Unified Route+Save Server**: Routing + Final Design Save

## Architecture

```
exp_v1/codebleu_tcl/
├── tcl_codebleu_evaluator.py    # Main evaluator class
├── codebleu/                    # Core CodeBLEU package
│   └── codebleu/
│       ├── codebleu.py          # Core CodeBLEU calculation
│       ├── bleu.py              # N-gram matching
│       ├── weighted_ngram_match.py  # Weighted n-gram matching
│       ├── syntax_match.py      # Syntax tree matching
│       ├── dataflow_match.py    # Dataflow analysis
│       ├── utils.py             # Utilities (comment removal, etc.)
│       ├── keywords/
│       │   └── tcl.txt          # EDA-specific TCL keywords
│       └── parser/              # Tree-sitter parsers
└── README.md                    # This file
```

## Key Features

### **EDA-Specific Adaptations**
- **Server-Aware Evaluation**: Different weights for synthesis, placement, CTS, and routing
- **EDA Command Recognition**: 270+ EDA-specific TCL keywords
- **Tool Detection**: Automatic detection of EDA tool type from script content
- **Template Integration**: Loads reference scripts from actual EDA templates

### **Academic Rigor**
- **Objective Scoring**: 0-100 scale with detailed component breakdown
- **Multi-Component Analysis**: N-gram, Weighted N-gram, Syntax, Dataflow matching
- **Comment Removal**: Proper TCL comment handling for fair comparison
- **Robust Error Handling**: Graceful handling of malformed scripts

### **CodeBLEU Components**
1. **N-gram Match**: Token-level similarity (BLEU-style)
2. **Weighted N-gram Match**: EDA keyword-weighted similarity
3. **Syntax Match**: Abstract syntax tree comparison
4. **Dataflow Match**: Variable usage and control flow analysis

## Usage

### **Basic Evaluation**
```python
from tcl_codebleu_evaluator import TCLCodeBLEUEvaluator

# Initialize evaluator
evaluator = TCLCodeBLEUEvaluator()

# Evaluate a single script
result = evaluator.evaluate_generated_tcl(
    generated_script="path/to/generated.tcl",
    reference_script="path/to/reference.tcl",
    tool_type="synthesis"  # Optional: auto-detected if not provided
)

print(f"CodeBLEU Score: {result['codebleu']:.1f}")
print(f"N-gram: {result['ngram_match_score']:.1f}")
print(f"Syntax: {result['syntax_match_score']:.1f}")
print(f"Dataflow: {result['dataflow_match_score']:.1f}")
```

### **Batch Evaluation**
```python
# Evaluate multiple scripts
results = evaluator.evaluate_batch(
    generated_files=["gen1.tcl", "gen2.tcl"],
    reference_files=["ref1.tcl", "ref2.tcl"],
    tool_types=["synthesis", "unified_placement"]
)

# Get average scores
avg_scores = evaluator.calculate_average_scores(results)
```

### **Integration with Experiment Framework**
```python
# Used by exp_v1/experiment/evaluate/evaluation_metrics.py
from exp_v1.codebleu_tcl.tcl_codebleu_evaluator import TCLCodeBLEUEvaluator

def evaluate_tcl_quality(generated_file, tool_type):
    evaluator = TCLCodeBLEUEvaluator()
    return evaluator.evaluate_generated_tcl(
        generated_script=generated_file,
        tool_type=tool_type
    )
```

## Configuration

### **EDA Server Weights**
Different weights for different EDA stages:

```python
eda_weights = {
    'synthesis': (0.20, 0.30, 0.25, 0.25),           # Higher weighted n-gram
    'unified_placement': (0.15, 0.25, 0.30, 0.30),   # Higher syntax & dataflow
    'cts': (0.20, 0.25, 0.30, 0.25),                # Higher syntax weight
    'unified_route_save': (0.20, 0.25, 0.25, 0.30),  # Higher dataflow weight
    'default': (0.25, 0.25, 0.25, 0.25)
}
```

### **Tool Detection Patterns**
Automatic tool type detection based on script content:

```python
detection_patterns = {
    'synthesis': {
        'patterns': ['analyze', 'elaborate', 'compile', 'synthesize'],
        'weight': 3.0
    },
    'unified_placement': {
        'patterns': ['floorPlan', 'addRing', 'placeDesign', 'globalNetConnect'],
        'weight': 2.5
    },
    'cts': {
        'patterns': ['ccopt_design', 'create_ccopt_clock_tree_spec'],
        'weight': 3.0
    },
    'unified_route_save': {
        'patterns': ['routeDesign', 'saveDesign', 'streamOut'],
        'weight': 2.0
    }
}
```

## Evaluation Metrics

### **Score Range**: 0-100
- **90-100**: Excellent similarity (near-identical functionality)
- **70-89**: Good similarity (minor differences)
- **50-69**: Moderate similarity (some structural differences)
- **30-49**: Low similarity (significant differences)
- **0-29**: Poor similarity (major structural differences)

### **Component Breakdown**
- **N-gram Match**: Basic token similarity
- **Weighted N-gram**: EDA keyword-weighted similarity
- **Syntax Match**: AST structure similarity  
- **Dataflow Match**: Variable usage and control flow similarity

## Technical Details

### **Tree-sitter Integration**
Uses tree-sitter for robust TCL parsing:
- Syntax tree generation
- Comment removal
- Variable usage analysis
- Control flow extraction

### **EDA Keyword Database**
270+ EDA-specific keywords organized by category:
- TCL built-in commands (100+ keywords)
- Synthesis commands (analyze, elaborate, compile, etc.)
- Placement commands (floorPlan, placeDesign, etc.)
- CTS commands (ccopt_design, create_ccopt_clock_tree_spec, etc.)
- Routing commands (routeDesign, optDesign, etc.)
- Reporting commands (report_timing, report_area, etc.)

### **Comment Handling**
Intelligent TCL comment removal:
```python
# Removes comments while preserving strings
def remove_tcl_comments(source):
    # Handles inline comments: command # comment
    # Preserves # within strings: puts "Value: #123"
    # Removes full-line comments: # This is a comment
```

## Testing

### **Unit Tests**
```bash
cd exp_v1/codebleu_tcl
python -m pytest tests/ -v
```

### **Integration Tests**
```bash
# Test with real server outputs
python tcl_codebleu_evaluator.py --test-mode
```

### **Validation**
```bash
# Run evaluation on sample data
cd exp_v1/experiment
python run_evaluation.py --method codebleu --dataset sample
```

## Performance

### **Typical Scores by Method**
- **OURS (AI-Generated)**: 60-80 (detailed, professional scripts)
- **BASELINE1 (Template)**: 40-60 (basic template matching)
- **BASELINE2 (Rule-based)**: 45-65 (structured but limited)

### **Execution Time**
- **Single evaluation**: ~0.1-0.5 seconds
- **Batch evaluation (100 files)**: ~10-30 seconds
- **Memory usage**: ~50-100MB for typical workloads

## Troubleshooting

### **Common Issues**

1. **Import Errors**
   ```bash
   # Ensure proper Python path
   export PYTHONPATH="${PYTHONPATH}:/path/to/exp_v1/codebleu_tcl"
   ```

2. **Tree-sitter Issues**
   ```bash
   # Install tree-sitter dependencies
   pip install tree-sitter tree-sitter-tcl
   ```

3. **Low Scores**
   - Check for empty/malformed scripts
   - Verify reference template quality
   - Review tool type detection accuracy

### **Debug Mode**
```python
evaluator = TCLCodeBLEUEvaluator()
evaluator.debug = True  # Enable detailed logging
result = evaluator.evaluate_generated_tcl(...)
```

## References

### **Academic Papers**
- CodeBLEU: a Method for Automatic Evaluation of Code Synthesis (EMNLP 2020)
- BLEU: a Method for Automatic Evaluation of Machine Translation (ACL 2002)

### **EDA Integration**
- Integrated with 4-server EDA architecture
- Compatible with Cadence Innovus and Synopsys Design Compiler
- Supports FreePDK45 and other standard cell libraries

## Contributing

### **Adding New EDA Tools**
1. Update `detection_patterns` in `tcl_codebleu_evaluator.py`
2. Add tool-specific keywords to `keywords/tcl.txt`
3. Define appropriate weights in `eda_weights`
4. Add test cases

### **Improving Accuracy**
1. Enhance tree-sitter parsing rules
2. Refine dataflow analysis patterns
3. Add more EDA-specific syntax patterns
4. Improve comment removal logic

---

**Version**: 1.0.0  
**Last Updated**: January 2025  
**Compatibility**: Python 3.11+, Tree-sitter 0.20+  
**License**: MIT License