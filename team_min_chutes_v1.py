# team_min_chutes.py
# End-to-end minimal AutoGen multi-agent loop using Chutes.ai with preflight+failover.
# Python 3.10+, `pip install -U autogen-agentchat autogen-ext[openai]`

import os
import time
import asyncio
from typing import List

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.ui import Console

from autogen_core.models import UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.tools.code_execution import PythonCodeExecutionTool


# =============================
# CONFIG
# =============================
# Your Chutes key; env var takes precedence if set.
CHUTES_API_KEY = os.environ.get("CHUTES_API_KEY", "cpk_6409376b53ff4bcda0bed0b6e71b2abe.105ceb10f63a5052bf24ac406ffcf330.9IVsa2JTvSIgVL1nUCSOCfOpBlKvcust")
# Use your chute URL if you have a private one; default is shared example.
CHUTES_BASE_URL = os.environ.get("CHUTES_BASE_URL", "https://llm.chutes.ai/v1")

# Preferred model first, followed by fallbacks
PREFERRED_MODELS: List[str] = [
    "moonshotai/Kimi-K2-Instruct-75k",
    "openai/gpt-oss-120b",
    "deepseek-ai/DeepSeek-V3-0324",
    "openai/gpt-oss-20b"
]

# Minimal capability descriptor required by AutoGen for non-OpenAI model names
BASE_MODEL_INFO = {
    "vision": False,
    "function_calling": True,     # set False if your chute/model doesn't support tool calling
    "json_output": False,
    "structured_output": False,
    "family": "unknown",
}

# Toggle to quickly scale the coding team
MULTI_CODERS = False
NUM_CODERS = 5  # used if MULTI_CODERS is True


# =============================
# MODEL CLIENT + PREFLIGHT
# =============================
def make_client(model_name: str) -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model=model_name,
        api_key=CHUTES_API_KEY,
        base_url=CHUTES_BASE_URL,   # must end with /v1
        temperature=0.2,
        include_name_in_message=True,
        model_info=BASE_MODEL_INFO,
        # You can cap response length if your backend supports it:
        # extra_create_args={"max_tokens": 768},
    )

async def preflight(client: OpenAIChatCompletionClient, tries: int = 2, delay: float = 1.5) -> bool:
    """Tiny streamed request to confirm the model is actually routable."""
    for attempt in range(tries):
        try:
            stream = client.create_stream(
                messages=[UserMessage(content="hi", source="user")],
                extra_create_args={"max_tokens": 4, "stream_options": {"include_usage": True}},
            )
            async for _ in stream:
                pass
            return True
        except Exception:
            if attempt == tries - 1:
                return False
            await asyncio.sleep(delay * (2 ** attempt))
    return False

async def pick_ready_model(models: List[str]) -> OpenAIChatCompletionClient:
    for m in models:
        client = make_client(m)
        ok = await preflight(client)
        if ok:
            print(f"[preflight] Using model: {m}")
            return client
        else:
            print(f"[preflight] Model not ready: {m} -> trying next")
    raise RuntimeError("No model is currently available (all preflights failed).")


# =============================
# OPTIONAL: USAGE CHECK
# =============================
async def try_print_stream_usage(model_client: OpenAIChatCompletionClient):
    """Some OpenAI-compatible servers return usage at the end of a stream."""
    try:
        stream = model_client.create_stream(
            messages=[UserMessage(content="Say 'hi' in one word.", source="user")],
            extra_create_args={"stream_options": {"include_usage": True}, "max_tokens": 4},
        )
        usage = None
        async for chunk in stream:
            if getattr(chunk, "usage", None):
                usage = chunk.usage
        print("Token usage:", usage if usage else "(provider did not return usage in stream)")
    except Exception as e:
        print(f"(Usage check skipped): {e}")


# =============================
# MAIN
# =============================
async def main():
    os.makedirs("sandbox", exist_ok=True)

    # Build a client with preflight+failover
    model = await pick_ready_model(PREFERRED_MODELS)

    # Allow agents to write files & run Python/commands in ./sandbox
    exec_tool = PythonCodeExecutionTool(LocalCommandLineCodeExecutor(work_dir="sandbox"))

    # Agents
    planner = AssistantAgent("Planner", model_client=model)
    tester  = AssistantAgent("Tester",  model_client=model, tools=[exec_tool])

    if MULTI_CODERS:
        coders = [AssistantAgent(f"Coder{i}", model_client=model, tools=[exec_tool])
                  for i in range(NUM_CODERS)]
        members = [planner, *coders, tester]
        max_turns = 60
    else:
        coder = AssistantAgent("Coder", model_client=model, tools=[exec_tool])
        members = [planner, coder, tester]
        max_turns = 40

    # Terminate when pytest prints "X passed in Ys" (signature line), or after max_turns
    team = RoundRobinGroupChat(
        members,
        termination_condition=TextMentionTermination(" passed in ") | MaxMessageTermination(max_turns),
    )

    # No success token in the prompt (prevents false positives)
    task = """You are a team solving a tiny coding task.

    Implement function sum_of_squares(nums: list[int]) -> int in a file sandbox/solution.py.
    Also create sandbox/test_solution.py with pytest tests (cover normal and edge cases).
    Use the Python execution tool to write files (Python file I/O), then run tests with:
    python -m pytest -q
    Tester: after each run, paste ONLY the last non-empty line of pytest output.
    Iterate until tests pass. Keep outputs concise.
    """

    t0 = time.time()
    result = await Console(team.run_stream(task=task))
    dt = time.time() - t0

    print("\n--- SUMMARY ---")
    print(f"Elapsed seconds: {dt:.2f}")
    try:
        print(f"Messages exchanged: {len(result.messages)}")
    except Exception:
        pass

    await try_print_stream_usage(model)


if __name__ == "__main__":
    asyncio.run(main())
