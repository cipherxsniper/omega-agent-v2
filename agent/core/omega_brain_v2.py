"""
OmegaBrain v2: integrates real LLM reasoning, real semantic memory, and real
action execution. This replaces the original OmegaBrain's hardcoded
hypotheses, exact-key memory, and no-op action stubs.
"""

import logging
import time
from typing import Any, Dict, Optional

from agent.core.llm_client import LLMClient, get_default_client
from agent.core.semantic_memory import SemanticMemoryStore
from agent.core.reasoning_v2 import ReasoningEngineV2
from agent.core.action_engine_v2 import ActionEngine

logger = logging.getLogger("OmegaBrainV2")


class OmegaBrainV2:
    def __init__(self, sandbox_root: str = "./omega_sandbox", llm: Optional[LLMClient] = None,
                 allow_shell: bool = True, allow_network: bool = False):
        self.llm = llm or get_default_client()
        self.memory = SemanticMemoryStore()
        self.reasoning = ReasoningEngineV2(self.llm, self.memory)
        self.actions = ActionEngine(sandbox_root, allow_shell=allow_shell, allow_network=allow_network)
        self.goals: Dict[str, Dict[str, Any]] = {}

    async def process_task(self, task_description: str, task_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        task_context = task_context or {}
        logger.info(f"Processing task: {task_description}")

        cot_result = await self.reasoning.chain_of_thought(task_description, task_context)

        goal_id = f"goal_{int(time.time() * 1000)}"
        self.goals[goal_id] = {
            "description": task_description,
            "status": "REASONED",
            "confidence": cot_result["confidence"],
        }

        return {
            "status": "REASONED",
            "reasoning": cot_result,
            "active_goal_id": goal_id,
        }

    def action_summary(self) -> Dict[str, Any]:
        return self.actions.summarize_history()

