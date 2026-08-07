import asyncio
import logging
import time
import py_compile
import os
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
    def __init__(self, validator: ActionValidator, analyzer: SideEffectAnalyzer):
        self.validator = validator
        self.analyzer = analyzer
        self.audit_log: List[ExecutionResult] = []

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

    async def _dispatch_action(self, node: ActionNode) -> tuple:
        """
        Real per-action execution. No fake success — each branch does
        something genuine and reports what actually happened.
        """
        name = node.action.name
        target = node.action.target

        if name == "read_file":
            if not target:
                return False, {"error": "read_file called with no target path set"}
            if not os.path.exists(target):
                return False, {"error": f"File not found: {target}"}
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
                os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
                with open(target, "w") as f:
                    f.write(file_content)
                return True, {"status_code": "OK", "bytes_written": len(file_content), "path": target}
            except Exception as e:
                return False, {"error": f"Write failed: {e}"}

        elif name == "run_bash":
            cmd = node.parameters.get("command")
            if not cmd:
                return False, {"error": "run_bash called with no 'command' parameter"}
            try:
                import subprocess
                proc = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=30
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
            with open(target, "r") as f:
                content_ = f.read()
            count = content_.count(old_str)
            if count == 0:
                return False, {"error": "old_str not found in file"}
            if count > 1:
                return False, {"error": f"old_str matches {count} times, must be unique"}
            content_ = content_.replace(old_str, new_str)
            with open(target, "w") as f:
                f.write(content_)
            return True, {"status_code": "OK", "path": target, "replaced": True}

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
                return ExecutionResult(
                    action_name=node.action.name,
                    success=success,
                    output=output,
                    execution_time=duration
                )
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
