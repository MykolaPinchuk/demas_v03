## Human-to-human notes

Never proceed beyond 65% context window, even with gpt-5. refactoring which involve creating new files and reorganization will be messy and need to be handled with at most 40% window filled. Always commit before such refactoring!

At 65% context window, stop immediately and restart.

The most important thing in agentic coding is not building and implementing new functionality. This is an easy part.

Codebase maintenance is a hard part. Thus, I should always think hard when to do codebase cleanup/refactoring and what exactly needs to be done.

Such refactorings should be prompted carefully. I should carefully think about consequences of options I pick for such refactoring.

So it is refactoring/cleaning and not intitial development which required most careful thinking.

Do such refactoring only on a fresh cpntext window. MAybe I will need the best model for them as well.

Add using venv into agent instructions. Or eveb better, add this to Cursor memories.

Ask agents how to speed up runs. As we move to fancier tests, runs will take longer. I can allocate 14/16 threads to this.





### Few things to add:


Figure out whether I can use Vertex with free tier for geminis.

Make sure token usage is reported in results. hard, tried once, abandoned.

Retries. Make sure that models receive information which they need to improve in the next attempt.

Add r1-0528 model.


