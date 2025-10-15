"""Semantic Kernel plugin for Git operations.

This plugin exposes Git operations as kernel functions that can be
automatically invoked by SK agents using FunctionChoiceBehavior.Auto().

The plugin provides annotated functions for:
- Running git blame on specific lines
- Finding files in repositories
- Extracting code context around specific lines
- Getting commit information
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

from semantic_kernel.functions import kernel_function


class GitPlugin:
    """Semantic Kernel plugin for Git operations.
    
    This plugin provides kernel functions for common Git operations used
    in code inspection and analysis, allowing SK agents to automatically
    invoke Git operations via function calling.
    
    All functions use Annotated type hints to provide SK with parameter
    descriptions for the LLM to understand how to call them.
    
    Attributes:
        repositories: List of repository paths to search
    """
    
    def __init__(self, repositories: Optional[List[str]] = None):
        """Initialize the Git plugin.
        
        Args:
            repositories: Optional list of repository paths to search.
                         Can be set later via set_repositories().
        """
        self.repositories = [Path(repo) for repo in (repositories or [])]
    
    def set_repositories(self, repositories: List[str]) -> None:
        """Set or update the list of repositories.
        
        Args:
            repositories: List of repository paths to search
        """
        self.repositories = [Path(repo) for repo in repositories]
    
    @kernel_function(
        name="git_blame",
        description="Run git blame on a specific line in a file to find who last modified it and when"
    )
    def git_blame(
        self,
        file_path: Annotated[str, "Relative path to the file within the repository"],
        line_number: Annotated[int, "Line number to run git blame on (1-indexed)"],
        repo: Annotated[str, "Absolute path to the git repository"],
    ) -> Annotated[str, "JSON string containing git blame information (commit, author, date, message)"]:
        """Run git blame on a specific line in a file.
        
        This function executes 'git blame' on the specified line and returns
        detailed commit information including the author, date, and commit message.
        
        Args:
            file_path: Relative path to the file within the repository
            line_number: Line number to blame (1-indexed)
            repo: Absolute path to the git repository
        
        Returns:
            JSON string with structure:
            {
                "success": true/false,
                "commit": "abc123...",
                "author": "John Doe",
                "date": "2024-10-15 10:30:00 -0700",
                "message": "Fix bug in payment processing",
                "file": "path/to/file.py",
                "line": 42
            }
        """
        repository = Path(repo)
        
        if not repository.exists() or not (repository / ".git").exists():
            return json.dumps({
                "success": False,
                "error": f"Repository not found or not a git repository: {repo}"
            })
        
        try:
            # Run git blame
            result = subprocess.run(
                ["git", "blame", "-L", f"{line_number},{line_number}", file_path],
                cwd=repository,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return json.dumps({
                    "success": False,
                    "error": f"git blame failed: {result.stderr.strip()}",
                    "file": file_path,
                    "line": line_number
                })
            
            # Parse git blame output
            # Format: commit_hash (author date time line_num) code
            # Note: Initial commits may have a ^ prefix
            blame_line = result.stdout.strip()
            
            # Extract commit hash (first field), handling optional ^ prefix for initial commits
            commit_match = re.match(r'^\^?([0-9a-f]+)', blame_line)
            if not commit_match:
                return json.dumps({
                    "success": False,
                    "error": "Failed to parse git blame output",
                    "output": blame_line
                })
            
            commit_hash = commit_match.group(1)
            
            # Get commit details
            commit_info = self._get_commit_info(repository, commit_hash)
            commit_info.update({
                "success": True,
                "file": file_path,
                "line": line_number
            })
            
            return json.dumps(commit_info, indent=2)
        
        except subprocess.TimeoutExpired:
            return json.dumps({
                "success": False,
                "error": "git blame timed out after 10 seconds",
                "file": file_path,
                "line": line_number
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "file": file_path,
                "line": line_number
            })
    
    @kernel_function(
        name="find_file_in_repo",
        description="Find a file by name or path in a git repository, returning all matches"
    )
    def find_file_in_repo(
        self,
        filename: Annotated[str, "File name or relative path to search for (e.g., 'payment.py' or 'src/payment.py')"],
        repo: Annotated[str, "Absolute path to the git repository to search in"],
    ) -> Annotated[str, "JSON array of matching file paths relative to the repository root"]:
        """Find a file in a git repository by name or path.
        
        This function searches for files matching the given name or path pattern.
        If the filename contains path separators, it searches for exact path matches.
        Otherwise, it recursively searches for files with matching names.
        
        Args:
            filename: File name or relative path to search for
            repo: Absolute path to the git repository
        
        Returns:
            JSON array of matching file paths (relative to repo root), or error object
        """
        repository = Path(repo)
        
        if not repository.exists() or not (repository / ".git").exists():
            return json.dumps({
                "success": False,
                "error": f"Repository not found or not a git repository: {repo}"
            })
        
        try:
            matches = []
            
            # If filename contains path separators, search for exact path
            if "/" in filename or "\\" in filename:
                full_path = repository / filename
                if full_path.exists() and full_path.is_file():
                    matches.append(filename)
            else:
                # Search for file by name recursively
                for file_path in repository.rglob(f"*{filename}"):
                    if file_path.is_file():
                        # Get path relative to repository root
                        relative_path = file_path.relative_to(repository)
                        matches.append(str(relative_path))
            
            return json.dumps({
                "success": True,
                "matches": matches,
                "count": len(matches),
                "repository": str(repository)
            }, indent=2)
        
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error searching for file: {str(e)}",
                "filename": filename,
                "repository": str(repository)
            })
    
    @kernel_function(
        name="extract_code_context",
        description="Extract code around a specific line in a file with configurable context"
    )
    def extract_code_context(
        self,
        file_path: Annotated[str, "Relative path to the file within the repository"],
        line_number: Annotated[int, "Target line number (1-indexed) to extract context around"],
        repo: Annotated[str, "Absolute path to the git repository"],
        context_lines: Annotated[int, "Number of lines before and after the target line to include (default: 10)"] = 10,
    ) -> Annotated[str, "JSON string containing code snippet, function name, and line range information"]:
        """Extract code context around a specific line.
        
        This function reads a file and extracts code around the specified line,
        including context lines before and after. It also attempts to identify
        the function containing the target line.
        
        Args:
            file_path: Relative path to the file within the repository
            line_number: Target line number (1-indexed)
            repo: Absolute path to the git repository
            context_lines: Number of lines before and after to include (default: 10)
        
        Returns:
            JSON string with structure:
            {
                "success": true/false,
                "snippet": "...code...",
                "function": "function_name",
                "start_line": 30,
                "end_line": 50,
                "suspect_line": 40,
                "file": "path/to/file.py"
            }
        """
        repository = Path(repo)
        full_path = repository / file_path
        
        if not full_path.exists():
            return json.dumps({
                "success": False,
                "error": f"File not found: {file_path}",
                "file": file_path,
                "repository": str(repository)
            })
        
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
            
            return json.dumps({
                "success": True,
                "snippet": snippet,
                "function": function_name,
                "start_line": start_line + 1,
                "end_line": end_line,
                "suspect_line": line_number,
                "file": file_path,
                "total_lines": len(lines)
            }, indent=2)
        
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error reading file: {str(e)}",
                "file": file_path,
                "repository": str(repository)
            })
    
    @kernel_function(
        name="get_commit_info",
        description="Get detailed information about a specific git commit"
    )
    def get_commit_info(
        self,
        commit_hash: Annotated[str, "Git commit hash (full or abbreviated)"],
        repo: Annotated[str, "Absolute path to the git repository"],
    ) -> Annotated[str, "JSON string containing commit information (author, date, message, files changed)"]:
        """Get detailed information about a git commit.
        
        This function retrieves comprehensive information about a commit including
        the author, date, commit message, and files changed.
        
        Args:
            commit_hash: Git commit hash (full or abbreviated)
            repo: Absolute path to the git repository
        
        Returns:
            JSON string with commit details
        """
        repository = Path(repo)
        
        if not repository.exists() or not (repository / ".git").exists():
            return json.dumps({
                "success": False,
                "error": f"Repository not found or not a git repository: {repo}"
            })
        
        commit_info = self._get_commit_info(repository, commit_hash)
        commit_info["success"] = "error" not in commit_info or commit_info.get("commit") != commit_hash
        
        return json.dumps(commit_info, indent=2)
    
    def _get_commit_info(self, repository: Path, commit_hash: str) -> Dict[str, Any]:
        """Get detailed commit information (internal helper).
        
        Args:
            repository: Path to the git repository
            commit_hash: Commit hash to get info for
        
        Returns:
            Dictionary with commit information
        """
        try:
            # Get commit author, date, and message
            result = subprocess.run(
                ["git", "show", "-s", "--format=%an%n%ai%n%s", commit_hash],
                cwd=repository,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return {
                    "commit": commit_hash,
                    "error": f"Failed to get commit info: {result.stderr.strip()}"
                }
            
            lines = result.stdout.strip().split('\n')
            
            return {
                "commit": commit_hash,
                "author": lines[0] if len(lines) > 0 else "unknown",
                "date": lines[1] if len(lines) > 1 else "unknown",
                "message": lines[2] if len(lines) > 2 else "unknown"
            }
        
        except subprocess.TimeoutExpired:
            return {
                "commit": commit_hash,
                "error": "git show timed out after 10 seconds"
            }
        except Exception as e:
            return {
                "commit": commit_hash,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def _extract_function_name(self, lines: List[str], target_line: int) -> str:
        """Extract function name containing the target line (internal helper).
        
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
