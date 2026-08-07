"""
Reasoning engine v2: every step that used to be hardcoded now calls the LLM.

Three upgrades over the original:
  1. generate_hypotheses  - real strategies for the actual task (was 2 fixed options)
  2. chain_of_thought     - the LLM actually reasons step by step (was bookkeeping)
  3. meta_cognition_check - the LLM critiques its own plan (was a keyword match
                             on the words "unbounded"/"destructive")

All three fail loudly and honestly if the LLM call errors - no fabricated
success, matching the fallback pattern already established in the Groq patch.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent.core.llm_client import LLMClient
from agent.core.semantic_memory import SemanticMemoryStore

logger = logging.getLogger("OmegaReasoningV2")


@dataclass
class Hypothesis:
    id: str
    description: str
    rationale: str
    confidence_score: float
    evidence: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)


def _strip_fences(text: str) -> str:
    t = text.strip()
    for fence in ("```json", "```"):
        if t.startswith(fence):
            t = t[len(fence):]
        if t.endswith("```"):
            t = t[: -len("```")]
    return t.strip()


class ReasoningEngineV2:
    def __init__(self, llm: LLMClient, memory: SemanticMemoryStore):
        self.llm = llm
        self.memory = memory

    async def generate_hypotheses(self, problem: str, context: Dict[str, Any]) -> List[Hypothesis]:
        logger.info(f"Generating hypotheses for: '{problem}'")
        prompt = f"""You are a planning module for an autonomous agent. Given this task,
propose exactly 2 distinct, genuinely different strategies to accomplish it.

Task: {problem}
Context: {json.dumps(context)}

Respond ONLY with valid JSON, no other text:
{{"hypotheses": [
  {{"id": "snake_case_id", "description": "...", "rationale": "...",
    "confidence_score": 0.0, "evidence": ["..."], "risks": ["..."]}},
  {{"id": "snake_case_id", "description": "...", "rationale": "...",
    "confidence_score": 0.0, "evidence": ["..."], "risks": ["..."]}}
]}}"""
        try:
            raw = await self.llm.complete(prompt, temperature=0.4, max_tokens=700)
            parsed = json.loads(_strip_fences(raw))
            return [
                Hypothesis(
                    id=h["id"], description=h["description"], rationale=h["rationale"],
                    confidence_score=float(h["confidence_score"]),
                    evidence=h.get("evidence", []), risks=h.get("risks", []),
                )
                for h in parsed["hypotheses"]
            ]
        except Exception as e:
            logger.error(f"Hypothesis generation failed: {e}")
            return [Hypothesis(
                id="fallback_error", description="LLM call failed, no strategy generated",
                rationale=str(e), confidence_score=0.0, evidence=[], risks=["llm_unavailable"],
            )]

    def evaluate_hypotheses(self, hypotheses: List[Hypothesis]) -> Hypothesis:
        best, best_score = None, -1.0
        for h in hypotheses:
            score = h.confidence_score - len(h.risks) * 0.05 + len(h.evidence) * 0.02
            if score > best_score:
                best, best_score = h, score
        return best

    async def chain_of_thought(self, problem: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Real multi-step reasoning: retrieves relevant prior memory, generates
        and scores hypotheses, then asks the LLM to actually reason through
        the selected approach step by step - not a fixed list of log lines.
        """
        logger.info(f"Chain-of-thought for: '{problem}'")

        related = self.memory.search(problem, top_k=3)
        memory_context = "\n".join(f"- {m['content']} (relevance {m['score']})" for m in related) or "none found"

        hyps = await self.generate_hypotheses(problem, context)
        selected = self.evaluate_hypotheses(hyps)

        meta_ok, meta_notes = await self.meta_cognition_check(selected, problem)
        if not meta_ok:
            selected.confidence_score *= 0.5
            logger.warning(f"Meta-cognition flagged concerns: {meta_notes}")

        reasoning_prompt = f"""You selected this strategy: {selected.description}
Rationale: {selected.rationale}
Relevant prior context:
{memory_context}

Task: {problem}

Write out your step-by-step reasoning for how to actually execute this
strategy on this specific task. Be concrete, not generic. 3-5 steps."""

        try:
            steps_text = await self.llm.complete(reasoning_prompt, temperature=0.3, max_tokens=500)
        except Exception as e:
            steps_text = f"[reasoning generation failed: {e}]"

        self.memory.store(
            key=f"cot::{problem}"[:120],
            content=f"Task: {problem}\nStrategy: {selected.description}\nSteps: {steps_text}",
            importance=0.6,
        )

        return {
            "solution_strategy": selected.description,
            "steps": steps_text,
            "confidence": selected.confidence_score,
            "selected_hypothesis": selected,
            "meta_cognition": meta_notes,
        }

    async def meta_cognition_check(self, hypothesis: Hypothesis, problem: str) -> (bool, str):
        """
        Real self-critique via LLM, replacing the old keyword match against
        'unbounded'/'destructive' in the risks list - which would miss any
        risk phrased differently and flag any risk that happened to contain
        those substrings regardless of actual severity.
        """
        prompt = f"""Critique this plan for safety and soundness before it executes.

Task: {problem}
Selected strategy: {hypothesis.description}
Rationale: {hypothesis.rationale}
Stated risks: {hypothesis.risks}

Does this plan risk irreversible harm, data loss, or acting outside its
intended scope? Respond ONLY with JSON: {{"safe": true/false, "notes": "one sentence"}}"""
        try:
            raw = await self.llm.complete(prompt, temperature=0.0, max_tokens=150)
            parsed = json.loads(_strip_fences(raw))
            return bool(parsed.get("safe", True)), parsed.get("notes", "")
        except Exception as e:
            # Fail closed on the safety check specifically: if we can't verify
            # safety, treat as unverified rather than assuming safe.
            logger.error(f"Meta-cognition check failed: {e}")
            return False, f"meta-cognition check errored, treating as unverified: {e}"
