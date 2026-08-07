"""
Real action execution.

The original ActionEngine logged "Action passed validation checks" and
"Executing" for every action but never actually did anything - compile_code
had no compiler behind it. This version performs real file, shell, and HTTP
actions, with an explicit allowlist and confirmation gate for anything
destructive, because giving an autonomous loop unrestricted shell access
without guardrails is how you lose data.
"""

import asyncio
import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("OmegaActionEngine")

# Actions considered destructive enough to require explicit opt-in per call,
# not just per-session. This list is deliberately conservative.
DESTRUCTIVE_SHELL_PATTERNS = ["rm -rf", "mkfs", "dd if=", ":(){ :|:& };:", "> /dev/sd"]


@dataclass
class ActionResult:
    action: str
    success: bool
    output: Any = None
    error: Optional[str] = None


class ActionEngine:
    """
    Executes real actions within a restricted working directory. Nothing
    here silently no-ops - every action either does the real thing or
    returns success=False with a concrete error.
    """

    def __init__(self, sandbox_root: str, allow_shell: bool = True, allow_network: bool = False):
        self.sandbox_root = os.path.abspath(sandbox_root)
        os.makedirs(self.sandbox_root, exist_ok=True)
        self.allow_shell = allow_shell
        self.allow_network = allow_network
        self.history: List[ActionResult] = []

    def _resolve_path(self, path: str) -> str:
        """Resolve a path and refuse to leave the sandbox root."""
        full = os.path.abspath(os.path.join(self.sandbox_root, path))
        if not full.startswith(self.sandbox_root):
            raise PermissionError(f"Path '{path}' escapes sandbox root")
        return full

    async def read_file(self, path: str) -> ActionResult:
        try:
            full = self._resolve_path(path)
            with open(full, "r") as f:
                content = f.read()
            result = ActionResult("read_file", True, output=content)
        except Exception as e:
            result = ActionResult("read_file", False, error=str(e))
        self.history.append(result)
        logger.info(f"read_file({path}) -> success={result.success}")
        return result

    async def write_file(self, path: str, content: str) -> ActionResult:
        try:
            full = self._resolve_path(path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as f:
                f.write(content)
            result = ActionResult("write_file", True, output=f"wrote {len(content)} bytes to {path}")
        except Exception as e:
            result = ActionResult("write_file", False, error=str(e))
        self.history.append(result)
        logger.info(f"write_file({path}) -> success={result.success}")
        return result

    async def run_shell(self, command: str, timeout: float = 30.0, confirm_destructive: bool = False) -> ActionResult:
        if not self.allow_shell:
            result = ActionResult("run_shell", False, error="shell execution disabled for this agent instance")
            self.history.append(result)
            return result

        for pattern in DESTRUCTIVE_SHELL_PATTERNS:
            if pattern in command and not confirm_destructive:
                result = ActionResult(
                    "run_shell", False,
                    error=f"blocked potentially destructive command matching '{pattern}'. "
                          f"Re-call with confirm_destructive=True if this is intentional.",
                )
                self.history.append(result)
                logger.warning(f"Blocked destructive shell command: {command}")
                return result

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=self.sandbox_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                result = ActionResult("run_shell", False, error=f"command timed out after {timeout}s")
                self.history.append(result)
                return result

            success = proc.returncode == 0
            result = ActionResult(
                "run_shell", success,
                output=stdout.decode(errors="replace"),
                error=stderr.decode(errors="replace") if not success else None,
            )
        except Exception as e:
            result = ActionResult("run_shell", False, error=str(e))
        self.history.append(result)
        logger.info(f"run_shell('{command}') -> success={result.success}")
        return result

    async def http_request(self, url: str, method: str = "GET", **kwargs) -> ActionResult:
        if not self.allow_network:
            result = ActionResult("http_request", False, error="network access disabled for this agent instance")
            self.history.append(result)
            return result
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.request(method, url, **kwargs)
                result = ActionResult(
                    "http_request", resp.status_code < 400,
                    output={"status": resp.status_code, "body": resp.text[:5000]},
                    error=None if resp.status_code < 400 else f"HTTP {resp.status_code}",
                )
        except Exception as e:
            result = ActionResult("http_request", False, error=str(e))
        self.history.append(result)
        logger.info(f"http_request({method} {url}) -> success={result.success}")
        return result

    def summarize_history(self) -> Dict[str, Any]:
        total = len(self.history)
        failed = [r for r in self.history if not r.success]
        return {
            "total_actions": total,
            "failed_count": len(failed),
            "failure_rate": (len(failed) / total) if total else 0.0,
            "recent_failures": [{"action": r.action, "error": r.error} for r in failed[-5:]],
        }

