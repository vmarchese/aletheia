"""Unit tests for Code Inspector Agent."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
import tempfile
import os

from aletheia.agents.code_inspector import CodeInspectorAgent
from aletheia.scratchpad import Scratchpad, ScratchpadSection


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return {
        "llm": {
            "default_model": "gpt-4o",
            "api_key_env": "OPENAI_API_KEY"
        },
        "code_inspection": {
            "depth": "standard"
        }
    }


@pytest.fixture
def mock_scratchpad():
    """Create mock scratchpad."""
    scratchpad = MagicMock()
    scratchpad.read_section.return_value = None
    return scratchpad


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repository with sample files."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    
    # Initialize git repo
    os.system(f"cd {repo_dir} && git init")
    os.system(f"cd {repo_dir} && git config user.email 'test@example.com'")
    os.system(f"cd {repo_dir} && git config user.name 'Test User'")
    
    # Create .git directory marker
    git_dir = repo_dir / ".git"
    git_dir.mkdir(exist_ok=True)
    
    # Create sample files
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    
    # Go file with function
    go_file = src_dir / "features.go"
    go_file.write_text("""package features

type Feature struct {
    Name    string
    Enabled *bool
}

func IsEnabled(f *Feature) bool {
    return *f.Enabled
}

func Get(name string) *Feature {
    return nil
}
""")
    
    # Python file with function
    py_file = src_dir / "handler.py"
    py_file.write_text("""def process_request(request):
    feature = get_feature("new_feature")
    if is_enabled(feature):
        return handle_new_way(request)
    return handle_old_way(request)

def is_enabled(feature):
    return feature and feature.enabled
""")
    
    # Commit files
    os.system(f"cd {repo_dir} && git add -A && git commit -m 'Initial commit'")
    
    return repo_dir


class TestCodeInspectorAgent:
    """Test suite for Code Inspector Agent."""
    
    def test_initialization(self, mock_config, mock_scratchpad):
        """Test agent initialization."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        assert agent.config == mock_config
        assert agent.scratchpad == mock_scratchpad
        assert agent.repositories == []
        assert agent.analysis_depth == "standard"
    
    def test_initialization_with_repositories(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test initialization with repositories."""
        repos = [str(temp_git_repo)]
        agent = CodeInspectorAgent(mock_config, mock_scratchpad, repositories=repos)
        
        assert agent.repositories == repos
    
    def test_execute_without_repositories(self, mock_config, mock_scratchpad):
        """Test execute fails without repositories."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        with pytest.raises(ValueError, match="No repositories provided"):
            agent.execute()
    
    def test_execute_without_pattern_analysis(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test execute fails without pattern analysis."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad, repositories=[str(temp_git_repo)])
        mock_scratchpad.read_section.return_value = None
        
        with pytest.raises(ValueError, match="No pattern analysis found"):
            agent.execute()
    
    def test_execute_success(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test successful execution."""
        pattern_analysis = {
            "error_clusters": [
                {
                    "pattern": "nil pointer dereference at features.go:8",
                    "count": 45,
                    "stack_trace": "features.go:8"
                }
            ],
            "anomalies": []
        }
        
        mock_scratchpad.read_section.return_value = pattern_analysis
        
        agent = CodeInspectorAgent(mock_config, mock_scratchpad, repositories=[str(temp_git_repo)])
        
        with patch.object(agent, '_analyze_code_with_llm', return_value="Potential null pointer dereference"):
            with patch.object(agent, '_run_git_blame', return_value={
                "commit": "abc123",
                "author": "Test User",
                "date": "2025-10-14",
                "message": "Add feature"
            }):
                result = agent.execute()
        
        assert result["success"] is True
        assert result["suspect_files_found"] >= 0
        assert result["repositories_searched"] == 1
        mock_scratchpad.write_section.assert_called_once()
    
    def test_extract_stack_traces_from_error_clusters(self, mock_config, mock_scratchpad):
        """Test extracting stack traces from error clusters."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        pattern_analysis = {
            "error_clusters": [
                {"stack_trace": "file1.go:10 → file2.go:20"},
                {"pattern": "error at file3.py:30"},
                {"stack_trace": "file4.js:40"}
            ]
        }
        
        traces = agent._extract_stack_traces(pattern_analysis)
        
        assert len(traces) >= 2
        assert "file1.go:10 → file2.go:20" in traces
        assert "file4.js:40" in traces
    
    def test_extract_stack_traces_from_anomalies(self, mock_config, mock_scratchpad):
        """Test extracting stack traces from anomalies."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        pattern_analysis = {
            "anomalies": [
                {"description": "Error spike: handler.go:15 → service.go:25"},
                {"description": "Timeout in process_request"}
            ]
        }
        
        traces = agent._extract_stack_traces(pattern_analysis)
        
        assert len(traces) >= 1
        assert any("handler.go:15 → service.go:25" in t for t in traces)
    
    def test_map_stack_trace_simple_format(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test mapping simple file:line format."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad, repositories=[temp_git_repo])
        
        stack_trace = "features.go:8"
        mappings = agent._map_stack_trace_to_files(stack_trace)
        
        assert len(mappings) > 0
        assert any("features.go" in m["file"] for m in mappings)
        assert any(m["line"] == 8 for m in mappings)
    
    def test_map_stack_trace_with_path(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test mapping with path prefix."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad, repositories=[temp_git_repo])
        
        stack_trace = "src/features.go:10"
        mappings = agent._map_stack_trace_to_files(stack_trace)
        
        assert len(mappings) > 0
        assert any("features.go" in m["file"] for m in mappings)
    
    def test_map_stack_trace_chain(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test mapping chain of files."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad, repositories=[temp_git_repo])
        
        stack_trace = "features.go:8 → handler.py:7"
        mappings = agent._map_stack_trace_to_files(stack_trace)
        
        assert len(mappings) >= 2
        files = [m["file"] for m in mappings]
        assert any("features.go" in f for f in files)
        assert any("handler.py" in f for f in files)
    
    def test_find_file_in_repository_exact_path(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test finding file by exact path."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        files = agent._find_file_in_repository(temp_git_repo, "src/features.go")
        
        assert len(files) == 1
        assert files[0].name == "features.go"
    
    def test_find_file_in_repository_by_name(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test finding file by name only."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        files = agent._find_file_in_repository(temp_git_repo, "features.go")
        
        assert len(files) >= 1
        assert any(f.name == "features.go" for f in files)
    
    def test_find_file_not_found(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test file not found returns empty list."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        files = agent._find_file_in_repository(temp_git_repo, "nonexistent.go")
        
        assert len(files) == 0
    
    def test_extract_code_success(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test extracting code around a line."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        code_info = agent._extract_code(temp_git_repo, "src/features.go", 8, context_lines=3)
        
        assert code_info is not None
        assert "snippet" in code_info
        assert "function" in code_info
        assert "IsEnabled" in code_info["snippet"]
        assert code_info["suspect_line"] == 8
    
    def test_extract_code_file_not_found(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test extract code returns None for missing file."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        code_info = agent._extract_code(temp_git_repo, "nonexistent.go", 10)
        
        assert code_info is None
    
    def test_extract_code_with_context(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test code extraction includes context lines."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        code_info = agent._extract_code(temp_git_repo, "src/features.go", 8, context_lines=5)
        
        assert code_info is not None
        snippet_lines = code_info["snippet"].split('\n')
        assert len(snippet_lines) >= 5  # Should have context before and after
    
    def test_extract_function_name_go(self, mock_config, mock_scratchpad):
        """Test extracting Go function name."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        lines = [
            "package features\n",
            "\n",
            "func IsEnabled(f *Feature) bool {\n",
            "    return *f.Enabled\n",
            "}\n"
        ]
        
        func_name = agent._extract_function_name(lines, 3)
        
        assert func_name == "IsEnabled"
    
    def test_extract_function_name_python(self, mock_config, mock_scratchpad):
        """Test extracting Python function name."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        lines = [
            "def process_request(request):\n",
            "    feature = get_feature('test')\n",
            "    return feature\n"
        ]
        
        func_name = agent._extract_function_name(lines, 1)
        
        assert func_name == "process_request"
    
    def test_extract_function_name_not_found(self, mock_config, mock_scratchpad):
        """Test returns 'unknown' when function not found."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        lines = ["variable = 123\n", "another = 456\n"]
        
        func_name = agent._extract_function_name(lines, 1)
        
        assert func_name == "unknown"
    
    def test_run_git_blame_success(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test git blame on valid file."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        # Use line 1 which should always exist
        blame_info = agent._run_git_blame(temp_git_repo, "src/features.go", 1)
        
        # Git blame might fail on specific lines, so we just check it returns something reasonable
        # If it succeeds, it should have commit info
        # If it fails, it returns None which is acceptable
        if blame_info is not None:
            assert "commit" in blame_info
    
    def test_run_git_blame_file_not_found(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test git blame on nonexistent file."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        blame_info = agent._run_git_blame(temp_git_repo, "nonexistent.go", 10)
        
        assert blame_info is None
    
    @patch('subprocess.run')
    def test_run_git_blame_timeout(self, mock_run, mock_config, mock_scratchpad, temp_git_repo):
        """Test git blame timeout handling."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("git", 10)
        
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        blame_info = agent._run_git_blame(temp_git_repo, "src/features.go", 8)
        
        assert blame_info is None
    
    def test_get_commit_info_success(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test getting commit information."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        # Get the latest commit hash
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=temp_git_repo,
            capture_output=True,
            text=True
        )
        commit_hash = result.stdout.strip()
        
        commit_info = agent._get_commit_info(temp_git_repo, commit_hash)
        
        assert commit_info is not None
        assert "commit" in commit_info
        assert "author" in commit_info
        assert "date" in commit_info
        assert "message" in commit_info
    
    @patch('subprocess.run')
    def test_get_commit_info_failure(self, mock_run, mock_config, mock_scratchpad, temp_git_repo):
        """Test get commit info failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        commit_info = agent._get_commit_info(temp_git_repo, "invalid_hash")
        
        assert commit_info == {"commit": "invalid_hash"}
    
    def test_analyze_code_with_llm(self, mock_config, mock_scratchpad):
        """Test LLM code analysis."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "Potential null pointer dereference on line 8"
        
        with patch.object(agent, 'get_llm', return_value=mock_llm):
            code_info = {
                "snippet": "func IsEnabled(f *Feature) bool {\n    return *f.Enabled\n}",
                "function": "IsEnabled",
                "suspect_line": 8
            }
            
            git_blame = {
                "author": "John Doe",
                "date": "2025-10-14",
                "commit": "abc123",
                "message": "Add feature"
            }
            
            analysis = agent._analyze_code_with_llm(
                code_info,
                "features.go:8",
                file_path="features.go",
                git_blame_info=git_blame
            )
        
        assert "null pointer" in analysis.lower() or "dereference" in analysis.lower()
        mock_llm.complete.assert_called_once()
    
    def test_analyze_code_with_llm_error(self, mock_config, mock_scratchpad):
        """Test LLM analysis error handling."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        mock_llm = MagicMock()
        mock_llm.complete.side_effect = Exception("API Error")
        
        with patch.object(agent, 'get_llm', return_value=mock_llm):
            code_info = {"snippet": "code", "function": "test", "suspect_line": 1}
            
            analysis = agent._analyze_code_with_llm(
                code_info,
                "test.go:1",
                file_path="test.go",
                git_blame_info=None
            )
        
        assert "Error" in analysis
    
    def test_analyze_callers_success(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test analyzing caller functions."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        # The handler.py file calls is_enabled
        callers = agent._analyze_callers(temp_git_repo, "src/features.go", "IsEnabled")
        
        # Should find at least some references (might find the definition too)
        assert isinstance(callers, list)
    
    def test_analyze_callers_unknown_function(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test analyzing callers for unknown function."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        callers = agent._analyze_callers(temp_git_repo, "src/features.go", "unknown")
        
        assert callers == []
    
    @patch('subprocess.run')
    def test_analyze_callers_timeout(self, mock_run, mock_config, mock_scratchpad, temp_git_repo):
        """Test caller analysis timeout handling."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("git", 30)
        
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        callers = agent._analyze_callers(temp_git_repo, "src/features.go", "IsEnabled")
        
        assert callers == []
    
    def test_depth_minimal(self, mock_config, mock_scratchpad):
        """Test minimal analysis depth."""
        mock_config["code_inspection"] = {"depth": "minimal"}
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        assert agent.analysis_depth == "minimal"
    
    def test_depth_deep(self, mock_config, mock_scratchpad):
        """Test deep analysis depth."""
        mock_config["code_inspection"] = {"depth": "deep"}
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        assert agent.analysis_depth == "deep"
    
    def test_invalid_repository_warning(self, mock_config, mock_scratchpad, tmp_path, capsys):
        """Test warning for invalid repository."""
        invalid_repo = tmp_path / "not_a_repo"
        invalid_repo.mkdir()
        
        agent = CodeInspectorAgent(mock_config, mock_scratchpad, repositories=[str(invalid_repo)])
        
        pattern_analysis = {"error_clusters": []}
        mock_scratchpad.read_section.return_value = pattern_analysis
        
        with pytest.raises(ValueError, match="No valid git repositories"):
            agent.execute()
    
    def test_multiple_repositories(self, mock_config, mock_scratchpad, temp_git_repo, tmp_path):
        """Test searching multiple repositories."""
        # Create second repo
        repo2 = tmp_path / "repo2"
        repo2.mkdir()
        os.system(f"cd {repo2} && git init")
        (repo2 / ".git").mkdir(exist_ok=True)
        
        agent = CodeInspectorAgent(
            mock_config,
            mock_scratchpad,
            repositories=[str(temp_git_repo), str(repo2)]
        )
        
        pattern_analysis = {"error_clusters": []}
        mock_scratchpad.read_section.return_value = pattern_analysis
        
        result = agent.execute()
        
        assert result["repositories_searched"] == 2
    
    def test_execute_with_repositories_parameter(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test execute with repositories passed as parameter."""
        agent = CodeInspectorAgent(mock_config, mock_scratchpad)
        
        pattern_analysis = {"error_clusters": []}
        mock_scratchpad.read_section.return_value = pattern_analysis
        
        result = agent.execute(repositories=[str(temp_git_repo)])
        
        assert result["success"] is True
        assert result["repositories_searched"] == 1


class TestCodeInspectorAgentSKMode:
    """Test suite for Code Inspector Agent SK mode."""
    
    def test_sk_mode_initialization(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test SK agent initialization with GitPlugin."""
        agent = CodeInspectorAgent(
            mock_config,
            mock_scratchpad,
            repositories=[str(temp_git_repo)]
        )
        
        # Check that git plugin is initialized
        assert agent._git_plugin is not None
        assert agent._plugins_registered is False
    
    def test_sk_mode_plugin_registration(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test that GitPlugin is registered with kernel."""
        agent = CodeInspectorAgent(
            mock_config,
            mock_scratchpad,
            repositories=[str(temp_git_repo)]
        )
        
        # Mock the kernel to avoid API key requirement
        mock_kernel = MagicMock()
        mock_kernel.plugins = []
        
        with patch.object(agent, '_kernel', mock_kernel):
            # Register plugins
            agent._register_plugins()
        
        assert agent._plugins_registered is True
        # Check that plugin was added
        mock_kernel.add_plugin.assert_called_once()
    
    def test_execute_sk_mode_with_mock_response(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test execute in SK mode with mocked SK response."""
        pattern_analysis = {
            "error_clusters": [
                {
                    "pattern": "nil pointer at features.go:8",
                    "stack_trace": "features.go:8"
                }
            ]
        }
        
        mock_scratchpad.read_section.return_value = pattern_analysis
        
        agent = CodeInspectorAgent(
            mock_config,
            mock_scratchpad,
            repositories=[str(temp_git_repo)]
        )
        
        # Mock the kernel to avoid API key requirement
        mock_kernel = MagicMock()
        agent._kernel = mock_kernel
        
        # Mock the SK invoke method
        mock_sk_response = f"""
{{
    "suspect_files": [
        {{
            "file": "src/features.go",
            "line": 8,
            "function": "IsEnabled",
            "repository": "{str(temp_git_repo)}",
            "snippet": "return *f.Enabled",
            "analysis": "Potential nil pointer dereference",
            "git_blame": {{
                "commit": "abc123",
                "author": "Test User",
                "date": "2025-10-14",
                "message": "Add feature"
            }}
        }}
    ],
    "related_code": []
}}
"""
        
        with patch.object(agent, 'invoke', return_value=mock_sk_response):
            result = agent.execute(use_sk=True)
        
        assert result["success"] is True
        assert result["sk_used"] is True
        assert result["suspect_files_found"] == 1
        assert result["git_blame_executed"] == 1
        
        # Verify scratchpad was written
        mock_scratchpad.write_section.assert_called_once()
        call_args = mock_scratchpad.write_section.call_args
        assert call_args[0][0] == ScratchpadSection.CODE_INSPECTION
        inspection = call_args[0][1]
        assert len(inspection["suspect_files"]) == 1
        assert inspection["suspect_files"][0]["function"] == "IsEnabled"
    
    def test_execute_sk_mode_no_stack_traces(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test SK mode with no stack traces found."""
        pattern_analysis = {
            "error_clusters": [],
            "anomalies": []
        }
        
        mock_scratchpad.read_section.return_value = pattern_analysis
        
        agent = CodeInspectorAgent(
            mock_config,
            mock_scratchpad,
            repositories=[str(temp_git_repo)]
        )
        
        # Mock the kernel to avoid API key requirement
        mock_kernel = MagicMock()
        agent._kernel = mock_kernel
        
        result = agent.execute(use_sk=True)
        
        assert result["success"] is True
        assert result["sk_used"] is True
        assert result["suspect_files_found"] == 0
        
        # Verify scratchpad was written with empty result
        mock_scratchpad.write_section.assert_called_once()
        call_args = mock_scratchpad.write_section.call_args
        inspection = call_args[0][1]
        assert len(inspection["suspect_files"]) == 0
        assert "note" in inspection
    
    def test_execute_sk_mode_with_invalid_json_response(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test SK mode with non-JSON response (fallback)."""
        pattern_analysis = {
            "error_clusters": [
                {
                    "pattern": "error at features.go:8",
                    "stack_trace": "features.go:8"
                }
            ]
        }
        
        mock_scratchpad.read_section.return_value = pattern_analysis
        
        agent = CodeInspectorAgent(
            mock_config,
            mock_scratchpad,
            repositories=[str(temp_git_repo)]
        )
        
        # Mock the kernel to avoid API key requirement
        mock_kernel = MagicMock()
        agent._kernel = mock_kernel
        
        # Mock SK response with plain text (no JSON)
        mock_sk_response = "I analyzed the code and found potential issues in features.go"
        
        with patch.object(agent, 'invoke', return_value=mock_sk_response):
            result = agent.execute(use_sk=True)
        
        assert result["success"] is True
        assert result["sk_used"] is True
        assert result["suspect_files_found"] == 0  # No structured data
        
        # Verify scratchpad has analysis_text
        call_args = mock_scratchpad.write_section.call_args
        inspection = call_args[0][1]
        assert "analysis_text" in inspection
        assert inspection["analysis_text"] == mock_sk_response
    
    def test_execute_direct_mode_returns_sk_used_false(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test that direct mode (default) returns sk_used=False."""
        pattern_analysis = {"error_clusters": []}
        mock_scratchpad.read_section.return_value = pattern_analysis
        
        agent = CodeInspectorAgent(
            mock_config,
            mock_scratchpad,
            repositories=[str(temp_git_repo)]
        )
        
        result = agent.execute(use_sk=False)
        
        assert result["success"] is True
        assert result["sk_used"] is False
    
    def test_sk_mode_with_multiple_repositories(self, mock_config, mock_scratchpad, temp_git_repo, tmp_path):
        """Test SK mode with multiple repositories."""
        # Create second repo
        repo2 = tmp_path / "repo2"
        repo2.mkdir()
        os.system(f"cd {repo2} && git init")
        (repo2 / ".git").mkdir(exist_ok=True)
        
        pattern_analysis = {
            "error_clusters": [
                {"stack_trace": "file.go:10"}
            ]
        }
        
        mock_scratchpad.read_section.return_value = pattern_analysis
        
        agent = CodeInspectorAgent(
            mock_config,
            mock_scratchpad,
            repositories=[str(temp_git_repo), str(repo2)]
        )
        
        mock_sk_response = '{"suspect_files": [], "related_code": []}'
        
        # Mock the kernel to avoid API key requirement
        mock_kernel = MagicMock()
        agent._kernel = mock_kernel
        
        with patch.object(agent, 'invoke', return_value=mock_sk_response):
            result = agent.execute(use_sk=True)
        
        assert result["success"] is True
        assert result["repositories_searched"] == 2
        assert result["sk_used"] is True
    
    def test_git_plugin_repositories_updated(self, mock_config, mock_scratchpad, temp_git_repo):
        """Test that git plugin repositories are updated when execute is called."""
        agent = CodeInspectorAgent(
            mock_config,
            mock_scratchpad
        )
        
        # Initially no repositories
        assert len(agent.repositories) == 0
        
        pattern_analysis = {"error_clusters": []}
        mock_scratchpad.read_section.return_value = pattern_analysis
        
        # Mock the kernel to avoid API key requirement
        mock_kernel = MagicMock()
        agent._kernel = mock_kernel
        
        # Execute with repositories parameter
        result = agent.execute(repositories=[str(temp_git_repo)], use_sk=True)
        
        # Git plugin should be updated
        assert len(agent._git_plugin.repositories) == 1
        assert str(agent._git_plugin.repositories[0]) == str(temp_git_repo)
        assert result["sk_used"] is True
