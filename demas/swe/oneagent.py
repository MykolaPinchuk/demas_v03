# Re-export the one-agent runner to keep import stability
from team_swebench_oneagent import *  # noqa: F401,F403
import asyncio as _asyncio
from team_swebench_oneagent import main as _root_main

def main() -> None:
    _asyncio.run(_root_main())

if __name__ == "__main__":
    main()


