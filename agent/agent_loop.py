"""
agent_loop.py — real agentic tool-use loop.

The model gets real tools (read_file, write_file, run_bash, compile_code) via
Groq function-calling. Each step: model responds with either a tool call or a
final answer. Tool calls are executed for real via ActionEngine's honest
dispatch handlers, results are fed back to the model, and the loop repeats
until the model stops calling tools or max_steps is hit.

Every real tool result is signed via proofchain if a signed_log path is given.
No fake success anywhere in this file — a tool either genuinely ran or the
loop reports the real error back to the model.
"""
import os
import sys
import json
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.expanduser('~/.omega/lib'))

from api.groq_client import chat_completion
from agent.core.action_engine import Action, ActionNode, ActionExecutor, ActionValidator, SideEffectAnalyzer
from omega_proof import sign_event

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the given path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path to read"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file at the given path, creating directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "Run a shell command and return its stdout/stderr/exit code.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compile_code",
            "description": "Check a Python file compiles cleanly (syntax check).",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and directories at the given path.",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace an exact unique text match in a file with new text (like find-and-replace).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_str": {"type": "string", "description": "Exact text to find, must be unique in file"},
                    "new_str": {"type": "string", "description": "Text to replace it with"},
                },
                "required": ["path", "old_str", "new_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show git status for the repo at the given directory path.",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Show git diff of unstaged changes for the repo at the given directory path.",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Stage all changes and commit with the given message, in the repo at the given directory path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "message": {"type": "string"}},
                "required": ["path", "message"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are Omega, an agentic coding assistant with real tool access. "
    "You can read files, write files, run shell commands, and check code compiles. "
    "Use tools to actually accomplish the task — never claim something is done "
    "unless a tool result confirmed it. When the task is complete, reply with a "
    "final summary and make no further tool calls."
)


async def _execute_tool_call(executor, tool_call):
    """Take one model tool_call, run it for real, return the real result dict."""
    name = tool_call["function"]["name"]
    try:
        args = json.loads(tool_call["function"]["arguments"])
    except json.JSONDecodeError as e:
        return {"error": f"Model sent malformed tool arguments: {e}"}

    action = Action(name=name, target=args.get("path"))
    node = ActionNode(action=action, parameters=args)
    result = await executor._execute_with_retry(node, {})

    return {
        "success": result.success,
        "output": result.output,
        "error": result.error_message,
    }


def run_agent_task(task_description, max_steps=10, signed_log=None, cwd_hint=None):
    """
    Runs the real tool-use loop synchronously (wraps async internals).
    Returns the full transcript: list of {step, role, content/tool_calls/tool_result}.
    """
    validator = ActionValidator()
    analyzer = SideEffectAnalyzer()
    executor = ActionExecutor(validator, analyzer)

    system = SYSTEM_PROMPT
    if cwd_hint:
        system += f" The current working directory is {cwd_hint}."

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task_description},
    ]

    transcript = []
    loop = asyncio.new_event_loop()

    try:
        for step in range(max_steps):
            message = chat_completion(
                messages,
                tools=TOOLS,
                reasoning_effort="default",
                return_message=True,
            )

            tool_calls = message.get("tool_calls")

            if not tool_calls:
                final_content = message.get("content", "")
                transcript.append({"step": step, "role": "assistant", "content": final_content, "final": True})
                if signed_log:
                    sign_event(signed_log, event_type="agent_final", data={"step": step, "content": final_content[:1000]})
                break

            messages.append(message)
            transcript.append({"step": step, "role": "assistant", "tool_calls": tool_calls})

            for tc in tool_calls:
                result = loop.run_until_complete(_execute_tool_call(executor, tc))

                if signed_log:
                    sign_event(signed_log, event_type="tool_call", data={
                        "step": step,
                        "tool": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                        "result": result,
                    })

                transcript.append({"step": step, "role": "tool", "tool_call_id": tc["id"], "result": result})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result),
                })
        else:
            transcript.append({"step": max_steps, "role": "system", "content": f"Stopped: hit max_steps ({max_steps}) without model finishing."})

    finally:
        loop.close()

    return transcript


if __name__ == "__main__":
    import sys as _sys
    task = " ".join(_sys.argv[1:]) or "List the files in the current directory using run_bash, then summarize what you see."
    log_path = os.path.expanduser("~/.omega/logs/agent_loop_signed.log")
    result = run_agent_task(task, signed_log=log_path)
    for entry in result:
        print(json.dumps(entry, indent=2, default=str))
