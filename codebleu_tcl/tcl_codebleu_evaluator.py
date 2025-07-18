#!/usr/bin/env python3
"""TCL CodeBLEU Evaluator for Experiment Framework Integration"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

# Add the codebleu directory to path for imports
sys.path.append(str(Path(__file__).parent / "codebleu" / "codebleu"))

try:
    from codebleu import calc_codebleu
except ImportError:
    print("Warning: Could not import calc_codebleu. Make sure the codebleu package is properly set up.")
    calc_codebleu = None


class TCLCodeBLEUEvaluator:
    """TCL CodeBLEU Evaluator for experiment framework integration"""
    
    def __init__(self, keywords_dir: Optional[Path] = None):
        """Initialize the evaluator
        
        Args:
            keywords_dir: Path to keywords directory
        """
        if keywords_dir is None:
            keywords_dir = Path(__file__).parent / "codebleu" / "codebleu" / "keywords"
        self.keywords_dir = keywords_dir
        
        # Default weights for CodeBLEU calculation
        self.default_weights = (0.25, 0.25, 0.25, 0.25)
        
        # EDA tool specific evaluation weights
        self.eda_weights = {
            'floorplan': (0.20, 0.20, 0.30, 0.30),  # Higher syntax and dataflow weights
            'powerplan': (0.20, 0.20, 0.30, 0.30),  # Power planning stage
            'placement': (0.20, 0.20, 0.30, 0.30),  # Placement stage
            'cts': (0.20, 0.20, 0.30, 0.30),        # Clock tree synthesis stage
            'route': (0.20, 0.20, 0.30, 0.30),      # Routing stage
            'default': (0.25, 0.25, 0.25, 0.25)
        }
    
    def evaluate_generated_tcl(
        self,
        generated_tcl_file: Path,
        reference_tcl_file: Path,
        template_tcl_file: Optional[Path] = None,
        tool_type: str = "default"
    ) -> Dict:
        """Evaluate generated TCL against reference and template
        
        Args:
            generated_tcl_file: Path to generated TCL file
            reference_tcl_file: Path to reference TCL file
            template_tcl_file: Optional path to template TCL file
            tool_type: Type of EDA tool for weight adjustment
            
        Returns:
            Dictionary containing evaluation results
        """
        
        if calc_codebleu is None:
            return {"error": "CodeBLEU not available"}
        
        # Read TCL files
        generated_tcl = self._read_tcl_file(generated_tcl_file)
        reference_tcl = self._read_tcl_file(reference_tcl_file)
        template_tcl = self._read_tcl_file(template_tcl_file) if template_tcl_file else None
        
        # Get appropriate weights
        weights = self.eda_weights.get(tool_type, self.eda_weights['default'])
        
        try:
            # Calculate CodeBLEU score
            codebleu_result = calc_codebleu(
                [reference_tcl], 
                [generated_tcl],
                lang="tcl",
                weights=weights,
                keywords_dir=self.keywords_dir
            )
            
            # Additional analysis
            analysis_result = self._analyze_tcl_script(generated_tcl)
            
            # Combine results
            evaluation_result = {
                'file_info': {
                    'generated_file': str(generated_tcl_file),
                    'reference_file': str(reference_tcl_file),
                    'template_file': str(template_tcl_file) if template_tcl_file else None,
                    'tool_type': tool_type
                },
                'codebleu_scores': codebleu_result,
                'script_analysis': analysis_result,
                'summary': self._create_summary(codebleu_result, analysis_result)
            }
            
            return evaluation_result
            
        except Exception as e:
            return {
                'error': str(e),
                'file_info': {
                    'generated_file': str(generated_tcl_file),
                    'reference_file': str(reference_tcl_file),
                    'template_file': str(template_tcl_file) if template_tcl_file else None,
                    'tool_type': tool_type
                }
            }
    
    def evaluate_experiment_results(
        self,
        experiment_dir: Path,
        method_name: str,
        reference_dir: Optional[Path] = None,
        template_dir: Optional[Path] = None
    ) -> Dict:
        """Evaluate all results for a specific method in experiment directory
        
        Args:
            experiment_dir: Path to experiment directory
            method_name: Name of the method (baseline1, baseline2, ours)
            reference_dir: Optional path to reference TCL files
            template_dir: Optional path to template TCL files
            
        Returns:
            Dictionary containing evaluation results for all cases
        """
        
        method_dir = experiment_dir / "results" / method_name
        if not method_dir.exists():
            raise FileNotFoundError(f"Method directory not found: {method_dir}")
        
        # Find all generated TCL files
        generated_files = list(method_dir.glob("*.tcl"))
        if not generated_files:
            raise FileNotFoundError(f"No TCL files found in {method_dir}")
        
        # Evaluate each file
        results = {}
        overall_scores = {
            'codebleu_scores': [],
            'syntax_scores': [],
            'dataflow_scores': []
        }
        
        for generated_file in generated_files:
            case_name = generated_file.stem
            
            # Find corresponding reference and template files
            reference_file = None
            template_file = None
            
            if reference_dir:
                ref_file = reference_dir / f"{case_name}.tcl"
                if ref_file.exists():
                    reference_file = ref_file
            
            if template_dir:
                temp_file = template_dir / f"{case_name}.tcl"
                if temp_file.exists():
                    template_file = temp_file
            
            # Evaluate the file
            try:
                result = self.evaluate_generated_tcl(
                    generated_file,
                    reference_file or generated_file,  # Use generated as reference if no reference provided
                    template_file
                )
                
                results[case_name] = result
                
                # Collect scores for overall statistics
                if 'codebleu_scores' in result and 'codebleu' in result['codebleu_scores']:
                    overall_scores['codebleu_scores'].append(result['codebleu_scores']['codebleu'])
                    overall_scores['syntax_scores'].append(result['codebleu_scores']['syntax_match_score'])
                    overall_scores['dataflow_scores'].append(result['codebleu_scores']['dataflow_match_score'])
                
            except Exception as e:
                print(f"Error evaluating {case_name}: {e}")
                results[case_name] = {'error': str(e)}
        
        # Calculate overall statistics
        overall_stats = self._calculate_overall_statistics(overall_scores)
        
        return {
            'method': method_name,
            'experiment_dir': str(experiment_dir),
            'total_cases': len(results),
            'results': results,
            'overall_statistics': overall_stats
        }
    
    def compare_methods(
        self,
        experiment_dir: Path,
        methods: List[str] = None,
        reference_dir: Optional[Path] = None,
        template_dir: Optional[Path] = None
    ) -> Dict:
        """Compare multiple methods in an experiment
        
        Args:
            experiment_dir: Path to experiment directory
            methods: List of method names to compare
            reference_dir: Optional path to reference TCL files
            template_dir: Optional path to template TCL files
            
        Returns:
            Dictionary containing comparison results
        """
        
        if methods is None:
            methods = ['baseline1', 'baseline2', 'ours']
        
        method_results = {}
        
        for method in methods:
            try:
                result = self.evaluate_experiment_results(
                    experiment_dir,
                    method,
                    reference_dir,
                    template_dir
                )
                method_results[method] = result
            except Exception as e:
                print(f"Error evaluating method {method}: {e}")
                method_results[method] = {'error': str(e)}
        
        # Create comparison summary
        comparison = self._create_method_comparison(method_results)
        
        return {
            'experiment_dir': str(experiment_dir),
            'methods': methods,
            'method_results': method_results,
            'comparison': comparison
        }
    
    def _read_tcl_file(self, file_path: Optional[Path]) -> str:
        """Read TCL file content"""
        if file_path is None or not file_path.exists():
            return ""
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return ""
    
    def _analyze_tcl_script(self, script: str) -> Dict:
        """Analyze TCL script for additional metrics"""
        
        import re
        
        analysis = {
            'total_lines': len(script.split('\n')),
            'code_lines': len([line for line in script.split('\n') if line.strip() and not line.strip().startswith('#')]),
            'comment_lines': len([line for line in script.split('\n') if line.strip().startswith('#')]),
            'eda_commands': {},
            'variables': [],
            'syntax_errors': []
        }
        
        # Count EDA commands for different stages
        eda_commands = {
            'floorplan': ['setDrawView', 'floorPlan', 'setPinAssignMode', 'editPin', 'planDesign', 'checkFPlan', 'setDesignMode'],
            'powerplan': ['addTieHiLo', 'createPowerDomain', 'createPowerSwitch', 'createPowerPort', 'connectPowerNet', 'setPowerDomain'],
            'placement': ['placeDesign', 'place_opt_design', 'setPlaceMode', 'setOptMode', 'setPlaceMode', 'setOptMode'],
            'cts': ['createClockTreeSpec', 'clockDesign', 'createClock', 'setClockTreeOptions', 'setCTSMode', 'clockDesign'],
            'route': ['routeDesign', 'route_opt_design', 'setNanoRouteMode', 'setRouteMode', 'setNanoRouteMode', 'setRouteMode']
        }
        
        for category, commands in eda_commands.items():
            found_commands = []
            for cmd in commands:
                if cmd in script:
                    found_commands.append(cmd)
            analysis['eda_commands'][category] = {
                'found_commands': found_commands,
                'command_count': len(found_commands),
                'completeness': len(found_commands) / len(commands) if commands else 0.0
            }
        
        # Extract variables
        var_pattern = r'\$(\w+)'
        analysis['variables'] = list(set(re.findall(var_pattern, script)))
        
        # Basic syntax validation
        lines = script.split('\n')
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Check for unmatched braces
            if line.count('{') != line.count('}'):
                analysis['syntax_errors'].append(f"Line {i}: Unmatched braces")
            
            # Check for unmatched brackets
            if line.count('[') != line.count(']'):
                analysis['syntax_errors'].append(f"Line {i}: Unmatched brackets")
        
        return analysis
    
    def _create_summary(
        self,
        codebleu_result: Dict,
        analysis_result: Dict
    ) -> Dict:
        """Create a summary of evaluation results"""
        
        return {
            'overall_score': codebleu_result.get('codebleu', 0.0),
            'syntax_score': codebleu_result.get('syntax_match_score', 0.0),
            'dataflow_score': codebleu_result.get('dataflow_match_score', 0.0),
            'total_lines': analysis_result.get('total_lines', 0),
            'code_lines': analysis_result.get('code_lines', 0),
            'comment_lines': analysis_result.get('comment_lines', 0),
            'syntax_errors': len(analysis_result.get('syntax_errors', [])),
            'variable_count': len(analysis_result.get('variables', []))
        }
    
    def _calculate_overall_statistics(self, scores: Dict) -> Dict:
        """Calculate overall statistics from collected scores"""
        
        stats = {}
        
        for metric, score_list in scores.items():
            if score_list:
                stats[metric] = {
                    'mean': sum(score_list) / len(score_list),
                    'min': min(score_list),
                    'max': max(score_list),
                    'count': len(score_list)
                }
            else:
                stats[metric] = {
                    'mean': 0.0,
                    'min': 0.0,
                    'max': 0.0,
                    'count': 0
                }
        
        return stats
    
    def _create_method_comparison(self, method_results: Dict) -> Dict:
        """Create comparison between methods"""
        
        comparison = {
            'best_method': None,
            'method_rankings': {},
            'score_differences': {}
        }
        
        # Calculate average CodeBLEU scores
        method_scores = {}
        for method, result in method_results.items():
            if 'overall_statistics' in result and 'codebleu_scores' in result['overall_statistics']:
                avg_score = result['overall_statistics']['codebleu_scores']['mean']
                method_scores[method] = avg_score
        
        if method_scores:
            # Find best method
            best_method = max(method_scores.items(), key=lambda x: x[1])
            comparison['best_method'] = {
                'method': best_method[0],
                'score': best_method[1]
            }
            
            # Create rankings
            sorted_methods = sorted(method_scores.items(), key=lambda x: x[1], reverse=True)
            comparison['method_rankings'] = {
                method: {'rank': i+1, 'score': score}
                for i, (method, score) in enumerate(sorted_methods)
            }
            
            # Calculate score differences
            best_score = best_method[1]
            for method, score in method_scores.items():
                comparison['score_differences'][method] = {
                    'difference_from_best': best_score - score,
                    'percentage_of_best': (score / best_score) * 100 if best_score > 0 else 0
                }
        
        return comparison
    
    def save_evaluation_results(
        self,
        results: Dict,
        output_file: Path
    ) -> None:
        """Save evaluation results to JSON file"""
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"Evaluation results saved to: {output_file}")
        except Exception as e:
            print(f"Error saving results to {output_file}: {e}")


def main():
    """Main function for command-line usage"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="TCL CodeBLEU Evaluator")
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
    
    args = parser.parse_args()
    
    # Initialize evaluator
    evaluator = TCLCodeBLEUEvaluator()
    
    try:
        if args.compare_all:
            # Compare all methods
            results = evaluator.compare_methods(
                args.experiment_dir,
                reference_dir=args.reference_dir,
                template_dir=args.template_dir
            )
        else:
            # Evaluate single method
            results = evaluator.evaluate_experiment_results(
                args.experiment_dir,
                args.method,
                args.reference_dir,
                args.template_dir
            )
            
            # Update tool_type for all results based on stage-type
            if args.stage_type != "default":
                for case_name, result in results['results'].items():
                    if 'file_info' in result:
                        result['file_info']['tool_type'] = args.stage_type
        
        # Print summary
        if args.compare_all:
            print("\n=== Method Comparison Summary ===")
            comparison = results['comparison']
            if comparison['best_method']:
                print(f"Best Method: {comparison['best_method']['method']}")
                print(f"Best Score: {comparison['best_method']['score']:.4f}")
            
            print("\nMethod Rankings:")
            for method, info in comparison['method_rankings'].items():
                print(f"  {method}: Rank {info['rank']}, Score {info['score']:.4f}")
        else:
            print(f"\n=== {args.method.upper()} Method Evaluation Summary ===")
            stats = results['overall_statistics']
            print(f"Average CodeBLEU Score: {stats['codebleu_scores']['mean']:.4f}")
            print(f"Average Syntax Score: {stats['syntax_scores']['mean']:.4f}")
            print(f"Average Data Flow Score: {stats['dataflow_scores']['mean']:.4f}")
            print(f"Total Cases: {results['total_cases']}")
        
        # Save results if output file specified
        if args.output:
            evaluator.save_evaluation_results(results, args.output)
        
    except Exception as e:
        print(f"Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 