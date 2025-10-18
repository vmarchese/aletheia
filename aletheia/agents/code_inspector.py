"""Code Inspector Agent for mapping errors to source code.

This agent is responsible for:
- Reading PATTERN_ANALYSIS section from scratchpad
- Mapping stack traces to source files in user-provided repositories
- Extracting suspect functions and context
- Running git blame on suspect lines
- Analyzing caller relationships
- Writing results to the scratchpad's CODE_INSPECTION section

This is the SK-based version that uses Semantic Kernel's ChatCompletionAgent
with GitPlugin for automatic function calling.
"""

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aletheia.agents.sk_base import SKBaseAgent
from aletheia.llm.prompts import compose_messages, get_system_prompt, get_user_prompt_template
from aletheia.plugins.git_plugin import GitPlugin
from aletheia.scratchpad import ScratchpadSection
from aletheia.utils import run_command
from aletheia.utils.validation import validate_git_repository


class CodeInspectorAgent(SKBaseAgent):
    """SK-based agent responsible for inspecting source code related to errors.
    
    This agent uses Semantic Kernel's ChatCompletionAgent with GitPlugin for
    git operations. The LLM can automatically invoke plugin functions via
    FunctionChoiceBehavior.Auto().
    
    The Code Inspector Agent:
    1. Reads the PATTERN_ANALYSIS section from the scratchpad
    2. Extracts stack traces from error clusters
    3. Maps stack traces to source files in user-provided repositories
    4. Extracts suspect functions and surrounding context
    5. Runs git blame on suspect lines (via GitPlugin)
    6. Analyzes caller relationships (configurable depth)
    7. Writes results to the CODE_INSPECTION section
    
    Attributes:
        config: Agent configuration including repositories and analysis depth
        scratchpad: Scratchpad for reading data and writing inspection results
        repositories: List of repository paths to search for files
        analysis_depth: Depth of analysis (minimal, standard, deep)
        _git_plugin: GitPlugin instance for git operations
        _plugins_registered: Whether SK plugins have been registered
    """
    
    def __init__(self, config: Dict[str, Any], scratchpad: Any, repositories: Optional[List[str]] = None):
        """Initialize the Code Inspector Agent.
        
        Args:
            config: Configuration dictionary with code inspection settings
            scratchpad: Scratchpad instance for agent communication
            repositories: Optional list of repository paths to search
        """
        super().__init__(config, scratchpad, agent_name="code_inspector")
        self.repositories = repositories or []
        self.analysis_depth = config.get("code_inspection", {}).get("depth", "standard")
        
        # Initialize git plugin (not registered with kernel yet)
        self._git_plugin = GitPlugin(self.repositories)
        self._plugins_registered = False
    
    def _register_plugins(self) -> None:
        """Register SK plugins with the kernel for automatic function calling.
        
        This registers the GitPlugin so the SK agent can automatically invoke
        git operations via FunctionChoiceBehavior.Auto().
        """
        if self._plugins_registered:
            return
        
        # Update git plugin with current repositories
        self._git_plugin.set_repositories(self.repositories)
        
        # Register with kernel
        self.kernel.add_plugin(self._git_plugin, plugin_name="git")
        
        self._plugins_registered = True
    
    def _format_conversation_history(self, conversation_history: Any) -> str:
        """Format conversation history for prompt inclusion.
        
        This is a simple formatter - NO custom parsing or extraction logic.
        Just converts the conversation history to a readable string format.
        
        Args:
            conversation_history: Conversation history from scratchpad (list or dict)
        
        Returns:
            Formatted conversation history string
        """
        if not conversation_history:
            return "No conversation history available."
        
        if isinstance(conversation_history, list):
            # Format as list of messages
            formatted = []
            for msg in conversation_history:
                if isinstance(msg, dict):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    formatted.append(f"{role}: {content}")
                else:
                    formatted.append(str(msg))
            return "\n".join(formatted)
        elif isinstance(conversation_history, dict):
            # Format as dict with role -> messages mapping
            formatted = []
            for role, messages in conversation_history.items():
                if isinstance(messages, list):
                    for msg in messages:
                        formatted.append(f"{role}: {msg}")
                else:
                    formatted.append(f"{role}: {messages}")
            return "\n".join(formatted)
        else:
            return str(conversation_history)
    
    def _format_agent_notes(self, agent_notes: Any) -> str:
        """Format agent notes for prompt inclusion.
        
        This is a simple formatter - NO custom parsing or extraction logic.
        Just converts agent notes to a readable string format.
        
        Args:
            agent_notes: Agent notes from scratchpad (dict or any)
        
        Returns:
            Formatted agent notes string
        """
        if not agent_notes:
            return "No agent notes available."
        
        if isinstance(agent_notes, dict):
            formatted = []
            for agent_name, notes in agent_notes.items():
                formatted.append(f"=== {agent_name} ===")
                if isinstance(notes, dict):
                    for key, value in notes.items():
                        formatted.append(f"{key}: {value}")
                else:
                    formatted.append(str(notes))
            return "\n".join(formatted)
        else:
            return str(agent_notes)
    
    def execute(self, repositories: Optional[List[str]] = None, use_sk: bool = False, **kwargs) -> Dict[str, Any]:
        """Execute the code inspection process.
        
        This method can operate in two modes:
        1. SK mode: Uses SK agent with automatic function calling via GitPlugin
        2. Direct mode (default): Directly calls git operations (maintains backward compatibility)
        
        Args:
            repositories: Optional list of repository paths to search
            use_sk: If True, uses SK agent with GitPlugin. If False, uses direct git calls.
            **kwargs: Additional parameters for inspection
        
        Returns:
            Dictionary with execution results:
                - success: bool - Whether execution succeeded
                - suspect_files_found: int - Number of suspect files identified
                - git_blame_executed: int - Number of git blame operations
                - repositories_searched: int - Number of repositories searched
                - sk_used: bool - Whether SK mode was used
        
        Raises:
            ValueError: If PATTERN_ANALYSIS section is missing
            ValueError: If no repositories provided
        """
        # Update repositories if provided
        if repositories:
            self.repositories = repositories
        
        if not self.repositories:
            raise ValueError("No repositories provided. Cannot inspect code without repository paths.")
        
        # Validate repositories
        validated_repos = []
        for repo_path in self.repositories:
            try:
                validated_path = validate_git_repository(repo_path)
                validated_repos.append(validated_path)
            except Exception as e:
                # Log warning but continue with other repos
                print(f"Warning: Invalid repository {repo_path}: {e}")
        
        if not validated_repos:
            raise ValueError("No valid git repositories found.")
        
        self.repositories = validated_repos
        
        # Update git plugin with validated repos
        self._git_plugin.set_repositories([str(repo) for repo in self.repositories])
        
        # Read pattern analysis from scratchpad
        pattern_analysis = self.read_scratchpad(ScratchpadSection.PATTERN_ANALYSIS)
        if not pattern_analysis:
            raise ValueError("No pattern analysis found. Run Pattern Analyzer Agent first.")
        
        # If SK mode requested, register plugins and use SK agent
        if use_sk:
            self._register_plugins()
            return self._execute_with_sk(pattern_analysis)
        
        # Otherwise, use direct mode (backward compatibility)
        return self._execute_direct(pattern_analysis)
    
    def _execute_with_sk(self, pattern_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code inspection using SK agent with GitPlugin.
        
        This mode uses the SK ChatCompletionAgent which can automatically
        invoke GitPlugin functions for git operations. It supports both
        guided and conversational modes based on scratchpad content.
        
        Args:
            pattern_analysis: Pattern analysis data from scratchpad
        
        Returns:
            Dictionary with execution results
        """
        # Auto-detect conversational mode by checking for CONVERSATION_HISTORY
        conversation_history = self.read_scratchpad(ScratchpadSection.CONVERSATION_HISTORY)
        conversational_mode = bool(conversation_history)
        
        # Prepare context for SK agent
        stack_traces = self._extract_stack_traces(pattern_analysis)
        
        if not stack_traces and not conversational_mode:
            # No stack traces found in guided mode, write empty result
            inspection = {
                "suspect_files": [],
                "related_code": [],
                "note": "No stack traces found in pattern analysis"
            }
            self.write_scratchpad(ScratchpadSection.CODE_INSPECTION, inspection)
            return {
                "success": True,
                "suspect_files_found": 0,
                "git_blame_executed": 0,
                "repositories_searched": len(self.repositories),
                "sk_used": True,
                "conversational_mode": False
            }
        
        # Build prompt based on mode
        if conversational_mode:
            user_message = self._build_sk_conversational_prompt(
                pattern_analysis,
                conversation_history
            )
            # Note: system prompt for conversational mode is set during agent initialization
            # via the agent_name parameter which looks up "code_inspector_conversational"
            # For now, we use the default system prompt and rely on the comprehensive user prompt
        else:
            user_message = self._build_sk_guided_prompt(stack_traces)
        
        # Invoke SK agent
        response = self.invoke(
            user_message,
            settings={"temperature": 0.3, "max_tokens": 2000}
        )
        
        # Parse response to extract inspection results
        inspection = self._parse_sk_inspection_response(response, conversational_mode)
        
        # Write inspection results to scratchpad
        self.write_scratchpad(ScratchpadSection.CODE_INSPECTION, inspection)
        
        return {
            "success": True,
            "suspect_files_found": len(inspection.get("suspect_files", [])),
            "git_blame_executed": sum(1 for sf in inspection.get("suspect_files", []) if sf.get("git_blame")),
            "repositories_searched": len(self.repositories),
            "sk_used": True,
            "conversational_mode": conversational_mode,
            "needs_clarification": inspection.get("needs_clarification", False)
        }
    
    def _build_sk_guided_prompt(self, stack_traces: List[str]) -> str:
        """Build guided mode prompt for SK agent.
        
        Args:
            stack_traces: List of stack traces to analyze
        
        Returns:
            Prompt string for SK agent
        """
        return f"""
Analyze the following stack traces and perform code inspection:

Stack Traces:
{json.dumps(stack_traces, indent=2)}

Repositories to search:
{json.dumps([str(repo) for repo in self.repositories], indent=2)}

For each stack trace:
1. Map file references to actual files in the repositories using find_file_in_repo
2. Extract code context using extract_code_context
3. Run git blame on suspect lines using git_blame
4. Analyze the code and git blame information

Provide your analysis in JSON format with this structure:
{{
    "suspect_files": [
        {{
            "file": "path/to/file",
            "line": 123,
            "function": "function_name",
            "repository": "/path/to/repo",
            "snippet": "code snippet",
            "analysis": "your analysis",
            "git_blame": {{ git blame info }}
        }}
    ],
    "related_code": []
}}
"""
    
    def _build_sk_conversational_prompt(
        self,
        pattern_analysis: Dict[str, Any],
        conversation_history: Any
    ) -> str:
        """Build conversational mode prompt for SK agent.
        
        This method reads all relevant sections from scratchpad and builds
        a comprehensive prompt that includes conversation history, pattern
        analysis, and agent notes. The LLM will extract repository paths
        from this context.
        
        Args:
            pattern_analysis: Pattern analysis data from scratchpad
            conversation_history: Conversation history from scratchpad
        
        Returns:
            Prompt string for SK agent
        """
        # Get template
        prompt_template = get_user_prompt_template("code_inspector_conversational")
        
        # Read problem description
        problem_description = self.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION)
        if not problem_description:
            problem_description = "No problem description available."
        elif isinstance(problem_description, dict):
            problem_description = problem_description.get("description", str(problem_description))
        
        # Format conversation history
        conversation_str = self._format_conversation_history(conversation_history)
        
        # Format pattern analysis
        pattern_analysis_str = json.dumps(pattern_analysis, indent=2) if pattern_analysis else "No pattern analysis available."
        
        # Try to read agent notes (may not exist in all scratchpads)
        agent_notes = None
        try:
            # Check if AGENT_NOTES section exists
            if hasattr(ScratchpadSection, 'AGENT_NOTES'):
                agent_notes = self.read_scratchpad(ScratchpadSection.AGENT_NOTES)
        except (AttributeError, KeyError):
            # AGENT_NOTES section doesn't exist, that's okay
            pass
        
        agent_notes_str = self._format_agent_notes(agent_notes)
        
        # Build prompt
        return prompt_template.format(
            problem_description=str(problem_description),
            conversation_history=conversation_str,
            pattern_analysis=pattern_analysis_str,
            agent_notes=agent_notes_str
        )
    
    def _parse_sk_inspection_response(
        self,
        response: str,
        conversational_mode: bool
    ) -> Dict[str, Any]:
        """Parse SK agent response into inspection results.
        
        Args:
            response: Response from SK agent
            conversational_mode: Whether in conversational mode
        
        Returns:
            Parsed inspection dictionary
        """
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                inspection = json.loads(json_match.group(0))
            else:
                # Fallback: create inspection from response text
                inspection = {
                    "suspect_files": [],
                    "related_code": [],
                    "analysis_text": response
                }
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            inspection = {
                "suspect_files": [],
                "related_code": [],
                "analysis_text": response
            }
        
        # Add conversational fields if in conversational mode
        if conversational_mode:
            if "conversational_summary" not in inspection:
                inspection["conversational_summary"] = None
            if "confidence" not in inspection:
                inspection["confidence"] = None
            if "reasoning" not in inspection:
                inspection["reasoning"] = None
            if "needs_clarification" not in inspection:
                inspection["needs_clarification"] = False
            if "clarification_questions" not in inspection:
                inspection["clarification_questions"] = []
            if "repositories_identified" not in inspection:
                inspection["repositories_identified"] = [str(repo) for repo in self.repositories]
        
        return inspection
    
    def _execute_direct(self, pattern_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code inspection using direct git operations (backward compatibility).
        
        This mode directly calls git operations via subprocess, maintaining
        backward compatibility with existing code.
        
        Args:
            pattern_analysis: Pattern analysis data from scratchpad
        
        Returns:
            Dictionary with execution results
        """
        # Initialize inspection results
        inspection = {
            "suspect_files": [],
            "related_code": []
        }
        
        # Extract stack traces from error clusters
        stack_traces = self._extract_stack_traces(pattern_analysis)
        
        # Map stack traces to source files
        for stack_trace in stack_traces:
            file_mappings = self._map_stack_trace_to_files(stack_trace)
            
            for file_info in file_mappings:
                # Extract code around suspect line
                code_info = self._extract_code(
                    file_info["repository"],
                    file_info["file"],
                    file_info["line"]
                )
                
                if code_info:
                    # Run git blame on suspect line
                    git_blame_info = self._run_git_blame(
                        file_info["repository"],
                        file_info["file"],
                        file_info["line"]
                    )
                    
                    # Analyze with LLM
                    analysis = self._analyze_code_with_llm(
                        code_info, 
                        stack_trace,
                        file_path=file_info["file"],
                        git_blame_info=git_blame_info
                    )
                    
                    suspect_entry = {
                        "file": file_info["file"],
                        "line": file_info["line"],
                        "function": code_info.get("function", "unknown"),
                        "repository": str(file_info["repository"]),
                        "snippet": code_info.get("snippet", ""),
                        "analysis": analysis,
                        "git_blame": git_blame_info
                    }
                    
                    inspection["suspect_files"].append(suspect_entry)
                    
                    # Analyze callers if depth is standard or deep
                    if self.analysis_depth in ["standard", "deep"]:
                        callers = self._analyze_callers(
                            file_info["repository"],
                            file_info["file"],
                            code_info.get("function", "")
                        )
                        inspection["related_code"].extend(callers)
        
        # Write inspection results to scratchpad
        self.write_scratchpad(ScratchpadSection.CODE_INSPECTION, inspection)
        
        return {
            "success": True,
            "suspect_files_found": len(inspection["suspect_files"]),
            "git_blame_executed": sum(1 for sf in inspection["suspect_files"] if sf.get("git_blame")),
            "repositories_searched": len(self.repositories),
            "sk_used": False
        }
    
    def _extract_stack_traces(self, pattern_analysis: Dict[str, Any]) -> List[str]:
        """Extract stack traces from pattern analysis.
        
        Args:
            pattern_analysis: Pattern analysis data from scratchpad
        
        Returns:
            List of stack trace strings
        """
        stack_traces = []
        
        # Extract from error clusters
        error_clusters = pattern_analysis.get("error_clusters", [])
        for cluster in error_clusters:
            if isinstance(cluster, dict) and "stack_trace" in cluster:
                stack_traces.append(cluster["stack_trace"])
            elif isinstance(cluster, dict) and "pattern" in cluster:
                # Pattern might contain file:line information
                pattern = cluster["pattern"]
                if re.search(r'\w+\.\w+:\d+', pattern):
                    stack_traces.append(pattern)
        
        # Extract from anomalies if they contain stack traces
        anomalies = pattern_analysis.get("anomalies", [])
        for anomaly in anomalies:
            if isinstance(anomaly, dict):
                desc = anomaly.get("description", "")
                # Look for stack trace patterns in description
                if "→" in desc or "->" in desc:
                    stack_traces.append(desc)
        
        return stack_traces
    
    def _map_stack_trace_to_files(self, stack_trace: str) -> List[Dict[str, Any]]:
        """Map a stack trace to source files in repositories.
        
        Args:
            stack_trace: Stack trace string (e.g., "charge.go:112 → features.go:57")
        
        Returns:
            List of dictionaries with file, line, and repository information
        """
        file_mappings = []
        
        # Handle None or empty stack trace
        if not stack_trace:
            return file_mappings
        
        # Parse stack trace to extract file:line pairs
        # Support multiple formats: "file.go:123", "file.go:123 → file2.go:456"
        patterns = [
            r'(\w+/[\w/]+\.\w+):(\d+)',  # Full path: dir/file.ext:line
            r'([\w]+\.\w+):(\d+)',        # Simple: file.ext:line
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, stack_trace)
            for file_path, line_num in matches:
                # Search for this file in all repositories
                for repo in self.repositories:
                    found_files = self._find_file_in_repository(repo, file_path)
                    for found_file in found_files:
                        file_mappings.append({
                            "file": str(found_file.relative_to(repo)),
                            "line": int(line_num),
                            "repository": repo,
                            "full_path": found_file
                        })
        
        return file_mappings
    
    def _find_file_in_repository(self, repository: Path, file_name: str) -> List[Path]:
        """Find a file in a git repository.
        
        Args:
            repository: Path to the git repository
            file_name: Name or relative path of the file to find
        
        Returns:
            List of Path objects for matching files
        """
        matches = []
        
        # If file_name contains path separators, search for exact path
        if "/" in file_name or "\\" in file_name:
            full_path = repository / file_name
            if full_path.exists() and full_path.is_file():
                matches.append(full_path)
        else:
            # Search for file by name recursively
            for file_path in repository.rglob(f"*{file_name}"):
                if file_path.is_file():
                    matches.append(file_path)
        
        return matches
    
    def _extract_code(
        self,
        repository: Path,
        file_path: str,
        line_number: int,
        context_lines: int = 10
    ) -> Optional[Dict[str, Any]]:
        """Extract code around a specific line.
        
        Args:
            repository: Path to the git repository
            file_path: Relative path to the file in repository
            line_number: Line number to extract
            context_lines: Number of lines before and after to include
        
        Returns:
            Dictionary with code information or None if file not found
        """
        full_path = repository / file_path
        
        if not full_path.exists():
            return None
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Calculate range
            start_line = max(0, line_number - context_lines - 1)
            end_line = min(len(lines), line_number + context_lines)
            
            # Extract snippet
            snippet_lines = lines[start_line:end_line]
            snippet = ''.join(snippet_lines)
            
            # Try to extract function name
            function_name = self._extract_function_name(lines, line_number - 1)
            
            return {
                "snippet": snippet,
                "function": function_name,
                "start_line": start_line + 1,
                "end_line": end_line,
                "suspect_line": line_number
            }
        except Exception as e:
            print(f"Error reading file {full_path}: {e}")
            return None
    
    def _extract_function_name(self, lines: List[str], target_line: int) -> str:
        """Extract function name containing the target line.
        
        Args:
            lines: List of file lines
            target_line: Zero-indexed line number
        
        Returns:
            Function name or "unknown"
        """
        # Look backwards from target line for function definition
        function_patterns = [
            r'^\s*func\s+(\w+)',              # Go: func FunctionName
            r'^\s*def\s+(\w+)',               # Python: def function_name
            r'^\s*function\s+(\w+)',          # JavaScript: function functionName
            r'^\s*(\w+)\s*\([^)]*\)\s*{',    # C/C++/Java: returnType functionName()
            r'^\s*public\s+\w+\s+(\w+)\s*\(', # Java: public type method()
            r'^\s*private\s+\w+\s+(\w+)\s*\(', # Java: private type method()
        ]
        
        for i in range(target_line, max(-1, target_line - 50), -1):
            if i >= len(lines):
                continue
            line = lines[i]
            for pattern in function_patterns:
                match = re.search(pattern, line)
                if match:
                    return match.group(1)
        
        return "unknown"
    
    def _run_git_blame(
        self,
        repository: Path,
        file_path: str,
        line_number: int
    ) -> Optional[Dict[str, Any]]:
        """Run git blame on a specific line.
        
        Args:
            repository: Path to the git repository
            file_path: Relative path to the file in repository
            line_number: Line number to blame
        
        Returns:
            Dictionary with git blame information or None if failed
        """
        try:
            result = run_command(
                ["git", "blame", "-L", f"{line_number},{line_number}", file_path],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
                timeout=10
            )
            
            if result.returncode != 0:
                return None
            
            # Parse git blame output
            # Format: commit_hash (author date time line_num) code
            blame_line = result.stdout.strip()
            
            # Extract commit hash (first field)
            commit_match = re.match(r'^([0-9a-f]+)', blame_line)
            if not commit_match:
                return None
            
            commit_hash = commit_match.group(1)
            
            # Get commit details
            commit_info = self._get_commit_info(repository, commit_hash)
            
            return commit_info
        
        except (subprocess.TimeoutExpired, Exception) as e:
            print(f"Error running git blame: {e}")
            return None
    
    def _get_commit_info(self, repository: Path, commit_hash: str) -> Dict[str, Any]:
        """Get detailed commit information.
        
        Args:
            repository: Path to the git repository
            commit_hash: Commit hash to get info for
        
        Returns:
            Dictionary with commit information
        """
        try:
            # Get commit author, date, and message
            result = run_command(
                ["git", "show", "-s", "--format=%an%n%ai%n%s", commit_hash],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
                timeout=10
            )
            
            if result.returncode != 0:
                return {"commit": commit_hash}
            
            lines = result.stdout.strip().split('\n')
            
            return {
                "commit": commit_hash,
                "author": lines[0] if len(lines) > 0 else "unknown",
                "date": lines[1] if len(lines) > 1 else "unknown",
                "message": lines[2] if len(lines) > 2 else "unknown"
            }
        
        except (subprocess.TimeoutExpired, Exception):
            return {"commit": commit_hash}
    
    def _analyze_code_with_llm(
        self,
        code_info: Dict[str, Any],
        stack_trace: str,
        file_path: str = "",
        git_blame_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Analyze code with LLM to identify potential issues.
        
        Args:
            code_info: Dictionary with code snippet and context
            stack_trace: Stack trace that led to this code
            file_path: Path to the file being analyzed
            git_blame_info: Optional git blame information
        
        Returns:
            Analysis text from LLM
        """
        try:
            llm = self.get_llm()
            
            # Get user prompt template for code analysis
            prompt_template = get_user_prompt_template("code_inspector_analysis")
            
            # Infer language from file extension
            language = "unknown"
            if file_path:
                ext = Path(file_path).suffix
                language_map = {
                    ".go": "go",
                    ".py": "python",
                    ".js": "javascript",
                    ".ts": "typescript",
                    ".java": "java",
                    ".cpp": "cpp",
                    ".c": "c",
                    ".rs": "rust"
                }
                language = language_map.get(ext, "unknown")
            
            # Format git blame info
            git_blame_str = "Not available"
            if git_blame_info:
                git_blame_str = f"Author: {git_blame_info.get('author', 'unknown')}, Date: {git_blame_info.get('date', 'unknown')}, Commit: {git_blame_info.get('commit', 'unknown')}, Message: {git_blame_info.get('message', 'unknown')}"
            
            # Format prompt with code info
            user_prompt = prompt_template.format(
                file_path=file_path,
                code_snippet=code_info.get("snippet", ""),
                function_name=code_info.get("function", "unknown"),
                line_number=code_info.get("suspect_line", 0),
                language=language,
                stack_trace=stack_trace,
                git_blame=git_blame_str
            )
            
            # Get system prompt
            system_prompt = get_system_prompt("code_inspector")
            
            # Compose messages
            messages = compose_messages(system_prompt, user_prompt)
            
            # Get LLM analysis
            response = llm.complete(
                prompt=messages[-1]["content"] if messages else user_prompt,
                system_prompt=messages[0]["content"] if len(messages) > 1 else system_prompt,
                temperature=0.3,  # Lower temperature for more focused analysis
                max_tokens=500
            )
            
            return response
        
        except Exception as e:
            # Fallback to simple analysis
            return f"Error analyzing code with LLM: {e}"
    
    def _analyze_callers(
        self,
        repository: Path,
        file_path: str,
        function_name: str
    ) -> List[Dict[str, Any]]:
        """Analyze functions that call the suspect function.
        
        Args:
            repository: Path to the git repository
            file_path: Relative path to the file in repository
            function_name: Name of the function to find callers for
        
        Returns:
            List of dictionaries with caller information
        """
        callers = []
        
        if not function_name or function_name == "unknown":
            return callers
        
        # For MVP, use simple grep-based search
        # Future: Use tree-sitter for precise AST-based analysis
        try:
            result = run_command(
                ["git", "grep", "-n", function_name],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
                timeout=30
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[:10]:  # Limit to first 10 callers
                    # Format: file:line:content
                    match = re.match(r'^([^:]+):(\d+):(.*)$', line)
                    if match:
                        caller_file, caller_line, content = match.groups()
                        
                        # Skip the definition itself
                        if caller_file == file_path:
                            continue
                        
                        # Extract code context
                        code_info = self._extract_code(
                            repository,
                            caller_file,
                            int(caller_line),
                            context_lines=5
                        )
                        
                        if code_info:
                            callers.append({
                                "file": caller_file,
                                "line": int(caller_line),
                                "function": code_info.get("function", "unknown"),
                                "snippet": code_info.get("snippet", ""),
                                "analysis": f"Calls {function_name} from {caller_file}"
                            })
        
        except (subprocess.TimeoutExpired, Exception) as e:
            print(f"Error analyzing callers: {e}")
        
        return callers
