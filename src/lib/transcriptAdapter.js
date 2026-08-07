// Converts the raw backend transcript (assistant tool_calls + matching tool
// results, keyed by tool_call_id) into the flat "step" shape WorkspacePanel
// renders: {id, tool, title, description, status, tool_output, tool_url}.

const TOOL_CATEGORY = {
  run_bash: "terminal",
  git_status: "terminal",
  git_diff: "terminal",
  git_commit: "terminal",
  git_log: "terminal",
  run_tests: "terminal",
  compile_code: "terminal",
  read_file: "editor",
  write_file: "editor",
  edit_file: "editor",
  list_dir: "editor",
  word_count: "editor",
  web_fetch: "browser",
  grep_search: "search",
  glob_find: "search",
  memory_search: "analysis",
  propose_new_tool: "analysis",
  write_todos: "analysis",
  read_todos: "analysis",
};

function safeParseArgs(argsStr) {
  try {
    return JSON.parse(argsStr);
  } catch {
    return {};
  }
}

function formatOutput(output) {
  if (output == null) return "";
  if (typeof output === "string") return output;
  try {
    return JSON.stringify(output, null, 2).slice(0, 4000);
  } catch {
    return String(output);
  }
}

export function stepsFromTranscript(transcript) {
  if (!Array.isArray(transcript)) return [];

  const resultsById = {};
  for (const entry of transcript) {
    if (entry.role === "tool" && entry.tool_call_id) {
      resultsById[entry.tool_call_id] = entry.result;
    }
  }

  const steps = [];
  for (const entry of transcript) {
    if (entry.role !== "assistant" || !entry.tool_calls) continue;
    for (const call of entry.tool_calls) {
      const name = call.function?.name || "unknown_tool";
      const args = safeParseArgs(call.function?.arguments || "{}");
      const result = resultsById[call.id];
      const success = result ? result.success !== false : null;

      steps.push({
        id: call.id,
        tool: TOOL_CATEGORY[name] || "none",
        title: name,
        description: Object.keys(args).length
          ? Object.entries(args)
              .map(([k, v]) => `${k}: ${typeof v === "string" ? v.slice(0, 80) : JSON.stringify(v)}`)
              .join(" · ")
          : null,
        status: result == null ? "running" : success ? "completed" : "failed",
        tool_output: result
          ? result.error
            ? `Error: ${result.error}`
            : formatOutput(result.output)
          : null,
        tool_url: name === "web_fetch" ? args.url : undefined,
      });
    }
  }

  return steps;
}
