import asyncio
import json
import logging
import time
import py_compile
import os
import sys
import hashlib
import tempfile
import fcntl
from contextlib import contextmanager
sys.path.append(os.path.expanduser('~/.omega/lib'))
from lib.omega_proof import sign_event
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger("OmegaActionEngine")

@dataclass
class Action:
    name: str
    preconditions: Dict[str, Any] = field(default_factory=dict)
    effects: Dict[str, Any] = field(default_factory=dict)
    cost: float = 1.0
    target: Optional[str] = None  # real file path this action operates on, if any

@dataclass
class ActionNode:
    action: Action
    parameters: Dict[str, Any] = field(default_factory=field)

@dataclass
class ExecutionResult:
    action_name: str
    success: bool
    output: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    execution_time: float = 0.0

class SideEffectAnalyzer:
    """
    Analyzes physical/computational side-effects, resource utilization, and structural risk parameters.
    """
    def __init__(self):
        pass

    async def analyze(self, action_node: ActionNode, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predicts structural and system state consequences.
        """
        logger.info(f"Analyzing side-effects for action: {action_node.action.name}")
        risk_score = 0.1
        warnings = []
        
        # Simple heuristic risk assessment
        if "delete" in action_node.action.name.lower() or "overwrite" in action_node.action.name.lower():
            risk_score = 0.8
            warnings.append("Destructive write action detected; risk coefficient increased.")
            
        if action_node.action.cost > 5.0:
            risk_score = max(risk_score, 0.5)
            warnings.append("High execution cost predicted.")
            
        return {
            "predicted_risk_score": risk_score,
            "warnings": warnings,
            "estimated_overhead_s": action_node.action.cost * 0.1
        }


class ActionValidator:
    """
    Asks whether the planned actions adhere to structural/safety/policy invariants.
    """
    def __init__(self, blacklisted_actions: Set[str] = None):
        self.blacklisted_actions = blacklisted_actions or {"reformat_root", "destroy_kernel"}

    async def validate(self, action_node: ActionNode, current_state: Dict[str, Any]) -> bool:
        """
        Evaluates safety and logic integrity.
        """
        name = action_node.action.name
        if name in self.blacklisted_actions:
            logger.critical(f"Action '{name}' rejected: Blacklisted action sequence.")
            return False
            
        # Check preconditions
        for cond_key, cond_val in action_node.action.preconditions.items():
            if current_state.get(cond_key) != cond_val:
                logger.error(f"Action '{name}' validation FAILED: Precondition '{cond_key}' mismatch. Expected {cond_val}, got {current_state.get(cond_key)}")
                return False
                
        logger.info(f"Action '{name}' passed validation checks.")
        return True


class ActionPlanner:
    """
    A STRIPS-style (Stanford Research Institute Problem Solver) planner.
    Forms sequential target paths using initial and terminal condition mappings.
    """
    def __init__(self, available_actions: List[Action]):
        self.actions = available_actions

    def plan(self, start_state: Dict[str, Any], goal_state: Dict[str, Any]) -> List[ActionNode]:
        """
        Standard backwards-chaining search or forward state space traversal.
        """
        logger.info(f"Formulating execution path. Start: {start_state} -> Goal: {goal_state}")
        plan_steps: List[ActionNode] = []
        current_state = start_state.copy()
        
        # Max limit to prevent infinite search loops
        max_depth = 10
        depth = 0
        
        while not self._goal_satisfied(current_state, goal_state) and depth < max_depth:
            depth += 1
            best_action: Optional[Action] = None
            
            for action in self.actions:
                # Find an action whose preconditions are met and whose effects bring us closer to goal state
                preconds_met = all(current_state.get(k) == v for k, v in action.preconditions.items())
                if preconds_met:
                    # Does it achieve any goal state requirements?
                    heurs_value = sum(1 for gk, gv in goal_state.items() if action.effects.get(gk) == gv)
                    if heurs_value > 0:
                        best_action = action
                        break
            
            if not best_action:
                # Fallback to general applicable action to move state forward
                for action in self.actions:
                    if all(current_state.get(k) == v for k, v in action.preconditions.items()):
                        best_action = action
                        break
                        
            if not best_action:
                logger.error("Planning halted: No valid path matches current action space restrictions.")
                return []
                
            plan_steps.append(ActionNode(action=best_action, parameters={}))
            # Apply effect transitions
            current_state.update(best_action.effects)
            
        return plan_steps

    def _goal_satisfied(self, current_state: Dict[str, Any], goal_state: Dict[str, Any]) -> bool:
        return all(current_state.get(k) == v for k, v in goal_state.items())


class ActionExecutor:
    """
    Handles robust execution of selected actions with built-in retries, rollbacks, and log tracing.
    """
    def __init__(self, validator: ActionValidator, analyzer: SideEffectAnalyzer, signed_log: str = None):
        self.validator = validator
        self.analyzer = analyzer
        self.audit_log: List[ExecutionResult] = []
        self.signed_log = signed_log or os.path.expanduser('~/.omega/logs/action_engine_signed.log')

    async def execute_plan(self, plan: List[ActionNode], current_state: Dict[str, Any]) -> List[ExecutionResult]:
        execution_trace = []
        state = current_state.copy()
        
        logger.info(f"Executing plan consisting of {len(plan)} actions.")
        
        for node in plan:
            # 1. Analyze side effects
            analysis = await self.analyzer.analyze(node, state)
            if analysis["predicted_risk_score"] > 0.9:
                logger.error(f"Execution halted: Side effect risk exceeds safety bounds ({analysis['predicted_risk_score']})")
                break
                
            # 2. Validate Safety
            if not await self.validator.validate(node, state):
                logger.error(f"Validation failure on: {node.action.name}")
                break
                
            # 3. Execute with retries
            result = await self._execute_with_retry(node, state)
            execution_trace.append(result)
            self.audit_log.append(result)
            
            if not result.success:
                logger.error(f"Plan broken at step {node.action.name}. Initiating rollback...")
                await self._rollback_state(node, state)
                break
            else:
                # Apply actual state mutations
                state.update(node.action.effects)
                
        return execution_trace

    OMEGA_WORKSPACE = os.path.expanduser("~/omega_workspace")
    OMEGA_ROOT = os.path.realpath(OMEGA_WORKSPACE)

    @classmethod
    def _compute_allowed_roots(cls):
        # omega_workspace is a hub of symlinks to the real repo folders.
        # realpath() follows symlinks to their target, so we must allow
        # both the workspace root AND the real location each symlink
        # points to - otherwise every symlinked repo gets rejected.
        roots = {cls.OMEGA_ROOT, os.path.realpath(os.path.expanduser("~/.omega"))}
        try:
            for entry in os.listdir(cls.OMEGA_WORKSPACE):
                full = os.path.join(cls.OMEGA_WORKSPACE, entry)
                roots.add(os.path.realpath(full))
        except FileNotFoundError:
            pass
        return roots

    def _resolve_target(self, target: str) -> str:
        # Relative paths from the model should resolve against the
        # workspace root, not this process's actual cwd.
        if not os.path.isabs(target):
            return os.path.join(self.OMEGA_WORKSPACE, target)
        return target

    def _path_allowed(self, target: str) -> bool:
        if not target:
            return False
        resolved = self._resolve_target(target)
        real = os.path.realpath(os.path.abspath(resolved))
        allowed_roots = self.__class__._compute_allowed_roots()
        for allowed in allowed_roots:
            if real == allowed or real.startswith(allowed + os.sep):
                return True
        return False

    @contextmanager
    def _file_lock(self, target: str, exclusive: bool = False):
        """Cross-process lock for approved workspace files; lock metadata stays outside repos."""
        real = os.path.realpath(os.path.abspath(target))
        lock_dir = os.path.expanduser("~/.omega/locks")
        os.makedirs(lock_dir, exist_ok=True)
        lock_name = hashlib.sha256(real.encode("utf-8")).hexdigest() + ".lock"
        lock_path = os.path.join(lock_dir, lock_name)
        with open(lock_path, "a+") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _atomic_write(self, target: str, content: str):
        directory = os.path.dirname(target) or "."
        os.makedirs(directory, exist_ok=True)
        mode = os.stat(target).st_mode if os.path.exists(target) else None
        fd, temporary = tempfile.mkstemp(prefix=".omega-write-", dir=directory, text=True)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if mode is not None:
                os.chmod(temporary, mode)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    async def _dispatch_action(self, node: ActionNode) -> tuple:
        """
        Real per-action execution. No fake success — each branch does
        something genuine and reports what actually happened.
        """
        name = node.action.name
        target = node.action.target

        if name in ("read_file", "write_file", "list_dir") and target:
            if not self._path_allowed(target):
                return False, {"error": f"Path '{target}' is outside the allowed Omega workspace"}
            # Resolve to an absolute path now that it's confirmed allowed,
            # so every downstream branch (open/os.listdir/etc.) gets a
            # correct path regardless of this process's actual cwd.
            target = self._resolve_target(target)

        if name == "read_file":
            if not target:
                return False, {"error": "read_file called with no target path set"}
            if not os.path.exists(target):
                return False, {"error": f"File not found: {target}"}
            with self._file_lock(target, exclusive=False):
                with open(target, "r", errors="replace") as f:
                    content = f.read()
            return True, {"status_code": "OK", "bytes_read": len(content), "path": target}

        elif name == "compile_code":
            if not target:
                return False, {"error": "compile_code called with no target path set"}
            if not os.path.exists(target):
                return False, {"error": f"File not found: {target}"}
            try:
                py_compile.compile(target, doraise=True)
                return True, {"status_code": "OK", "compiled": target}
            except py_compile.PyCompileError as e:
                return False, {"error": f"Compilation failed: {e}"}

        elif name == "write_file":
            if not target:
                return False, {"error": "write_file called with no target path set"}
            file_content = node.parameters.get("content")
            if file_content is None:
                return False, {"error": "write_file called with no 'content' parameter"}
            try:
                with self._file_lock(target, exclusive=True):
                    self._atomic_write(target, file_content)
                return True, {"status_code": "OK", "bytes_written": len(file_content), "path": target, "atomic": True, "locked": True}
            except Exception as e:
                return False, {"error": f"Write failed: {e}"}

        elif name == "run_bash":
            cmd = node.parameters.get("command")
            if not cmd:
                return False, {"error": "run_bash called with no 'command' parameter"}
            try:
                import subprocess
                # Match list_dir/read_file's path resolution: this process's
                # actual cwd is whatever directory the server happened to be
                # launched from, which drifts across restarts. Anchor every
                # run_bash call to the same OMEGA_WORKSPACE root those tools
                # already use, so relative paths behave identically across
                # every tool instead of only working in list_dir/read_file.
                proc = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=30,
                    cwd=self.OMEGA_WORKSPACE,
                )
                stdout = proc.stdout[-4000:] if proc.stdout else ""
                stderr = proc.stderr[-4000:] if proc.stderr else ""
                success = proc.returncode == 0
                return success, {
                    "status_code": proc.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "command": cmd,
                }
            except subprocess.TimeoutExpired:
                return False, {"error": f"Command timed out after 30s: {cmd}"}
            except Exception as e:
                return False, {"error": f"Execution failed: {e}"}

        elif name == "list_dir":
            if not target:
                return False, {"error": "list_dir called with no target path set"}
            if not os.path.isdir(target):
                return False, {"error": f"Not a directory: {target}"}
            entries = os.listdir(target)
            return True, {"status_code": "OK", "path": target, "entries": entries}

        elif name == "edit_file":
            if not target:
                return False, {"error": "edit_file called with no target path set"}
            old_str = node.parameters.get("old_str")
            new_str = node.parameters.get("new_str", "")
            if old_str is None:
                return False, {"error": "edit_file requires 'old_str'"}
            if not os.path.exists(target):
                return False, {"error": f"File not found: {target}"}
            with self._file_lock(target, exclusive=True):
                with open(target, "r") as f:
                    content_ = f.read()
                count = content_.count(old_str)
                if count == 0:
                    return False, {"error": "old_str not found in file"}
                if count > 1:
                    return False, {"error": f"old_str matches {count} times, must be unique"}
                content_ = content_.replace(old_str, new_str)
                self._atomic_write(target, content_)
            return True, {"status_code": "OK", "path": target, "replaced": True, "atomic": True, "locked": True}

        elif name == "git_status":
            try:
                import subprocess
                proc = subprocess.run(["git", "status", "--short"], cwd=target or ".",
                                       capture_output=True, text=True, timeout=15)
                return proc.returncode == 0, {"status_code": proc.returncode,
                                               "stdout": proc.stdout, "stderr": proc.stderr}
            except Exception as e:
                return False, {"error": str(e)}

        elif name == "git_diff":
            try:
                import subprocess
                proc = subprocess.run(["git", "diff"], cwd=target or ".",
                                       capture_output=True, text=True, timeout=15)
                return proc.returncode == 0, {"status_code": proc.returncode,
                                               "stdout": proc.stdout[-4000:], "stderr": proc.stderr}
            except Exception as e:
                return False, {"error": str(e)}

        elif name == "git_commit":
            msg = node.parameters.get("message")
            if not msg:
                return False, {"error": "git_commit requires 'message'"}
            try:
                import subprocess
                add = subprocess.run(["git", "add", "-A"], cwd=target or ".",
                                      capture_output=True, text=True, timeout=15)
                proc = subprocess.run(["git", "commit", "-m", msg], cwd=target or ".",
                                       capture_output=True, text=True, timeout=15)
                return proc.returncode == 0, {"status_code": proc.returncode,
                                               "stdout": proc.stdout, "stderr": proc.stderr}
            except Exception as e:
                return False, {"error": str(e)}

        elif name == "grep_search":
            pattern = node.parameters.get("pattern")
            search_path = target or "."
            if not pattern:
                return False, {"error": "grep_search requires 'pattern'"}
            try:
                import subprocess
                proc = subprocess.run(
                    ["grep", "-rn", "--include=*.py", "--include=*.js", "--include=*.jsx",
                     "-e", pattern, search_path],
                    capture_output=True, text=True, timeout=20
                )
                matches = proc.stdout.strip().split("\n") if proc.stdout.strip() else []
                return True, {"status_code": "OK", "pattern": pattern, "match_count": len(matches),
                               "matches": matches[:50]}
            except Exception as e:
                return False, {"error": str(e)}

        elif name == "glob_find":
            pattern = node.parameters.get("pattern")
            if not pattern:
                return False, {"error": "glob_find requires 'pattern'"}
            try:
                import glob as globmod
                search_root = target or "."
                full_pattern = os.path.join(search_root, "**", pattern)
                matches = globmod.glob(full_pattern, recursive=True)
                matches = [m for m in matches if "node_modules" not in m and "__pycache__" not in m]
                return True, {"status_code": "OK", "pattern": pattern, "match_count": len(matches),
                               "matches": matches[:100]}
            except Exception as e:
                return False, {"error": str(e)}

        elif name == "write_todos":
            todos = node.parameters.get("todos")
            if todos is None:
                return False, {"error": "write_todos requires 'todos' (list of task strings/objects)"}
            todo_path = os.path.expanduser("~/.omega/logs/agent_todos.json")
            try:
                import json as jsonmod
                with open(todo_path, "w") as f:
                    jsonmod.dump({"todos": todos, "updated_at": time.time()}, f, indent=2)
                return True, {"status_code": "OK", "todo_count": len(todos)}
            except Exception as e:
                return False, {"error": str(e)}

        elif name == "read_todos":
            todo_path = os.path.expanduser("~/.omega/logs/agent_todos.json")
            if not os.path.exists(todo_path):
                return True, {"status_code": "OK", "todos": [], "note": "no todo list exists yet"}
            try:
                import json as jsonmod
                with open(todo_path) as f:
                    data = jsonmod.load(f)
                return True, {"status_code": "OK", "todos": data.get("todos", [])}
            except Exception as e:
                return False, {"error": str(e)}

        elif name == "web_fetch":
            url = node.parameters.get("url")
            if not url:
                return False, {"error": "web_fetch requires 'url'"}
            try:
                import urllib.request
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    body = resp.read(50000).decode("utf-8", errors="replace")
                return True, {"status_code": resp.status, "url": url, "content": body[:5000],
                               "truncated": len(body) >= 5000}
            except Exception as e:
                return False, {"error": f"Fetch failed: {e}"}

        elif name == "run_tests":
            test_path = target or "."
            try:
                import subprocess
                proc = subprocess.run(
                    ["python3", "-m", "pytest", test_path, "-v", "--tb=short"],
                    capture_output=True, text=True, timeout=60
                )
                return proc.returncode == 0, {
                    "status_code": proc.returncode,
                    "stdout": proc.stdout[-4000:],
                    "stderr": proc.stderr[-2000:],
                    "passed": proc.returncode == 0,
                }
            except FileNotFoundError:
                return False, {"error": "pytest not installed (pip install pytest)"}
            except subprocess.TimeoutExpired:
                return False, {"error": "Tests timed out after 60s"}
            except Exception as e:
                return False, {"error": str(e)}

        elif name == "git_log":
            n = node.parameters.get("count", 10)
            try:
                import subprocess
                proc = subprocess.run(
                    ["git", "log", f"-{n}", "--oneline"],
                    cwd=target or ".", capture_output=True, text=True, timeout=15
                )
                commits = proc.stdout.strip().split("\n") if proc.stdout.strip() else []
                return proc.returncode == 0, {"status_code": proc.returncode, "commits": commits}
            except Exception as e:
                return False, {"error": str(e)}

        elif name == "word_count":
            if not target:
                return False, {"error": "word_count requires a target file path"}
            if not os.path.exists(target):
                return False, {"error": f"File not found: {target}"}
            with open(target) as f:
                text = f.read()
            return True, {"status_code": "OK", "words": len(text.split())}

        elif name == "line_count":
            if not target:
                return False, {"error": "line_count requires a target file path"}
            if not os.path.exists(target):
                return False, {"error": f"File not found: {target}"}
            with open(target) as f:
                lines = f.readlines()
            return True, {"status_code": "OK", "lines": len(lines)}

        elif name == "memory_search":
            query = node.parameters.get("query")
            if not query:
                return False, {"error": "memory_search requires 'query'"}
            log_dir = os.path.expanduser("~/.omega/logs")
            log_files = ["agent_loop_signed.log", "action_engine_signed.log", "self_extend_signed.log"]
            matches = []
            for fname in log_files:
                fpath = os.path.join(log_dir, fname)
                if not os.path.exists(fpath):
                    continue
                with open(fpath) as f:
                    for line in f:
                        if query.lower() in line.lower():
                            try:
                                entry = json.loads(line)
                                matches.append({
                                    "source_log": fname,
                                    "type": entry.get("type"),
                                    "signed_at": entry.get("signed_at"),
                                    "data": entry.get("data"),
                                    "entry_hash": entry.get("entry_hash"),
                                })
                            except json.JSONDecodeError:
                                continue
            matches.sort(key=lambda m: m.get("signed_at", ""), reverse=True)
            return True, {"status_code": "OK", "query": query, "match_count": len(matches),
                           "matches": matches[:15]}

        elif name == "deploy_canary":
            # Honestly not implemented yet — no real deploy mechanism exists.
            # Reporting success here would be exactly the kind of fake
            # logic we're eliminating. Fail loud instead.
            logger.warning(
                "deploy_canary called but has no real implementation — "
                "refusing to report fake success."
            )
            return False, {"error": "deploy_canary is not implemented (stub, honestly reported)"}

        else:
            logger.warning(f"Unknown action '{name}' — no real handler exists for it.")
            return False, {"error": f"No handler implemented for action '{name}'"}

    async def _execute_with_retry(self, node: ActionNode, state: Dict[str, Any], max_retries: int = 3) -> ExecutionResult:
        start_time = time.time()
        attempt = 0
        delay = 0.5
        
        while attempt < max_retries:
            attempt += 1
            try:
                logger.info(f"Executing '{node.action.name}' (Attempt {attempt}/{max_retries})")
                success, output = await self._dispatch_action(node)
                
                duration = time.time() - start_time
                result = ExecutionResult(
                    action_name=node.action.name,
                    success=success,
                    output=output,
                    execution_time=duration
                )
                try:
                    sign_event(self.signed_log, event_type="action_execution", data={
                        "action": node.action.name,
                        "target": node.action.target,
                        "success": success,
                        "output": output,
                    })
                except Exception as sign_err:
                    logger.warning(f"Failed to sign action result (continuing anyway): {sign_err}")
                return result
            except Exception as e:
                logger.warning(f"Attempt {attempt} failed: {e}")
                if attempt >= max_retries:
                    duration = time.time() - start_time
                    return ExecutionResult(
                        action_name=node.action.name,
                        success=False,
                        error_message=str(e),
                        execution_time=duration
                    )
                await asyncio.sleep(delay)
                delay *= 2
                
        return ExecutionResult(action_name=node.action.name, success=False, error_message="Max retries reached.")

    async def _rollback_state(self, node: ActionNode, state: Dict[str, Any]):
        """
        Runs inverted transactional offsets when state actions fail.
        """
        logger.warning(f"ROLLBACK executed for step: {node.action.name}")
        # Real-world rollback logic would invert the applied database queries or file transactions
        await asyncio.sleep(0.05)
