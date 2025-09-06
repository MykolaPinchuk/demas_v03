## General guidelines for agent

- Do not over-engineer.
- Use rapid iterative development. Make one change, validate, then proceed. Keep iterations small to minimize risk and make progress smooth.
- Human user is a Data Scientist with a very limited SWE background. Not very bright. Communicate accordingly.
- Ask questions if unsure. Do not ask questions about low-level SWE details.
- Always keep in mind big picture. Do not lose forest for trees. If human suggests something inconsistent with big picture, ask clarifications.
- Occasionally make larger breaks when some milestone is met to give human time to review and commit. 
- Keep .gitignore up to date. Except for that, do not touch git. Human will handle git workflow.
- Be honest. If unsure, say unsure. No bullshitting.
- Human is pretty dumb. Sometimes his demands make no sense. Be ready to push back and explain things further. Human is aware of this and fine with pushback.
- Context of an agent gets filled up very fast. This forces early restarts and slows down development. Lets maintain .cursorignore (earlier called context_ignore.md) file. This file should have structure similar to .gitignore and contain files and folders which agent should not read. This should slow down filling of its context window. If you think you really need to read some file from refrenced in .cusrsorignore and you know exactly what for, go ahead and read it.
- It is very important to keep codebase maintainable, clean, and intuitive.
- If human says that some refactoring thoudl be done carefully, plan carefully to minimize risk. Use temporary thin shims if needed.
