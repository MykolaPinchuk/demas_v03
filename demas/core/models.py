"""Model registry for benchmark sweeps.

This list should include all models we want to routinely benchmark.
Edit TRACKED_MODELS to add/remove entries. The sweep tool will iterate
over this list by default.
"""

from typing import List


# Consolidated from BENCHMARKS.md and prior runs
TRACKED_MODELS: List[str] = [
    # Kimi variants
    "moonshotai/Kimi-K2-Instruct-0905",
    "moonshotai/Kimi-K2-Instruct-75k",
    "moonshotai/Kimi-Dev-72B",
    # DeepSeek
    "deepseek-ai/DeepSeek-V3.1",
    "deepseek-ai/DeepSeek-V3-0324",
    # OpenAI OSS family (proxied via provider)
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    # Qwen
    "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8",
    "Qwen/Qwen3-Coder-30B-A3B-Instruct",
    # Zhipu/GLM
    "zai-org/GLM-4.5-FP8",
    "zai-org/GLM-4.5-Air",
    # Others observed in logs
    "unsloth/gemma-3-12b-it",
]


# Default sweep parameters
DEFAULT_TEMPERATURE: float = 0.2
DEFAULT_MAX_TURNS: int = 8


