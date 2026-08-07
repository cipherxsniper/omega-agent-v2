"""
self_extend.py — test-gated self-extension.

The agent can propose a new tool: a handler function + a test proving it
works. Nothing is added to the live system unless:
  1. The proposed code actually compiles
  2. The proposed test actually passes against it, in isolation
  3. The full existing regression suite still passes after merging

Only then is the new handler merged into action_engine.py, and the merge
itself is signed into the proofchain with the exact code and test that
justified it — so every capability this agent ever gains is traceable to
a real, passing test, not a claim.

If any gate fails, the proposal is rejected and the rejection (with reason)
is signed too — failed self-extension attempts are part of the honest
record, not swept away.
"""
import os
import sys
import json
import subprocess
import tempfile
import shutil
import py_compile
from datetime import datetime

sys.path.append(os.path.expanduser('~/.omega/lib'))
from omega_proof import sign_event

REPO_ROOT = os.path.dirname(os.path.abspath(__file__)) + "/.."
ACTION_ENGINE_PATH = os.path.join(REPO_ROOT, "agent/core/action_engine.py")
TEST_SUITE_PATH = os.path.join(REPO_ROOT, "test_action_engine.py")
SELF_EXTEND_LOG = os.path.expanduser("~/.omega/logs/self_extend_signed.log")
SELF_EXTEND_TEST_DIR = os.path.expanduser("~/.omega/logs/self_extend_tests")


def propose_tool(handler_name, handler_code, test_code, description=""):
    """
    handler_code: a full `elif name == "...": ... ` block (string) matching
      the existing dispatch pattern in _dispatch_action.
    test_code: a full pytest test function (string) that exercises it,
      written against the SAME executor fixture pattern as test_action_engine.py.

    Returns dict: {accepted: bool, reason: str, signed_hash: str|None}
    """
    os.makedirs(SELF_EXTEND_TEST_DIR, exist_ok=True)
    attempt_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S_") + handler_name

    # Gate 1: does the proposed handler code even compile as Python?
    tmp_check = tempfile.mktemp(suffix=".py")
    with open(tmp_check, "w") as f:
        # Wrap in a dummy function so an `elif` block is syntactically valid to check
        f.write("def _dummy(name, target, node):\n")
        f.write("    if False:\n        pass\n")
        for line in handler_code.splitlines():
            f.write("    " + line + "\n")
    try:
        py_compile.compile(tmp_check, doraise=True)
    except py_compile.PyCompileError as e:
        result = {"accepted": False, "reason": f"Gate 1 failed — handler code does not compile: {e}"}
        _sign_result(attempt_id, handler_name, description, result)
        return result
    finally:
        if os.path.exists(tmp_check):
            os.remove(tmp_check)

    # Gate 2: apply to a SCRATCH COPY of action_engine.py, not the live file,
    # and run the proposed test + full existing suite against the scratch copy.
    scratch_dir = os.path.join(SELF_EXTEND_TEST_DIR, attempt_id)
    os.makedirs(scratch_dir, exist_ok=True)
    scratch_repo = os.path.join(scratch_dir, "repo")
    shutil.copytree(REPO_ROOT, scratch_repo, ignore=shutil.ignore_patterns(
        "node_modules", "__pycache__", ".git", "self_extend_tests"
    ))

    scratch_engine = os.path.join(scratch_repo, "agent/core/action_engine.py")
    with open(scratch_engine) as f:
        engine_content = f.read()

    marker = '        elif name == "deploy_canary":'
    if marker not in engine_content:
        result = {"accepted": False, "reason": "Gate 2 failed — could not find insertion point in scratch copy"}
        _sign_result(attempt_id, handler_name, description, result)
        shutil.rmtree(scratch_dir, ignore_errors=True)
        return result

    indented_handler = "\n".join("        " + l if l.strip() else l for l in handler_code.splitlines())
    engine_content = engine_content.replace(marker, indented_handler + "\n\n" + marker)
    with open(scratch_engine, "w") as f:
        f.write(engine_content)

    # Write the proposed test into a NEW test file (doesn't touch the real one yet)
    scratch_test_path = os.path.join(scratch_repo, f"test_proposed_{handler_name}.py")
    with open(scratch_test_path, "w") as f:
        f.write("import sys, os\n")
        f.write("sys.path.insert(0, os.path.dirname(__file__))\n")
        f.write(open(TEST_SUITE_PATH).read())  # reuse fixtures
        f.write("\n\n")
        f.write(test_code)

    proc = subprocess.run(
        ["python3", "-m", "pytest", scratch_test_path, "-v", "--tb=short"],
        cwd=scratch_repo, capture_output=True, text=True, timeout=60
    )

    if proc.returncode != 0:
        result = {
            "accepted": False,
            "reason": "Gate 2 failed — proposed test did not pass against scratch copy",
            "pytest_output": proc.stdout[-2000:],
        }
        _sign_result(attempt_id, handler_name, description, result)
        shutil.rmtree(scratch_dir, ignore_errors=True)
        return result

    # Gate 3: full existing regression suite must ALSO still pass on the scratch copy
    proc_full = subprocess.run(
        ["python3", "-m", "pytest", "test_action_engine.py", "-v", "--tb=short"],
        cwd=scratch_repo, capture_output=True, text=True, timeout=60
    )
    if proc_full.returncode != 0:
        result = {
            "accepted": False,
            "reason": "Gate 3 failed — new handler broke the existing regression suite",
            "pytest_output": proc_full.stdout[-2000:],
        }
        _sign_result(attempt_id, handler_name, description, result)
        shutil.rmtree(scratch_dir, ignore_errors=True)
        return result

    # All gates passed — merge into the REAL action_engine.py for real.
    with open(ACTION_ENGINE_PATH) as f:
        real_content = f.read()
    if marker not in real_content:
        result = {"accepted": False, "reason": "Live file missing insertion marker — aborting merge"}
        _sign_result(attempt_id, handler_name, description, result)
        shutil.rmtree(scratch_dir, ignore_errors=True)
        return result

    real_content = real_content.replace(marker, indented_handler + "\n\n" + marker)
    with open(ACTION_ENGINE_PATH, "w") as f:
        f.write(real_content)

    # Also append the proposed test to the real suite so future regressions catch it too
    with open(TEST_SUITE_PATH, "a") as f:
        f.write("\n\n" + test_code)

    result = {
        "accepted": True,
        "reason": "All gates passed — merged into live action_engine.py and test suite",
    }
    signed_hash = _sign_result(attempt_id, handler_name, description, result, handler_code, test_code)
    shutil.rmtree(scratch_dir, ignore_errors=True)
    result["signed_hash"] = signed_hash
    return result


def _sign_result(attempt_id, handler_name, description, result, handler_code=None, test_code=None):
    entry = sign_event(SELF_EXTEND_LOG, event_type="self_extend_attempt", data={
        "attempt_id": attempt_id,
        "handler_name": handler_name,
        "description": description,
        "accepted": result["accepted"],
        "reason": result["reason"],
        "handler_code": handler_code,
        "test_code": test_code,
    })
    return entry["entry_hash"]

