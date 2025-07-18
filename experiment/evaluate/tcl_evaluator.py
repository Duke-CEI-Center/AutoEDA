#!/usr/bin/env python3
import os
import json
import time
import argparse
from typing import Dict, List
from evaluation_metrics import evaluate_tcl_quality, compare_methods

class TCLEvaluator:
    def __init__(self, results_dir="results", output_dir="evaluation_results"):
        self.results_dir = results_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def load_generation_results(self) -> Dict:
        """Load all generation results from results directory"""
        methods = ["baseline1", "baseline2", "ours"]
        all_results = {}
        
        for method in methods:
            method_dir = os.path.join(self.results_dir, method)
            if not os.path.exists(method_dir):
                print(f"Warning: {method_dir} not found")
                continue
            
            method_results = {}
            for file in os.listdir(method_dir):
                if file.endswith("_result.json"):
                    case_id = file.replace("_result.json", "")
                    result_file = os.path.join(method_dir, file)
                    tcl_file = os.path.join(method_dir, f"{case_id}_generated.tcl")
                    
                    with open(result_file, 'r') as f:
                        result = json.load(f)
                    
                    if os.path.exists(tcl_file):
                        with open(tcl_file, 'r') as f:
                            tcl_code = f.read()
                        result["tcl_code"] = tcl_code
                    
                    method_results[case_id] = result
            
            all_results[method] = method_results
        
        return all_results
    
    def evaluate_all_methods(self) -> Dict:
        """Evaluate all methods and generate comparison results"""
        generation_results = self.load_generation_results()
        evaluation_results = {}
        
        all_case_ids = set()
        for method_results in generation_results.values():
            all_case_ids.update(method_results.keys())
        
        for case_id in sorted(all_case_ids):
            case_evaluation = {
                "case_id": case_id,
                "methods": {}
            }
            
            for method in ["baseline1", "baseline2", "ours"]:
                if method in generation_results and case_id in generation_results[method]:
                    result = generation_results[method][case_id]
                    
                    # Extract tool type from case_id or result
                    tool_type = self._extract_tool_type(case_id, result)
                    
                    tcl_quality = evaluate_tcl_quality(
                        result.get("tcl_code", ""), 
                        tool_type
                    )
                    
                    case_evaluation["methods"][method] = {
                        "generation_success": result.get("success", False),
                        "execution_time": result.get("execution_time", 0),
                        "tcl_quality": tcl_quality,
                        "notes": result.get("notes", ""),
                        "timestamp": result.get("timestamp", ""),
                        "tool_type": tool_type
                    }
                else:
                    case_evaluation["methods"][method] = {
                        "generation_success": False,
                        "execution_time": 0,
                        "tcl_quality": {
                            "overall": "0.000",
                            "codebleu": "0.000",
                            "syntax_match": "0.000",
                            "dataflow_match": "0.000",
                            "ast_match": "0.000",
                            "ngram_match": "0.000",
                            "analysis": {
                                "command_count": 0,
                                "eda_commands": {},
                                "syntax_errors": 0,
                                "complexity": "low",
                                "total_lines": 0,
                                "comment_lines": 0,
                                "variables": []
                            },
                            "summary": {}
                        },
                        "notes": "No result found",
                        "timestamp": "",
                        "tool_type": "unknown"
                    }
            
            evaluation_results[case_id] = case_evaluation
        
        return evaluation_results
    
    def _extract_tool_type(self, case_id: str, result: Dict) -> str:
        """Extract EDA tool type from case_id or result"""
        # Try to extract from case_id
        case_lower = case_id.lower()
        if "floorplan" in case_lower:
            return "floorplan"
        elif "powerplan" in case_lower:
            return "powerplan"
        elif "placement" in case_lower:
            return "placement"
        elif "cts" in case_lower or "clock" in case_lower:
            return "cts"
        elif "route" in case_lower:
            return "route"
        
        # Try to extract from result
        if "tool" in result:
            return result["tool"]
        
        # Default to floorplan
        return "floorplan"
    
    def calculate_statistics(self, evaluation_results: Dict) -> Dict:
        """Calculate overall statistics for all methods using CodeBLEU scores"""
        methods = ["baseline1", "baseline2", "ours"]
        stats = {}
        
        for method in methods:
            success_count = 0
            codebleu_sum = 0
            syntax_sum = 0
            dataflow_sum = 0
            ast_sum = 0
            ngram_sum = 0
            time_sum = 0
            total_cases = 0
            
            for case_result in evaluation_results.values():
                if method in case_result["methods"]:
                    method_result = case_result["methods"][method]
                    total_cases += 1
                    
                    if method_result["generation_success"]:
                        success_count += 1
                        quality = method_result["tcl_quality"]
                        
                        try:
                            codebleu_sum += float(quality.get("codebleu", "0.0"))
                            syntax_sum += float(quality.get("syntax_match", "0.0"))
                            dataflow_sum += float(quality.get("dataflow_match", "0.0"))
                            ast_sum += float(quality.get("ast_match", "0.0"))
                            ngram_sum += float(quality.get("ngram_match", "0.0"))
                            time_sum += method_result["execution_time"]
                        except (ValueError, TypeError):
                            pass
            
            stats[method] = {
                "success_rate": success_count / total_cases if total_cases > 0 else 0,
                "avg_codebleu": codebleu_sum / success_count if success_count > 0 else 0,
                "avg_syntax": syntax_sum / success_count if success_count > 0 else 0,
                "avg_dataflow": dataflow_sum / success_count if success_count > 0 else 0,
                "avg_ast": ast_sum / success_count if success_count > 0 else 0,
                "avg_ngram": ngram_sum / success_count if success_count > 0 else 0,
                "avg_time": time_sum / success_count if success_count > 0 else 0,
                "total_cases": total_cases,
                "successful_cases": success_count
            }
        
        return stats
    
    def generate_evaluation_report(self) -> str:
        """Generate complete evaluation report with CodeBLEU analysis"""
        evaluation_results = self.evaluate_all_methods()
        statistics = self.calculate_statistics(evaluation_results)
        comparison = compare_methods(evaluation_results)
        
        report = {
            "evaluation_info": {
                "name": "TCL CodeBLEU Evaluation",
                "description": "Evaluation of TCL generation quality using CodeBLEU metrics",
                "total_cases": len(evaluation_results),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "evaluation_method": "CodeBLEU with TCL support",
                "evaluator_version": "Enhanced with TCL CodeBLEU implementation"
            },
            "case_results": evaluation_results,
            "statistics": statistics,
            "comparison": comparison,
            "detailed_analysis": self._generate_detailed_analysis(evaluation_results)
        }
        
        report_file = os.path.join(self.output_dir, "tcl_codebleu_evaluation.json")
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"CodeBLEU evaluation report saved to: {report_file}")
        return report_file
    
    def _generate_detailed_analysis(self, evaluation_results: Dict) -> Dict:
        """Generate detailed analysis of the evaluation results"""
        analysis = {
            "code_quality_insights": [],
            "method_performance": {},
            "eda_command_analysis": {},
            "syntax_analysis": {},
            "complexity_distribution": {}
        }
        
        # Analyze each method
        for method in ["baseline1", "baseline2", "ours"]:
            method_analysis = {
                "total_commands": 0,
                "total_syntax_errors": 0,
                "complexity_levels": {"low": 0, "medium": 0, "high": 0},
                "eda_command_usage": {},
                "avg_code_lines": 0,
                "avg_comment_lines": 0
            }
            
            code_lines_list = []
            comment_lines_list = []
            
            for case_result in evaluation_results.values():
                if method in case_result["methods"]:
                    method_result = case_result["methods"][method]
                    if method_result["generation_success"]:
                        quality = method_result["tcl_quality"]
                        analysis_data = quality.get("analysis", {})
                        
                        # Command count
                        method_analysis["total_commands"] += analysis_data.get("command_count", 0)
                        
                        # Syntax errors
                        method_analysis["total_syntax_errors"] += analysis_data.get("syntax_errors", 0)
                        
                        # Complexity
                        complexity = analysis_data.get("complexity", "low")
                        method_analysis["complexity_levels"][complexity] += 1
                        
                        # Code and comment lines
                        code_lines = analysis_data.get("total_lines", 0)
                        comment_lines = analysis_data.get("comment_lines", 0)
                        code_lines_list.append(code_lines)
                        comment_lines_list.append(comment_lines)
                        
                        # EDA commands
                        eda_commands = analysis_data.get("eda_commands", {})
                        for tool, cmd_data in eda_commands.items():
                            if tool not in method_analysis["eda_command_usage"]:
                                method_analysis["eda_command_usage"][tool] = {
                                    "total_commands": 0,
                                    "completeness": 0.0,
                                    "found_commands": []
                                }
                            method_analysis["eda_command_usage"][tool]["total_commands"] += cmd_data.get("command_count", 0)
                            method_analysis["eda_command_usage"][tool]["completeness"] += cmd_data.get("completeness", 0.0)
                            method_analysis["eda_command_usage"][tool]["found_commands"].extend(cmd_data.get("found_commands", []))
            
            # Calculate averages
            if code_lines_list:
                method_analysis["avg_code_lines"] = sum(code_lines_list) / len(code_lines_list)
            if comment_lines_list:
                method_analysis["avg_comment_lines"] = sum(comment_lines_list) / len(comment_lines_list)
            
            analysis["method_performance"][method] = method_analysis
        
        # Generate insights
        analysis["code_quality_insights"] = self._generate_insights(evaluation_results)
        
        return analysis
    
    def _generate_insights(self, evaluation_results: Dict) -> List[str]:
        """Generate insights from evaluation results"""
        insights = []
        
        # Analyze success rates
        success_rates = {}
        for method in ["baseline1", "baseline2", "ours"]:
            success_count = 0
            total_count = 0
            for case_result in evaluation_results.values():
                if method in case_result["methods"]:
                    total_count += 1
                    if case_result["methods"][method]["generation_success"]:
                        success_count += 1
            success_rates[method] = success_count / total_count if total_count > 0 else 0
        
        # Find best performing method
        best_method = max(success_rates.items(), key=lambda x: x[1])
        insights.append(f"Best success rate: {best_method[0]} ({best_method[1]:.1%})")
        
        # Analyze code quality
        for method in ["baseline1", "baseline2", "ours"]:
            avg_codebleu = 0
            count = 0
            for case_result in evaluation_results.values():
                if method in case_result["methods"]:
                    method_result = case_result["methods"][method]
                    if method_result["generation_success"]:
                        try:
                            avg_codebleu += float(method_result["tcl_quality"].get("codebleu", "0.0"))
                            count += 1
                        except (ValueError, TypeError):
                            pass
            
            if count > 0:
                avg_codebleu /= count
                insights.append(f"{method} average CodeBLEU: {avg_codebleu:.3f}")
        
        return insights
    
    def print_summary(self):
        """Print evaluation summary to console with CodeBLEU scores"""
        evaluation_results = self.evaluate_all_methods()
        statistics = self.calculate_statistics(evaluation_results)
        comparison = compare_methods(evaluation_results)
        
        print("\n" + "="*80)
        print("TCL CODEBLEU EVALUATION SUMMARY")
        print("="*80)
        
        for method in ["baseline1", "baseline2", "ours"]:
            stats = statistics[method]
            print(f"\n{method.upper()}:")
            print(f"  Success Rate:     {stats['success_rate']:.2%}")
            print(f"  Avg CodeBLEU:     {stats['avg_codebleu']:.3f}")
            print(f"  Avg Syntax Match: {stats['avg_syntax']:.3f}")
            print(f"  Avg Dataflow:     {stats['avg_dataflow']:.3f}")
            print(f"  Avg AST Match:    {stats['avg_ast']:.3f}")
            print(f"  Avg N-gram Match: {stats['avg_ngram']:.3f}")
            print(f"  Avg Time:         {stats['avg_time']:.2f}s")
            print(f"  Cases:            {stats['successful_cases']}/{stats['total_cases']}")
        
        # Print comparison insights
        if comparison.get("insights"):
            print(f"\nINSIGHTS:")
            for insight in comparison["insights"]:
                print(f"  • {insight}")
        
        # Print CodeBLEU analysis
        codebleu_analysis = comparison.get("codebleu_analysis", {})
        if codebleu_analysis:
            print(f"\nCODEBLEU ANALYSIS:")
            print(f"  Best Method:      {codebleu_analysis.get('best_method', 'N/A')}")
            print(f"  Best CodeBLEU:    {codebleu_analysis.get('best_codebleu', 0):.3f}")
            
            score_dist = codebleu_analysis.get("score_distribution", {})
            for method, scores in score_dist.items():
                print(f"  {method.upper()} Scores:")
                print(f"    CodeBLEU: {scores.get('codebleu_range', 'N/A')}")
                print(f"    Syntax:   {scores.get('syntax_range', 'N/A')}")
                print(f"    Dataflow: {scores.get('dataflow_range', 'N/A')}")
        
        print("\n" + "="*80)

def main():
    parser = argparse.ArgumentParser(description="Evaluate TCL generation quality using CodeBLEU")
    parser.add_argument("--results_dir", default="results", 
                       help="Directory containing generation results")
    parser.add_argument("--output_dir", default="evaluation_results",
                       help="Directory to save evaluation results")
    parser.add_argument("--summary", action="store_true",
                       help="Print summary to console")
    args = parser.parse_args()
    
    evaluator = TCLEvaluator(args.results_dir, args.output_dir)
    report_file = evaluator.generate_evaluation_report()
    
    if args.summary:
        evaluator.print_summary()
    
    print(f"CodeBLEU evaluation completed. Report saved to: {report_file}")

if __name__ == "__main__":
    main()