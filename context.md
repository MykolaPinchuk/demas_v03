This project is a buildig block towards Dynamic Evolutionary Multi-Agent System. The objective is to implement emergent evolutionary discovery of optimal multi-agent architecture. Its first application will be developing architecture of MAS for agentic coding. The idea is put a large set of agents  (which use different models) into framework where they can cooperate to perform a task (e.g. solving a programming problem). By keeping such framework maximally flexible, we hope to discover better MAS acritectures than using fixed predefined MAS inspired by human-centered heuristics.

Due to DEMAS compelxity, we plan to proceed iteratively developing its building blocks:
- Very basic agent harness for agentic coding tasks.
- Intergrate such basic agent (or agent team) with SWE-bench. Use only one simple problem from SWE-bench.
- Extend to 10 coding problems.
- Experiment with various models, 
- Extend a set of agent interactions to make it maximally flexible.
- Fully implement agent heterogeneity by multiple dimensions including role preferences, mindsets, collaboration prefences etc.
- Add logging and analysis of multi-agent communication and reasoning.
- Implement manual update to agent parameters before each run based on previous results.
- Implement automatic (via meta-agent?) evaluation and update to starting parameters.