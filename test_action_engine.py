"""
test_action_engine.py — real regression tests for the tool handler layer.

Run with: python3 -m pytest test_action_engine.py -v

These test actual behavior, not mocked stubs — real file writes, real reads,
real error paths. This is the safety net for a system with broad file/bash/
git access: catches silent regressions before they touch a real repo.
"""
import os
import asyncio
import tempfile
import shutil
import pytest

from agent.core.action_engine import (
    Action, ActionNode, ActionExecutor, ActionValidator, SideEffectAnalyzer
)


@pytest.fixture
def executor():
    validator = ActionValidator()
    analyzer = SideEffectAnalyzer()
    tmp_log = tempfile.mktemp(suffix=".log")
    ex = ActionExecutor(validator, analyzer, signed_log=tmp_log)
    yield ex
    if os.path.exists(tmp_log):
        os.remove(tmp_log)


@pytest.fixture
def tmpdir_path():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def run(executor, name, target=None, **params):
    action = Action(name=name, target=target)
    node = ActionNode(action=action, parameters=params)
    return asyncio.get_event_loop().run_until_complete(
        executor._execute_with_retry(node, {})
    )


class TestWriteFile:
    def test_write_creates_file(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "out.txt")
        result = run(executor, "write_file", target=path, content="hello")
        assert result.success is True
        assert os.path.exists(path)
        assert open(path).read() == "hello"

    def test_write_no_target_fails_honestly(self, executor):
        result = run(executor, "write_file", target=None, content="x")
        assert result.success is False
        assert "no target" in result.output["error"].lower()

    def test_write_no_content_fails_honestly(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "out.txt")
        result = run(executor, "write_file", target=path)
        assert result.success is False
        assert "content" in result.output["error"].lower()


class TestReadFile:
    def test_read_existing_file(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "in.txt")
        with open(path, "w") as f:
            f.write("data123")
        result = run(executor, "read_file", target=path)
        assert result.success is True
        assert result.output["bytes_read"] == 7

    def test_read_missing_file_fails_honestly(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "nope.txt")
        result = run(executor, "read_file", target=path)
        assert result.success is False
        assert "not found" in result.output["error"].lower()


class TestEditFile:
    def test_edit_replaces_unique_match(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "code.py")
        with open(path, "w") as f:
            f.write("x = 1\ny = 2\n")
        result = run(executor, "edit_file", target=path, old_str="x = 1", new_str="x = 100")
        assert result.success is True
        assert open(path).read() == "x = 100\ny = 2\n"

    def test_edit_rejects_ambiguous_match(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "code.py")
        with open(path, "w") as f:
            f.write("x = 1\nx = 1\n")
        result = run(executor, "edit_file", target=path, old_str="x = 1", new_str="x = 2")
        assert result.success is False
        assert "matches" in result.output["error"].lower()

    def test_edit_rejects_missing_match(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "code.py")
        with open(path, "w") as f:
            f.write("x = 1\n")
        result = run(executor, "edit_file", target=path, old_str="not_here", new_str="x")
        assert result.success is False


class TestRunBash:
    def test_bash_success(self, executor):
        result = run(executor, "run_bash", command="echo hello")
        assert result.success is True
        assert "hello" in result.output["stdout"]

    def test_bash_failure_reports_real_exit_code(self, executor):
        result = run(executor, "run_bash", command="exit 1")
        assert result.success is False
        assert result.output["status_code"] == 1

    def test_bash_no_command_fails_honestly(self, executor):
        result = run(executor, "run_bash")
        assert result.success is False


class TestCompileCode:
    def test_compile_valid_python(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "valid.py")
        with open(path, "w") as f:
            f.write("x = 1 + 1\n")
        result = run(executor, "compile_code", target=path)
        assert result.success is True

    def test_compile_invalid_python_fails(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "broken.py")
        with open(path, "w") as f:
            f.write("def f(:\n")
        result = run(executor, "compile_code", target=path)
        assert result.success is False


class TestGrepSearch:
    def test_grep_finds_real_match(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "a.py")
        with open(path, "w") as f:
            f.write("import hashlib\n")
        result = run(executor, "grep_search", target=tmpdir_path, pattern="hashlib")
        assert result.success is True
        assert result.output["match_count"] >= 1

    def test_grep_no_match_still_succeeds_with_zero(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "a.py")
        with open(path, "w") as f:
            f.write("x = 1\n")
        result = run(executor, "grep_search", target=tmpdir_path, pattern="nonexistent_xyz")
        assert result.success is True
        assert result.output["match_count"] == 0


class TestGlobFind:
    def test_glob_finds_matching_files(self, executor, tmpdir_path):
        open(os.path.join(tmpdir_path, "a.py"), "w").close()
        open(os.path.join(tmpdir_path, "b.txt"), "w").close()
        result = run(executor, "glob_find", target=tmpdir_path, pattern="*.py")
        assert result.success is True
        assert result.output["match_count"] == 1


class TestTodos:
    def test_write_then_read_roundtrip(self, executor):
        result_w = run(executor, "write_todos", todos=["step 1", "step 2"])
        assert result_w.success is True
        result_r = run(executor, "read_todos")
        assert result_r.success is True
        assert result_r.output["todos"] == ["step 1", "step 2"]


class TestDeployCanaryHonesty:
    def test_deploy_canary_refuses_fake_success(self, executor):
        """The one test that matters most: unimplemented actions must fail
        loudly, never silently report success."""
        result = run(executor, "deploy_canary")
        assert result.success is False
        assert "not implemented" in result.output["error"].lower()


class TestUnknownAction:
    def test_unknown_action_fails_honestly(self, executor):
        result = run(executor, "totally_made_up_action_xyz")
        assert result.success is False
        assert "no handler" in result.output["error"].lower()


class TestWordCount:
    def test_word_count_real_file(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "a.txt")
        with open(path, "w") as f:
            f.write("one two three four")
        result = run(executor, "word_count", target=path)
        assert result.success is True
        assert result.output["words"] == 4

class TestLineCount:
    def test_line_count_real_file(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "lines.txt")
        with open(path, "w") as f:
            f.write("first line\nsecond line\nthird line\n")
        result = run(executor, "line_count", target=path)
        assert result.success is True
        assert result.output["lines"] == 3

    def test_line_count_empty_file(self, executor, tmpdir_path):
        path = os.path.join(tmpdir_path, "empty.txt")
        with open(path, "w") as f:
            f.write("")
        result = run(executor, "line_count", target=path)
        assert result.success is True
        assert result.output["lines"] == 0

    def test_line_count_missing_file(self, executor):
        result = run(executor, "line_count", target="/nonexistent/file.txt")
        assert result.success is False