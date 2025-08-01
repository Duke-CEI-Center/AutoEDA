# Natural Language Toolkit: Utility functions
#
# Copyright (C) 2001-2020 NLTK Project
# Author: Steven Bird <stevenbird1@gmail.com>
# URL: <http://nltk.org/>
# For license information, see LICENSE

from itertools import chain

from tree_sitter import Language

AVAILABLE_LANGS = [
    "java",
    "javascript",
    "c_sharp",
    "php",
    "c",
    "cpp",
    "python",
    "go",
    "ruby",
    "rust",
    "tcl",
]  # keywords available


def pad_sequence(
    sequence,
    n,
    pad_left=False,
    pad_right=False,
    left_pad_symbol=None,
    right_pad_symbol=None,
):
    """
    Returns a padded sequence of items before ngram extraction.
        >>> list(pad_sequence([1,2,3,4,5], 2, pad_left=True, pad_right=True,
        >>>      left_pad_symbol='<s>', right_pad_symbol='</s>'))
        ['<s>', 1, 2, 3, 4, 5, '</s>']
        >>> list(pad_sequence([1,2,3,4,5], 2, pad_left=True, left_pad_symbol='<s>'))
        ['<s>', 1, 2, 3, 4, 5]
        >>> list(pad_sequence([1,2,3,4,5], 2, pad_right=True, right_pad_symbol='</s>'))
        [1, 2, 3, 4, 5, '</s>']
    :param sequence: the source data to be padded
    :type sequence: sequence or iter
    :param n: the degree of the ngrams
    :type n: int
    :param pad_left: whether the ngrams should be left-padded
    :type pad_left: bool
    :param pad_right: whether the ngrams should be right-padded
    :type pad_right: bool
    :param left_pad_symbol: the symbol to use for left padding (default is None)
    :type left_pad_symbol: any
    :param right_pad_symbol: the symbol to use for right padding (default is None)
    :type right_pad_symbol: any
    :rtype: sequence or iter
    """
    sequence = iter(sequence)
    if pad_left:
        sequence = chain((left_pad_symbol,) * (n - 1), sequence)
    if pad_right:
        sequence = chain(sequence, (right_pad_symbol,) * (n - 1))
    return sequence


# add a flag to pad the sequence so we get peripheral ngrams?


def ngrams(
    sequence,
    n,
    pad_left=False,
    pad_right=False,
    left_pad_symbol=None,
    right_pad_symbol=None,
):
    """
    Return the ngrams generated from a sequence of items, as an iterator.
    For example:
        >>> from nltk.util import ngrams
        >>> list(ngrams([1,2,3,4,5], 3))
        [(1, 2, 3), (2, 3, 4), (3, 4, 5)]
    Wrap with list for a list version of this function.  Set pad_left
    or pad_right to true in order to get additional ngrams:
        >>> list(ngrams([1,2,3,4,5], 2, pad_right=True))
        [(1, 2), (2, 3), (3, 4), (4, 5), (5, None)]
        >>> list(ngrams([1,2,3,4,5], 2, pad_right=True, right_pad_symbol='</s>'))
        [(1, 2), (2, 3), (3, 4), (4, 5), (5, '</s>')]
        >>> list(ngrams([1,2,3,4,5], 2, pad_left=True, left_pad_symbol='<s>'))
        [('<s>', 1), (1, 2), (2, 3), (3, 4), (4, 5)]
        >>> list(ngrams([1,2,3,4,5], 2, pad_left=True, pad_right=True, left_pad_symbol='<s>', right_pad_symbol='</s>'))
        [('<s>', 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, '</s>')]
    :param sequence: the source data to be converted into ngrams
    :type sequence: sequence or iter
    :param n: the degree of the ngrams
    :type n: int
    :param pad_left: whether the ngrams should be left-padded
    :type pad_left: bool
    :param pad_right: whether the ngrams should be right-padded
    :type pad_right: bool
    :param left_pad_symbol: the symbol to use for left padding (default is None)
    :type left_pad_symbol: any
    :param right_pad_symbol: the symbol to use for right padding (default is None)
    :type right_pad_symbol: any
    :rtype: sequence or iter
    """
    sequence = pad_sequence(sequence, n, pad_left, pad_right, left_pad_symbol, right_pad_symbol)

    history = []
    while n > 1:
        # PEP 479, prevent RuntimeError from being raised when StopIteration bubbles out of generator
        try:
            next_item = next(sequence)
        except StopIteration:
            # no more data, terminate the generator
            return
        history.append(next_item)
        n -= 1
    for item in sequence:
        history.append(item)
        yield tuple(history)
        del history[0]


def get_tree_sitter_language(lang: str) -> Language:
    """
    Get the tree-sitter language for a given language.
    :param lang: the language name to get the tree-sitter language for
    :return: the tree-sitter language
    """
    assert lang in AVAILABLE_LANGS, f"Language {lang} not available. Available languages: {AVAILABLE_LANGS}"

    try:
        if lang == "java":
            import tree_sitter_java

            return Language(tree_sitter_java.language())
        elif lang == "javascript":
            import tree_sitter_javascript

            return Language(tree_sitter_javascript.language())
        elif lang == "c_sharp":
            import tree_sitter_c_sharp

            return Language(tree_sitter_c_sharp.language())
        elif lang == "php":
            import tree_sitter_php

            try:
                return Language(tree_sitter_php.language())  # type: ignore[attr-defined]
            except AttributeError:
                return Language(tree_sitter_php.language_php())
        elif lang == "c":
            import tree_sitter_c

            return Language(tree_sitter_c.language())
        elif lang == "cpp":
            import tree_sitter_cpp

            return Language(tree_sitter_cpp.language())
        elif lang == "python":
            import tree_sitter_python

            return Language(tree_sitter_python.language())
        elif lang == "go":
            import tree_sitter_go

            return Language(tree_sitter_go.language())
        elif lang == "ruby":
            import tree_sitter_ruby

            return Language(tree_sitter_ruby.language())
        elif lang == "rust":
            import tree_sitter_rust

            return Language(tree_sitter_rust.language())
        elif lang == "tcl":
            # For TCL, we'll use a simplified approach since tree-sitter-tcl might not be available
            # We'll create a basic language definition or use a fallback
            try:
                import tree_sitter_tcl
                return Language(tree_sitter_tcl.language())
            except ImportError:
                # Fallback: create a basic language definition
                return _create_basic_tcl_language()
        else:
            assert False, "Not reachable"
    except ImportError:
        if lang == "tcl":
            # For TCL, provide a more helpful error message
            raise ImportError(
                f"Tree-sitter language for {lang} not available. "
                "Please install the language parser using `pip install tree-sitter-tcl` "
                "or use the fallback TCL parser."
            )
        else:
            raise ImportError(
                f"Tree-sitter language for {lang} not available. Please install the language parser using `pip install tree-sitter-{lang}`."
            )


def _create_basic_tcl_language():
    """Create a detailed TCL language definition for fallback"""
    # This is a more sophisticated TCL language definition
    # that can parse TCL syntax elements like commands, variables, control structures
    
    class TCLNode:
        def __init__(self, node_type, text="", start_point=(0, 0), end_point=(0, 0)):
            self.type = node_type
            self.text = text
            self.children = []
            self.start_point = start_point
            self.end_point = end_point
        
        def add_child(self, child):
            self.children.append(child)
        
        def __str__(self):
            if self.children:
                return f"({self.type} {' '.join(str(child) for child in self.children)})"
            else:
                return self.text or self.type
    
    class TCLTree:
        def __init__(self, root_node):
            self.root_node = root_node
    
    class DetailedTCLanguage:
        def __init__(self):
            self.name = "tcl"
            # EDA commands organized by the four unified server stages
            self.eda_commands = {
                # Synthesis Server Commands
                'synthesis': [
                    'analyze', 'elaborate', 'compile', 'compile_ultra',
                    'set_max_fanout', 'set_max_transition', 'set_max_capacitance',
                    'set_clock_uncertainty', 'create_clock', 'set_input_delay', 'set_output_delay',
                    'report_timing', 'report_area', 'report_power', 'report_qor',
                    'write_file', 'write_sdc', 'change_names', 'uniquify'
                ],

                # Unified Placement Server Commands (Floorplan + Powerplan + Placement)
                'unified_placement': [
                    # Floorplan commands
                    'setDrawView', 'floorPlan', 'setPinAssignMode', 'editPin', 'planDesign', 'checkFPlan',
                    'setDesignMode', 'defOut', 'summaryReport',

                    # Powerplan commands
                    'globalNetConnect', 'addStripe', 'sroute', 'addRing', 'addEndCap', 'addWellTap',
                    'createPowerDomain', 'createPowerSwitch', 'createPowerPort', 'connectPowerNet',

                    # Placement commands
                    'setPlaceMode', 'placeDesign', 'refinePlace', 'place_opt_design', 'setOptMode', 'optDesign',
                    'checkPlace', 'timeDesign', 'setExtractRCMode', 'extractRC', 'rcOut', 'saveNetlist'
                ],

                # CTS Server Commands
                'cts': [
                    'set_ccopt_property', 'ccopt_design', 'create_clock_tree_spec', 'clock_opt',
                    'setNanoRouteMode', 'report_ccopt_clock_tree_structure', 'report_ccopt_skew_groups',
                    'set_ccopt_mode', 'create_ccopt_clock_tree_spec', 'ccopt_check_and_flatten_ilms',
                    'all_registers', 'group_path', 'filter_collection', 'remove_from_collection'
                ],

                # Unified Route+Save Server Commands
                'unified_route_save': [
                    # Route commands
                    'setNanoRouteMode', 'setRouteMode', 'routeDesign', 'route_opt_design',
                    'checkRoute', 'verifyConnectivity', 'setAnalysisMode', 'addFiller',

                    # Save commands
                    'saveDesign', 'streamOut', 'defOut', 'saveNetlist', 'rcOut',
                    'write_sdf', 'report_power', 'report_timing', 'report_area'
                ],

                # Common/Setup commands used across stages
                'common_setup': [
                    'init_design', 'setMultiCpuUsage', 'setLibraryUnit', 'create_library_set',
                    'create_rc_corner', 'create_delay_corner', 'create_constraint_mode', 'create_analysis_view',
                    'set_analysis_view', 'update_constraint_mode', 'update_delay_corner'
                ]
            }
        
        def parse(self, code_bytes):
            try:
                code = code_bytes.decode('utf-8')
                root_node = self._parse_tcl_code(code)
                return TCLTree(root_node)
            except Exception as e:
                # Fallback to simple parsing if detailed parsing fails
                print(f"Warning: TCL parsing failed, using fallback: {e}")
                return self._fallback_parse(code_bytes)
        
        def _fallback_parse(self, code_bytes):
            """Fallback parsing method for error recovery"""
            code = code_bytes.decode('utf-8')
            root_node = TCLNode("program")
            root_node.add_child(TCLNode("word", code, (0, 0), (0, len(code))))
            return TCLTree(root_node)
        
        def _parse_tcl_code(self, code):
            """Parse TCL code into a detailed syntax tree"""
            # Preprocess code to handle multi-line commands
            processed_lines = self._preprocess_code(code)
            root_node = TCLNode("program")
            
            for line_info in processed_lines:
                line_num, line, start_col, end_col = line_info
                if not line or line.startswith('#'):
                    continue
                
                # Parse each line as a command
                command_node = self._parse_tcl_command(line, line_num, start_col, end_col)
                if command_node:
                    root_node.add_child(command_node)
            
            return root_node
        
        def _preprocess_code(self, code):
            """Preprocess code to handle multi-line commands and comments"""
            lines = code.split('\n')
            processed_lines = []
            current_line = ""
            current_line_num = 0
            current_start_col = 0
            
            for line_num, line in enumerate(lines):
                # Remove inline comments
                if '#' in line:
                    comment_pos = line.index('#')
                    # Check if # is inside quotes or braces
                    if not self._is_inside_quotes_or_braces(line, comment_pos):
                        line = line[:comment_pos].rstrip()
                
                # Handle line continuation
                if line.endswith('\\'):
                    current_line += line[:-1] + " "
                    if not current_line.strip():
                        current_start_col = len(line) - 1
                else:
                    current_line += line
                    if current_line.strip():
                        processed_lines.append((current_line_num, current_line.strip(), current_start_col, len(current_line)))
                    current_line = ""
                    current_line_num = line_num + 1
                    current_start_col = 0
            
            return processed_lines
        
        def _is_inside_quotes_or_braces(self, line, pos):
            """Check if a position is inside quotes or braces"""
            in_quotes = False
            in_braces = 0
            
            for i, char in enumerate(line[:pos]):
                if char == '"' and (i == 0 or line[i-1] != '\\'):
                    in_quotes = not in_quotes
                elif char == '{' and not in_quotes:
                    in_braces += 1
                elif char == '}' and not in_quotes:
                    in_braces -= 1
            
            return in_quotes or in_braces > 0
        
        def _parse_tcl_command(self, line, line_num, start_col, end_col):
            """Parse a single TCL command line"""
            if not line:
                return None
            
            # Split into words, handling quoted strings and braces
            words = self._split_tcl_words(line)
            if not words:
                return None
            
            command_name = words[0]
            args = words[1:]
            
            # Create command node with accurate position information
            command_node = TCLNode("command", command_name, (line_num, start_col), (line_num, end_col))
            
            # Add command name as first child
            name_node = TCLNode("word", command_name, (line_num, start_col), (line_num, start_col + len(command_name)))
            command_node.add_child(name_node)
            
            # Parse arguments based on command type
            try:
                if command_name == "set":
                    self._parse_set_command(command_node, args, line_num, start_col)
                elif command_name == "proc":
                    self._parse_proc_command(command_node, args, line_num, start_col)
                elif command_name in ["if", "elseif", "else"]:
                    self._parse_control_command(command_node, args, line_num, start_col)
                elif command_name in ["for", "foreach", "while"]:
                    self._parse_loop_command(command_node, args, line_num, start_col)
                elif self._is_eda_command(command_name):
                    self._parse_eda_command(command_node, args, line_num, start_col)
                else:
                    # Generic command parsing
                    self._parse_generic_command(command_node, args, line_num, start_col)
            except Exception as e:
                # If parsing fails, create a simple node
                print(f"Warning: Failed to parse command '{command_name}': {e}")
                self._parse_generic_command(command_node, args, line_num, start_col)
            
            return command_node
        
        def _is_eda_command(self, command_name):
            """Check if a command is an EDA tool command"""
            for category in self.eda_commands.values():
                if command_name in category:
                    return True
            return False
        
        def _split_tcl_words(self, line):
            """Split TCL line into words, handling quoted strings and braces"""
            words = []
            current_word = ""
            in_quotes = False
            in_braces = 0
            i = 0
            
            while i < len(line):
                char = line[i]
                
                if char == '"' and (i == 0 or line[i-1] != '\\'):
                    in_quotes = not in_quotes
                    current_word += char
                elif char == '{' and not in_quotes:
                    in_braces += 1
                    current_word += char
                elif char == '}' and not in_quotes:
                    in_braces -= 1
                    current_word += char
                elif char.isspace() and not in_quotes and in_braces == 0:
                    if current_word:
                        words.append(current_word)
                        current_word = ""
                else:
                    current_word += char
                
                i += 1
            
            if current_word:
                words.append(current_word)
            
            return words
        
        def _parse_set_command(self, command_node, args, line_num, start_col):
            """Parse set command: set var value"""
            if len(args) >= 2:
                # Variable name
                var_node = TCLNode("word", args[0], (line_num, start_col), (line_num, start_col + len(args[0])))
                command_node.add_child(var_node)
                
                # Value
                value_text = ' '.join(args[1:])
                value_node = TCLNode("word", value_text, (line_num, start_col), (line_num, start_col + len(value_text)))
                command_node.add_child(value_node)
        
        def _parse_proc_command(self, command_node, args, line_num, start_col):
            """Parse proc command: proc name args body"""
            if len(args) >= 3:
                # Procedure name
                name_node = TCLNode("word", args[0], (line_num, start_col), (line_num, start_col + len(args[0])))
                command_node.add_child(name_node)
                
                # Arguments
                args_node = TCLNode("word", args[1], (line_num, start_col), (line_num, start_col + len(args[1])))
                command_node.add_child(args_node)
                
                # Body
                body_text = ' '.join(args[2:])
                body_node = TCLNode("word", body_text, (line_num, start_col), (line_num, start_col + len(body_text)))
                command_node.add_child(body_node)
        
        def _parse_control_command(self, command_node, args, line_num, start_col):
            """Parse if/elseif/else commands"""
            if command_node.text in ["if", "elseif"] and args:
                # Condition
                condition_text = ' '.join(args)
                condition_node = TCLNode("word", condition_text, (line_num, start_col), (line_num, start_col + len(condition_text)))
                command_node.add_child(condition_node)
        
        def _parse_loop_command(self, command_node, args, line_num, start_col):
            """Parse for/foreach/while commands"""
            if args:
                # Loop specification
                loop_spec = ' '.join(args)
                loop_node = TCLNode("word", loop_spec, (line_num, start_col), (line_num, start_col + len(loop_spec)))
                command_node.add_child(loop_node)
        
        def _parse_eda_command(self, command_node, args, line_num, start_col):
            """Parse EDA tool commands"""
            for arg in args:
                arg_node = TCLNode("word", arg, (line_num, start_col), (line_num, start_col + len(arg)))
                command_node.add_child(arg_node)
        
        def _parse_generic_command(self, command_node, args, line_num, start_col):
            """Parse generic commands"""
            for arg in args:
                arg_node = TCLNode("word", arg, (line_num, start_col), (line_num, start_col + len(arg)))
                command_node.add_child(arg_node)
    
    return DetailedTCLanguage()
