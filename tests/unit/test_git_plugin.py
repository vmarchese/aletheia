"""Unit tests for Git Plugin.

Tests for the Semantic Kernel Git plugin that provides git operations
as kernel functions for SK agents.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, mock_open

import pytest

from aletheia.plugins.git_plugin import GitPlugin


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True, capture_output=True)
    
    # Create a test file
    test_file = repo_path / "test.py"
    test_file.write_text("""def hello():
    print("hello")
    return True

def world():
    print("world")
    return False
""")
    
    # Commit the file
    subprocess.run(["git", "add", "test.py"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True, capture_output=True)
    
    return repo_path


class TestGitPluginInitialization:
    """Tests for GitPlugin initialization."""
    
    def test_init_no_repositories(self):
        """Test initialization with no repositories."""
        plugin = GitPlugin()
        assert plugin.repositories == []
    
    def test_init_with_repositories(self):
        """Test initialization with repository list."""
        repos = ["/path/to/repo1", "/path/to/repo2"]
        plugin = GitPlugin(repositories=repos)
        assert len(plugin.repositories) == 2
        assert all(isinstance(r, Path) for r in plugin.repositories)
    
    def test_set_repositories(self):
        """Test setting repositories after initialization."""
        plugin = GitPlugin()
        repos = ["/path/to/repo1"]
        plugin.set_repositories(repos)
        assert len(plugin.repositories) == 1
        assert isinstance(plugin.repositories[0], Path)


class TestGitBlame:
    """Tests for git_blame kernel function."""
    
    def test_git_blame_success(self, temp_repo):
        """Test successful git blame operation."""
        plugin = GitPlugin()
        result_json = plugin.git_blame(
            file_path="test.py",
            line_number=2,
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert result["success"] is True
        assert "commit" in result
        assert result["author"] == "Test User"
        assert result["file"] == "test.py"
        assert result["line"] == 2
        assert "Initial commit" in result["message"]
    
    def test_git_blame_invalid_repository(self):
        """Test git blame with invalid repository."""
        plugin = GitPlugin()
        result_json = plugin.git_blame(
            file_path="test.py",
            line_number=1,
            repo="/nonexistent/repo"
        )
        
        result = json.loads(result_json)
        assert result["success"] is False
        assert "not found" in result["error"].lower() or "not a git repository" in result["error"].lower()
    
    def test_git_blame_invalid_file(self, temp_repo):
        """Test git blame with nonexistent file."""
        plugin = GitPlugin()
        result_json = plugin.git_blame(
            file_path="nonexistent.py",
            line_number=1,
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert result["success"] is False
        assert "file" in result
        assert result["line"] == 1
    
    @patch('subprocess.run')
    def test_git_blame_timeout(self, mock_run, temp_repo):
        """Test git blame with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("git", 10)
        
        plugin = GitPlugin()
        result_json = plugin.git_blame(
            file_path="test.py",
            line_number=1,
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert result["success"] is False
        assert "timed out" in result["error"].lower()
    
    @patch('subprocess.run')
    def test_git_blame_parse_failure(self, mock_run, temp_repo):
        """Test git blame with unparseable output."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "invalid output format"
        mock_run.return_value = mock_result
        
        plugin = GitPlugin()
        result_json = plugin.git_blame(
            file_path="test.py",
            line_number=1,
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert result["success"] is False
        assert "parse" in result["error"].lower()
    
    @patch('subprocess.run')
    def test_git_blame_subprocess_error(self, mock_run, temp_repo):
        """Test git blame with subprocess error."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "fatal: no such file"
        mock_run.return_value = mock_result
        
        plugin = GitPlugin()
        result_json = plugin.git_blame(
            file_path="test.py",
            line_number=1,
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert result["success"] is False
        assert "git blame failed" in result["error"]


class TestFindFileInRepo:
    """Tests for find_file_in_repo kernel function."""
    
    def test_find_file_by_name(self, temp_repo):
        """Test finding file by name."""
        plugin = GitPlugin()
        result_json = plugin.find_file_in_repo(
            filename="test.py",
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert result["success"] is True
        assert result["count"] == 1
        assert "test.py" in result["matches"][0]
    
    def test_find_file_by_path(self, temp_repo):
        """Test finding file by exact path."""
        plugin = GitPlugin()
        result_json = plugin.find_file_in_repo(
            filename="test.py",
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert result["success"] is True
        assert result["count"] >= 1
    
    def test_find_file_not_found(self, temp_repo):
        """Test finding nonexistent file."""
        plugin = GitPlugin()
        result_json = plugin.find_file_in_repo(
            filename="nonexistent.py",
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert result["success"] is True
        assert result["count"] == 0
        assert result["matches"] == []
    
    def test_find_file_invalid_repository(self):
        """Test finding file in invalid repository."""
        plugin = GitPlugin()
        result_json = plugin.find_file_in_repo(
            filename="test.py",
            repo="/nonexistent/repo"
        )
        
        result = json.loads(result_json)
        assert result["success"] is False
        assert "not found" in result["error"].lower() or "not a git repository" in result["error"].lower()
    
    def test_find_file_with_subdirectory(self, temp_repo):
        """Test finding file in subdirectory."""
        # Create subdirectory with file
        subdir = temp_repo / "src"
        subdir.mkdir()
        subfile = subdir / "module.py"
        subfile.write_text("# module code")
        
        plugin = GitPlugin()
        result_json = plugin.find_file_in_repo(
            filename="module.py",
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert result["success"] is True
        assert result["count"] >= 1
        assert any("module.py" in match for match in result["matches"])
    
    def test_find_file_by_partial_path(self, temp_repo):
        """Test finding file by partial path."""
        # Create nested structure
        subdir = temp_repo / "src" / "lib"
        subdir.mkdir(parents=True)
        subfile = subdir / "utils.py"
        subfile.write_text("# utils code")
        
        plugin = GitPlugin()
        result_json = plugin.find_file_in_repo(
            filename="src/lib/utils.py",
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert result["success"] is True
        assert result["count"] >= 1


class TestExtractCodeContext:
    """Tests for extract_code_context kernel function."""
    
    def test_extract_code_success(self, temp_repo):
        """Test successful code extraction."""
        plugin = GitPlugin()
        result_json = plugin.extract_code_context(
            file_path="test.py",
            line_number=2,
            repo=str(temp_repo),
            context_lines=2
        )
        
        result = json.loads(result_json)
        assert result["success"] is True
        assert "snippet" in result
        assert "hello" in result["snippet"]
        assert result["function"] == "hello"
        assert result["suspect_line"] == 2
        assert result["file"] == "test.py"
    
    def test_extract_code_default_context(self, temp_repo):
        """Test code extraction with default context lines."""
        plugin = GitPlugin()
        result_json = plugin.extract_code_context(
            file_path="test.py",
            line_number=5,
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert result["success"] is True
        assert "snippet" in result
        # Default context is 10 lines, so should include more content
        assert len(result["snippet"]) > 0
    
    def test_extract_code_invalid_file(self, temp_repo):
        """Test code extraction with nonexistent file."""
        plugin = GitPlugin()
        result_json = plugin.extract_code_context(
            file_path="nonexistent.py",
            line_number=1,
            repo=str(temp_repo),
            context_lines=5
        )
        
        result = json.loads(result_json)
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    def test_extract_code_function_detection(self, temp_repo):
        """Test function name detection."""
        plugin = GitPlugin()
        result_json = plugin.extract_code_context(
            file_path="test.py",
            line_number=6,  # Line in "world" function
            repo=str(temp_repo),
            context_lines=2
        )
        
        result = json.loads(result_json)
        assert result["success"] is True
        assert result["function"] == "world"
    
    def test_extract_code_edge_of_file(self, temp_repo):
        """Test extraction at edge of file (first/last lines)."""
        plugin = GitPlugin()
        
        # First line
        result_json = plugin.extract_code_context(
            file_path="test.py",
            line_number=1,
            repo=str(temp_repo),
            context_lines=10
        )
        result = json.loads(result_json)
        assert result["success"] is True
        assert result["start_line"] == 1
        
        # Last line (get total lines first)
        total_lines = result["total_lines"]
        result_json = plugin.extract_code_context(
            file_path="test.py",
            line_number=total_lines,
            repo=str(temp_repo),
            context_lines=10
        )
        result = json.loads(result_json)
        assert result["success"] is True
    
    @patch("builtins.open", side_effect=IOError("Read error"))
    def test_extract_code_read_error(self, mock_file, temp_repo):
        """Test code extraction with file read error."""
        plugin = GitPlugin()
        result_json = plugin.extract_code_context(
            file_path="test.py",
            line_number=1,
            repo=str(temp_repo),
            context_lines=5
        )
        
        result = json.loads(result_json)
        assert result["success"] is False
        assert "error" in result["error"].lower()


class TestGetCommitInfo:
    """Tests for get_commit_info kernel function."""
    
    def test_get_commit_info_success(self, temp_repo):
        """Test successful commit info retrieval."""
        # Get the commit hash from the repo
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=temp_repo,
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = result.stdout.strip()
        
        plugin = GitPlugin()
        result_json = plugin.get_commit_info(
            commit_hash=commit_hash,
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert result["success"] is True
        assert result["commit"] == commit_hash
        assert result["author"] == "Test User"
        assert "Initial commit" in result["message"]
    
    def test_get_commit_info_abbreviated_hash(self, temp_repo):
        """Test commit info with abbreviated hash."""
        # Get abbreviated commit hash
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=temp_repo,
            capture_output=True,
            text=True,
            check=True
        )
        short_hash = result.stdout.strip()
        
        plugin = GitPlugin()
        result_json = plugin.get_commit_info(
            commit_hash=short_hash,
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert result["success"] is True or "error" not in result
        assert short_hash in result["commit"]
    
    def test_get_commit_info_invalid_hash(self, temp_repo):
        """Test commit info with invalid hash."""
        plugin = GitPlugin()
        result_json = plugin.get_commit_info(
            commit_hash="invalidhash123",
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        # Should return commit hash with error
        assert "error" in result or result["success"] is False
    
    def test_get_commit_info_invalid_repository(self):
        """Test commit info with invalid repository."""
        plugin = GitPlugin()
        result_json = plugin.get_commit_info(
            commit_hash="abc123",
            repo="/nonexistent/repo"
        )
        
        result = json.loads(result_json)
        assert result["success"] is False
        assert "not found" in result["error"].lower() or "not a git repository" in result["error"].lower()
    
    @patch('subprocess.run')
    def test_get_commit_info_timeout(self, mock_run, temp_repo):
        """Test commit info with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("git", 10)
        
        plugin = GitPlugin()
        result_json = plugin.get_commit_info(
            commit_hash="abc123",
            repo=str(temp_repo)
        )
        
        result = json.loads(result_json)
        assert "error" in result
        assert "timed out" in result["error"].lower()


class TestExtractFunctionName:
    """Tests for _extract_function_name helper method."""
    
    def test_extract_python_function(self):
        """Test extracting Python function name."""
        plugin = GitPlugin()
        lines = [
            "import os\n",
            "\n",
            "def my_function():\n",
            "    x = 1\n",
            "    return x\n"
        ]
        
        function = plugin._extract_function_name(lines, 3)  # Line with x = 1
        assert function == "my_function"
    
    def test_extract_go_function(self):
        """Test extracting Go function name."""
        plugin = GitPlugin()
        lines = [
            "package main\n",
            "\n",
            "func HandleRequest() {\n",
            "    fmt.Println(\"hello\")\n",
            "}\n"
        ]
        
        function = plugin._extract_function_name(lines, 3)
        assert function == "HandleRequest"
    
    def test_extract_javascript_function(self):
        """Test extracting JavaScript function name."""
        plugin = GitPlugin()
        lines = [
            "const app = express();\n",
            "\n",
            "function processData() {\n",
            "    return data;\n",
            "}\n"
        ]
        
        function = plugin._extract_function_name(lines, 3)
        assert function == "processData"
    
    def test_extract_java_function(self):
        """Test extracting Java method name."""
        plugin = GitPlugin()
        lines = [
            "public class MyClass {\n",
            "\n",
            "    public void doSomething() {\n",
            "        int x = 1;\n",
            "    }\n",
            "}\n"
        ]
        
        function = plugin._extract_function_name(lines, 3)
        assert function == "doSomething"
    
    def test_extract_function_not_found(self):
        """Test when no function is found."""
        plugin = GitPlugin()
        lines = [
            "import os\n",
            "x = 1\n",
            "y = 2\n"
        ]
        
        function = plugin._extract_function_name(lines, 2)
        assert function == "unknown"
    
    def test_extract_function_far_from_definition(self):
        """Test extraction when target is far from function definition."""
        plugin = GitPlugin()
        lines = ["def my_func():\n"] + ["    pass\n"] * 60  # 60 lines of pass
        
        # Beyond the 50-line search limit
        function = plugin._extract_function_name(lines, 55)
        assert function == "unknown"


class TestPluginIntegration:
    """Integration tests for the Git plugin."""
    
    def test_full_workflow(self, temp_repo):
        """Test a full workflow: find file, extract code, run blame."""
        plugin = GitPlugin()
        
        # 1. Find the file
        find_result = json.loads(plugin.find_file_in_repo(
            filename="test.py",
            repo=str(temp_repo)
        ))
        assert find_result["success"] is True
        assert find_result["count"] > 0
        
        file_path = find_result["matches"][0]
        
        # 2. Extract code
        extract_result = json.loads(plugin.extract_code_context(
            file_path=file_path,
            line_number=2,
            repo=str(temp_repo),
            context_lines=5
        ))
        assert extract_result["success"] is True
        assert "hello" in extract_result["snippet"]
        
        # 3. Run blame
        blame_result = json.loads(plugin.git_blame(
            file_path=file_path,
            line_number=2,
            repo=str(temp_repo)
        ))
        assert blame_result["success"] is True
        assert "commit" in blame_result
        
        # 4. Get commit info
        commit_result = json.loads(plugin.get_commit_info(
            commit_hash=blame_result["commit"],
            repo=str(temp_repo)
        ))
        assert commit_result["success"] is True or "error" not in commit_result
        assert commit_result["author"] == "Test User"
    
    def test_multiple_repositories(self, temp_repo, tmp_path):
        """Test plugin with multiple repositories."""
        # Create second repo
        repo2 = tmp_path / "repo2"
        repo2.mkdir()
        subprocess.run(["git", "init"], cwd=repo2, check=True, capture_output=True)
        
        plugin = GitPlugin(repositories=[str(temp_repo), str(repo2)])
        assert len(plugin.repositories) == 2
        
        # Can work with both repos
        result1 = json.loads(plugin.find_file_in_repo("test.py", str(temp_repo)))
        assert result1["success"] is True
        
        result2 = json.loads(plugin.find_file_in_repo("test.py", str(repo2)))
        assert result2["success"] is True  # Even if no matches, should succeed
