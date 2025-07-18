# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from tree_sitter import Parser

from parser import (
    DFG_csharp,
    DFG_go,
    DFG_java,
    DFG_javascript,
    DFG_php,
    DFG_python,
    DFG_ruby,
    DFG_tcl,
    remove_comments_and_docstrings,
)
from utils import get_tree_sitter_language

dfg_function = {
    "python": DFG_python,
    "java": DFG_java,
    "ruby": DFG_ruby,
    "go": DFG_go,
    "php": DFG_php,
    "javascript": DFG_javascript,
    "c_sharp": DFG_csharp,
    "tcl": DFG_tcl,
}


def calc_syntax_match(references, candidate, lang):
    return corpus_syntax_match([references], [candidate], lang)


def corpus_syntax_match(references, candidates, lang, tree_sitter_language=None):
    if not tree_sitter_language:
        tree_sitter_language = get_tree_sitter_language(lang)

    parser = Parser()
    # Handle dummy language for TCL
    if hasattr(tree_sitter_language, 'name') and tree_sitter_language.name == "tcl":
        # Use a simple approach for TCL without tree-sitter
        return _simple_syntax_match(references, candidates, lang)
    else:
        parser.language = tree_sitter_language
    match_count = 0
    match_count_candidate_to_reference = 0
    total_count = 0

    for i in range(len(candidates)):
        references_sample = references[i]
        candidate = candidates[i]
        for reference in references_sample:
            try:
                candidate = remove_comments_and_docstrings(candidate, lang)
            except Exception:
                pass
            try:
                reference = remove_comments_and_docstrings(reference, lang)
            except Exception:
                pass

            candidate_tree = parser.parse(bytes(candidate, "utf8")).root_node

            reference_tree = parser.parse(bytes(reference, "utf8")).root_node

            def get_all_sub_trees(root_node):
                node_stack = []
                sub_tree_sexp_list = []
                depth = 1
                node_stack.append([root_node, depth])
                while len(node_stack) != 0:
                    cur_node, cur_depth = node_stack.pop()
                    sub_tree_sexp_list.append([str(cur_node), cur_depth])
                    for child_node in cur_node.children:
                        if len(child_node.children) != 0:
                            depth = cur_depth + 1
                            node_stack.append([child_node, depth])
                return sub_tree_sexp_list

            cand_sexps = [x[0] for x in get_all_sub_trees(candidate_tree)]
            ref_sexps = [x[0] for x in get_all_sub_trees(reference_tree)]

            # TODO: fix, now we count number of reference subtrees matching candidate,
            #       but we should count number of candidate subtrees matching reference
            #       See (4) in "3.2 Syntactic AST Match" of https://arxiv.org/pdf/2009.10297.pdf
            for sub_tree in ref_sexps:
                if sub_tree in cand_sexps:
                    match_count += 1

            for sub_tree in cand_sexps:
                if sub_tree in ref_sexps:
                    match_count_candidate_to_reference += 1

            total_count += len(ref_sexps)
    # print(f'match_count       {match_count} / {total_count}')
    # print(f'match_count_fixed {match_count_candidate_to_reference} / {total_count}')
    score = match_count / total_count
    return score


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
