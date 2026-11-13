---
name: murmurent-machines
description: Show the load on every machine you can reach (this computer, the lab's servers, its clusters) by running `murmurent machines load` and printing its table as it is. `usage` shows each storage tier instead; `status` only says which machines answer. Use when a member types /murmurent-machines, or asks "how busy are the machines?", "what is the load?", "which machine is free?" and wants the numbers, not an interpretation.
disable-model-invocation: true
argument-hint: "[load|usage|status]"
allowed-tools: Bash(murmurent machines*)
---

# /murmurent-machines: the load on every machine, as a table

Mike Hallett asked for this on 2026-11-13: asking the millwright about the
machines gave a different answer every time, and he wanted "something quick to
give me back what the load is". So this skill runs one command and shows what
it printed. It does not interpret, summarise, or advise.

## What to do

1. Read the argument (`$ARGUMENTS`). It is `load` (the default when empty),
   `usage` or `status`. Anything else: say the three choices and stop.
2. Run exactly one command, in the foreground, and nothing else:

   | Argument | Command |
   |---|---|
   | `load` or none | `murmurent machines load` |
   | `usage` | `murmurent machines usage` |
   | `status` | `murmurent machines` |

   It asks every machine you have set up at the same time and takes a few
   seconds per machine (a cluster takes longest). Do not add `--json`, do not
   probe any machine yourself with `ssh`, `uptime`, `df` or `nvidia-smi`, and do
   not call the millwright.
3. Print the command's output **verbatim** in a fenced code block, the whole
   table, every row. Then stop.

   - A row that says `unreachable: <why>` stays as it is. Do not retry, do not
     try another address, do not explain it.
   - A row that says `not set up: run murmurent machine add ...` stays as it
     is: that is the one thing the person can do, and the row already says it.
   - Lines that begin `problem:` (a mistake in the lab's `policy/machines.yaml`)
     are printed too.

That is the whole skill. No paragraph before the table, no advice after it. If
the person wants it read for them (which machine to use, who to ask to free
space), that is the millwright's operation 11, and they can ask it next.

## What it reads

`murmurent machines` is described in [`docs/machines.md`](../../docs/machines.md).
The machines come from `policy/machines.yaml` in the lab records repository;
your logins come from `~/.murmurent/hosts.yaml`. Every probe is read-only,
batch-mode ssh with a timeout. The exit code is 0 even when a machine is
unreachable.
