## DEMAS Context and Goals (Updated)

This project is a building block towards a Dynamic Evolutionary Multi‑Agent System (DEMAS).

Objective: discover effective multi‑agent coding architectures by iterative experimentation,
starting from a fast, reproducible evaluation harness and growing toward heterogeneous teams
and automatic parameter updates.

Context: MAS are currently built using predefined architectures inspired by models of interaction which work for humans. This is likely not optimal for AI agents. Letting such agents evolve in a maximally flexible and open-ended framework will likely yield better MAS architectures.



Iterative roadmap (high level):
- Minimal harness for agentic coding tasks (Dockerized tests, ≤30s per run).
- Integrate with SWE‑bench style tasks (repo@commit + pytest selection), start with one.
- Scale to 5–10 tasks; keep runs fast and reproducible (pinned commits, small -k filters).
- Experiment with models and parameters; compare against baseline results.
- Extend agent interactions toward flexible, pluggable tools and workflows.
- Implement agent heterogeneity (roles, mindsets, collaboration preferences, toolsets).
- Add logging and analysis of multi‑agent communication and reasoning.
- Manual parameter updates based on results; then automatic (meta‑agent) updates to starting parameters.

Operational constraints:
- Python‑only targets for now.
- Provider: Chutes.
- Internet only for git clone, pip install, model calls and other essentials.

Near‑term plan is detailed in `plan.md` (what to build next, how to run it, and success criteria).