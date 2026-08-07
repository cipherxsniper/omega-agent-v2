"""
End-to-end smoke test. Uses MockLLMClient so this runs with zero network
access and zero API key - it proves the plumbing works (memory search,
hypothesis parsing, action execution, meta-cognition) before you ever
point it at a real Groq key in Termux.
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from agent.core.llm_client import MockLLMClient
from agent.core.omega_brain_v2 import OmegaBrainV2


HYPOTHESIS_RESPONSE = json.dumps({
    "hypotheses": [
        {
            "id": "write_and_verify",
            "description": "Write the requested file then read it back to verify",
            "rationale": "Verifying after write catches silent failures",
            "confidence_score": 0.9,
            "evidence": ["Standard practice for file operations"],
            "risks": ["Extra I/O overhead"],
        },
        {
            "id": "write_only",
            "description": "Write the file without verification",
            "rationale": "Faster if verification is unnecessary",
            "confidence_score": 0.6,
            "evidence": [],
            "risks": ["No confirmation the write succeeded"],
        },
    ]
})

META_SAFE_RESPONSE = json.dumps({"safe": True, "notes": "Plan only touches sandboxed files, no destructive risk."})


async def main():
    mock = MockLLMClient(canned_responses={
        "propose exactly 2": HYPOTHESIS_RESPONSE,
        "safety and soundness": META_SAFE_RESPONSE,
    })

    brain = OmegaBrainV2(sandbox_root="/data/data/com.termux/files/home/omega-agent/test_sandbox", llm=mock, allow_shell=True, allow_network=False)

    print("=== 1. Task processing (reasoning + memory + meta-cognition) ===")
    result = await brain.process_task(
        "Write a short status note to status.txt and confirm it saved correctly",
        {"priority": "normal"},
    )
    print(f"Status: {result['status']}")
    print(f"Strategy: {result['reasoning']['solution_strategy']}")
    print(f"Confidence: {result['reasoning']['confidence']}")
    print(f"Meta-cognition notes: {result['reasoning']['meta_cognition']}")
    assert result["status"] == "REASONED"
    assert result["reasoning"]["confidence"] > 0

    print("\n=== 2. Real action execution (not stubs) ===")
    write_result = await brain.actions.write_file("status.txt", "agent is online\n")
    print(f"write_file success: {write_result.success}, output: {write_result.output}")
    assert write_result.success

    read_result = await brain.actions.read_file("status.txt")
    print(f"read_file success: {read_result.success}, content: {read_result.output!r}")
    assert read_result.success and "agent is online" in read_result.output

    print("\n=== 3. Sandbox escape is blocked ===")
    escape_result = await brain.actions.read_file("../../../etc/passwd")
    print(f"escape attempt success: {escape_result.success} (should be False)")
    assert not escape_result.success

    print("\n=== 4. Destructive shell command is blocked without confirmation ===")
    danger_result = await brain.actions.run_shell("rm -rf /")
    print(f"rm -rf blocked: {not danger_result.success}, error: {danger_result.error}")
    assert not danger_result.success

    print("\n=== 5. Safe shell command actually executes ===")
    shell_result = await brain.actions.run_shell("echo hello_from_real_shell")
    print(f"shell success: {shell_result.success}, output: {shell_result.output.strip()!r}")
    assert shell_result.success and "hello_from_real_shell" in shell_result.output

    print("\n=== 6. Semantic memory recalls related-but-not-identical text ===")
    brain.memory.store("note1", "The database connection pool exhausted under load", importance=0.7)
    brain.memory.store("note2", "Unrelated: the cafeteria menu changed on Tuesday", importance=0.2)
    hits = brain.memory.search("db pool ran out of connections", top_k=2)
    print(f"Top match: {hits[0]['id']} (score={hits[0]['score']}) -- {hits[0]['content']}")
    assert hits[0]["id"] == "note1", "Semantic search should surface the related note, not exact match"

    print("\n=== 7. Meta-cognition fails closed on LLM error ===")
    broken_mock = MockLLMClient()  # no canned responses -> generic JSON without 'safe' triggers default True; test explicit error path
    from agent.core.reasoning_v2 import ReasoningEngineV2, Hypothesis
    from agent.core.semantic_memory import SemanticMemoryStore

    class ExplodingLLM:
        async def complete(self, *a, **kw):
            raise RuntimeError("simulated network failure")

    exploding_reasoning = ReasoningEngineV2(ExplodingLLM(), SemanticMemoryStore())
    fake_hyp = Hypothesis(id="x", description="d", rationale="r", confidence_score=0.9)
    safe, notes = await exploding_reasoning.meta_cognition_check(fake_hyp, "test problem")
    print(f"Fails closed on error: safe={safe} (should be False), notes={notes}")
    assert safe is False, "Meta-cognition must fail CLOSED (unsafe) when the check itself errors"

    print("\n=== ALL CHECKS PASSED ===")
    print("\nAction history summary:", brain.action_summary())


if __name__ == "__main__":
    asyncio.run(main())

