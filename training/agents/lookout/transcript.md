# The exchange shown in the movie

Real reply, run on 2026-11-26 (Murmurent 2026.11.2, the lookout's instructions run on a general
agent, since the agent was new that day), by hand, on the question below. It read murmurent's own
files, every page on `docs/watch.md` and the fixed searches; there were no earlier lookout issues
to check against. The verdict line is verbatim; the detail is the first three of its ten items,
shortened to fit a frame. The whole report is issue #354. Nothing was installed or edited.

## 1
Member: lookout, what is new since 1 November 2026 that murmurent should look at?
Found 10 worth a look — Claude Code's November scheduled-task changes may have silently ended both murmurent routines; re-create them (docs/lookout.md, docs/reconcile.md).

1. Both of murmurent's timed jobs may have stopped without anyone noticing, so they need setting up again. ADOPT, small. Claude Code 2.1.329 to 2.1.332: saved scheduled tasks need scheduling again. docs/lookout.md, docs/reconcile.md.
2. A guard that crashes should refuse the write instead of letting it through; Claude Code can now do that. ADOPT, small, security guard first. New hook events. The three data-root hooks.
3. Agents could keep a tidier memory by checking their notes against what was actually said. CONSIDER, medium. "The components of agent memory" (Anthropic, 6 Nov). agents/oracle.md, docs/memory.md.
Read and set aside: Platform release notes, the skills and cookbooks, Codex 0.172.0, the MCP specification. UNRESOLVED: YouTube results pages load empty for a fetch.
