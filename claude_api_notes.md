# Claude integration research notes

## Official sources

1. Anthropic Create a Message API: https://platform.claude.com/docs/en/api/messages/create
   - Endpoint: POST /v1/messages.
   - Authentication uses the `x-api-key` header and `anthropic-version: 2023-06-01`.
   - Requests use top-level `system`, `max_tokens`, and alternating `messages` with `role` and `content`.
   - Tool definitions use Claude-native tool schemas; responses contain content blocks including `text` and potentially `tool_use`.
   - Images use content blocks with `type: image` and a source that can be `{type: base64, media_type, data}` or `{type: url, url}`.

2. Anthropic Working with Messages: https://platform.claude.com/docs/en/build-with-claude/working-with-messages
   - Messages API is stateless and accepts full conversation history.
   - The first system instruction belongs in the top-level `system` field rather than a `system` role message.
   - Claude 4.7 and later do not accept non-default temperature/top_p/top_k; the adapter should omit those sampling parameters.
   - Native response shape includes `content` blocks and `stop_reason`.

## Integration decision

Do not clone proprietary Claude Code or fabricate an Anthropic credential. Implement an optional native Anthropic Messages adapter that activates only when `ANTHROPIC_API_KEY` is configured locally or in the deployment environment. Normalize Claude text and tool-use blocks into Omega’s existing assistant message/tool_calls contract. Keep Groq and other providers as fallbacks when no Claude credential exists or Claude fails.

Creator attribution for generated work: Thomas Lee Harvey.
