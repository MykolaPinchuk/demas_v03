# team_min_chutes.py
# Steps 2-5 with Chutes.ai as the model provider.

import os
import time
import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.ui import Console

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.tools.code_execution import PythonCodeExecutionTool

# -----------------------------
# STEP 2: CHUTES credentials + endpoint
# -----------------------------
CHUTES_API_KEY = "cpk_6409376b53ff4bcda0bed0b6e71b2abe.105ceb10f63a5052bf24ac406ffcf330.9IVsa2JTvSIgVL1nUCSOCfOpBlKvcust"  # (your provided key)
CHUTES_BASE_URL = os.environ.get("CHUTES_BASE_URL", "https://llm.chutes.ai/v1")
MODEL_NAME = "openai/gpt-oss-120b"  # (your requested model)

# Optional: flip this to True to instantly scale to multiple coders (Step 4)
MULTI_CODERS = False
NUM_CODERS = 5  # used if MULTI_CODERS is True


async def try_print_stream_usage(model_client):
    """
    STEP 5 (optional): Attempt to retrieve token usage from the streamed completion.
    Not all OpenAI-compatible servers expose usage at end-of-stream; errors are ignored.
    """
    try:
        # Import only when needed to avoid hard dependency if APIs change.
        from autogen_core.models import UserMessage

        stream = model_client.create_stream(
            messages=[UserMessage(content="Say 'hi' in one word.", source="user")],
            # Many OpenAI-compatible backends support returning usage at end of stream:
            extra_create_args={"stream_options": {"include_usage": True}},
        )
        usage = None
        async for chunk in stream:
            if getattr(chunk, "usage", None):
                usage = chunk.usage
        if usage:
            print("Token usage reported by provider:", usage)
        else:
            print("Provider did not return usage in-stream (this is OK).")
    except Exception as e:
        print(f"(Usage check skipped / not supported): {e}")


async def main():
    # Ensure sandbox exists for file I/O
    os.makedirs("sandbox", exist_ok=True)

    # -----------------------------
    # STEP 3: Minimal multi-agent coding team
    # -----------------------------
    # Chutes: OpenAI-compatible client
    model = OpenAIChatCompletionClient(
        model=MODEL_NAME,
        api_key=CHUTES_API_KEY,
        base_url=CHUTES_BASE_URL,
        temperature=0.2,
        # helpful to ensure agent names are carried through some non-OpenAI backends
        include_name_in_message=True,
    )

    # Tool: allow agents to write files and run Python/commands in ./sandbox
    exec_tool = PythonCodeExecutionTool(LocalCommandLineCodeExecutor(work_dir="sandbox"))

    # Define agents
    planner = AssistantAgent("Planner", model_client=model)
    tester = AssistantAgent("Tester", model_client=model, tools=[exec_tool])

    if MULTI_CODERS:
        coders = [AssistantAgent(f"Coder{i}", model_client=model, tools=[exec_tool])
                  for i in range(NUM_CODERS)]
        team_members = [planner, *coders, tester]
        max_msgs = 60
    else:
        coder = AssistantAgent("Coder", model_client=model, tools=[exec_tool])
        team_members = [planner, coder, tester]
        max_msgs = 30

    team = RoundRobinGroupChat(
        team_members,
        termination_condition=(
            TextMentionTermination("ALL TESTS PASSED", ignore_case=True)
            | MaxMessageTermination(max_msgs)
        ),
    )

    task = """You are a team solving a tiny coding task.

Implement function sum_of_squares(nums: list[int]) -> int in a file sandbox/solution.py.
Also create sandbox/test_solution.py with pytest tests (normal + edge cases).
Use the Python execution tool to write files (Python file I/O), then run tests (e.g., `python -m pytest -q`).
Iterate until tests pass. When green, print literally: ALL TESTS PASSED.
Keep outputs concise.
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

    # -----------------------------
    # STEP 5: Optional usage/timing sanity check
    # -----------------------------
    await try_print_stream_usage(model)


if __name__ == "__main__":
    asyncio.run(main())
