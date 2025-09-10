# Token Usage Capture – Current Status and Policy

## What we tried
- Requesting provider-native usage (prompt/completion/total) via OpenAI-compatible clients.
- Streaming and non-streaming paths; injecting `stream_options.include_usage=true`.
- Logging usage from response objects and stream events.

## What works / doesn’t
- Some providers (e.g., OpenRouter routes we tested) do not expose tool-usage in stream events; non-stream usage is inconsistent.
- Chutes can return usage, but availability is intermittent and may be model/route dependent.
- Streaming makes UI nice but complicates usage extraction across SDKs.

## Accuracy expectations
- Native usage is billing-accurate and preferred.
- Estimates from visible messages are only suitable for rough comparisons and can undercount hidden reasoning or truncated tool outputs by 2–3× on some models.

## Policy (current)
- Benchmarks show tokens only when provider returns native usage.
- If usage is missing, token fields remain blank (not zero) and `BENCHMARKS.md` omits `tokens=`.
- No estimated tokens are surfaced in benchmarks.

## Next steps (provider-specific)
- Add a Chutes non-stream path proven to return usage consistently; fall back to stream for others.
- Gate OpenRouter models by tool-use and usage support — skip usage for routes that do not report it.
- Optional: add a separate, internal estimated-tokens report for debugging, clearly labeled as estimates.
