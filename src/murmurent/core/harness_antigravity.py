"""
Purpose: The Google Antigravity profile: where the commons go in Antigravity's
         own folders, rendered from one source and overwritten on every
         install (rule 3 of ``docs/harnesses_plan.md``). Phase 1: rules,
         skills, agents and MCP servers. Phase 2 adds the hooks.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-16
Input:   The commons (``rules/``, ``skills/``, ``agents/``,
         ``output_styles/``) and the MCP registrations.
Output:  Files under ``~/.gemini/config/``; an :class:`InstallReport` saying
         what was written, linked, skipped and what the person must know.

Every path, limit and name below was read from Antigravity's own documents
on 2026-11-16 (the App 2.32.1, its shipped guide under
``~/.gemini/antigravity/builtin/skills/agy-customizations/docs/`` and the
public pages under ``https://antigravity.google/docs/``). Each constant names
its source. Antigravity changes quickly: when something here stops matching,
the constant is the only line to change. Anything not read from a source is
marked unconfirmed in its comment.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from . import frontmatter as _fm
from .harness_policy import Event, Harness, InstallPaths, InstallReport, Installed, Profile, ToolEvent, TranscriptStore

# --- Paths (docs/hooks, docs/mcp, docs/rules, docs/skills, docs/subagents; the shipped guide) ---
CONFIG_DIR = ".gemini/config"                    # shared by the App, the IDE and the CLI
RULES_DIR = "rules"                              # ~/.gemini/config/rules/*.md, front matter `trigger`
SKILLS_DIR = "skills"                            # ~/.gemini/config/skills/<name>/SKILL.md
AGENTS_DIR = "agents"                            # ~/.gemini/config/agents/<name>.md (subagents)
MCP_FILE = "mcp_config.json"                     # {"mcpServers": {...}}, stdio: command, args, env
HOOKS_FILE = "hooks.json"                        # phase 2
APP_DATA_DIR = ".gemini/antigravity"             # the App's data folder; brain/<id>/.system_generated/logs/transcript.jsonl
CLI_DATA_DIR = ".gemini/antigravity-cli"         # the CLI's data folder, same layout
APP_BUNDLE = "/Applications/Antigravity.app"     # macOS; the App is the surface installed here
CLI_BINARY = "agy"                               # the CLI, a separate install

# --- Limits (docs/rules; the shipped rules.md) ---
RULE_FILE_LIMIT = 24_000                         # bytes per rule file, truncated past it
RULES_BUDGET_TOKENS = 20_000                     # all always-on rules together; past it, demoted to a path
BYTES_PER_TOKEN = 4                              # a rough rate for the budget warning; unconfirmed

#: What murmurent writes into the rules folder is prefixed, so an install can
#: tell its own files from the person's and overwrite only those.
PREFIX = "murmurent_"

#: Rules that are read when the model decides they apply, with the sentence
#: that lets it decide; every other rule is always on.
MODEL_DECISION: dict[str, str] = {
    "oracle_schema.md": "The front matter every oracle entry needs; read it before writing or editing an oracle or lab-oracle entry.",
}

#: Claude Code tool names and the Antigravity tool each maps to. The five
#: confirmed names come from docs/hooks (the matcher examples). The rest are
#: unconfirmed, so an agent that needs them gets no `tools` line at all
#: rather than a wrong one.
TOOL_MAP: dict[str, str] = {
    "Read": "view_file",
    "Write": "write_to_file",
    "Edit": "replace_file_content",
    "NotebookEdit": "write_to_file",
    "Bash": "run_command",
}

#: Antigravity's tool names and murmurent's kind for each (docs/hooks: the
#: five names in the matcher examples; the rest unconfirmed and left as
#: "other", which the guards allow).
KINDS: dict[str, str] = {
    "run_command": "shell",
    "write_to_file": "write",
    "replace_file_content": "edit",
    "multi_replace_file_content": "edit",
    "view_file": "read",
    "read_file": "read",          # what the App 2.32.1 recorded (transcript of 2026-11-16)
}
#: A tool name not in KINDS is classed by what its name says, in this order,
#: so a write tool murmurent has not met yet still reaches the guards (the
#: safe direction); a name that says nothing is "other", which the guards
#: allow.
KIND_HINTS: tuple[tuple[str, str], ...] = (
    ("replace", "edit"), ("edit", "edit"), ("patch", "edit"),
    ("write", "write"), ("create", "write"), ("save", "write"), ("delete", "write"), ("remove", "write"), ("move", "write"),
    ("command", "shell"), ("shell", "shell"), ("terminal", "shell"), ("exec", "shell"),
    ("read", "read"), ("view", "read"), ("open", "read"),
)
#: The argument that names the shell line (docs/hooks, confirmed) and the
#: ones that may name the file (unconfirmed: taken from the tools' common
#: lineage; the adapter also looks at every string argument that is an
#: absolute path, so a wrong key name cannot blind the guards).
COMMAND_KEY = "CommandLine"
PATH_KEYS: tuple[str, ...] = ("TargetFile", "AbsolutePath", "FilePath", "TargetPath", "Path", "file_path", "path")
CONTENT_KEYS: tuple[str, ...] = ("CodeContent", "ReplacementContent", "Content", "content")
#: The matcher for the governance hook: every tool, since a write tool under
#: a name murmurent has not met would otherwise never reach the guards.
GOVERNED_MATCHER = "*"
HOOK_NAME = "murmurent-governance"

#: The data-handling fact every install prints (the terms, Section 5, read
#: 2026-11-16). It is printed every time, not once.
DATA_WARNING = (
    "Under a personal Google sign-in, Antigravity's terms let Google keep, review and "
    "train on every interaction unless telemetry is off, and keep what it needs even "
    "then. Only a Google Cloud sign-in runs under contractual terms. Do not use it in "
    "a restricted or protected project until the PI has decided (docs/harnesses.md)."
)


def _trigger_front_matter(name: str) -> str:
    """The front matter Antigravity reads a rule by (docs/rules)."""
    if name in MODEL_DECISION:
        return f"---\ntrigger: model_decision\ndescription: {MODEL_DECISION[name]}\n---\n\n"
    return "---\ntrigger: always_on\n---\n\n"


class AntigravityProfile(Profile):
    """Google Antigravity: the App on a Mac today; the CLI reads the same config."""

    facts = Harness(
        name="antigravity",
        description="Google Antigravity (the App, the IDE or the agy CLI); runs Gemini and Claude models",
        place="google_personal",
        # The model list of 2026-11-16 (docs/models); it changes often and is
        # never trusted from here.
        models=("gemini-4-carbon", "gemini-4-argon", "gemini-4-hydrogen", "gemini-3.8-flash",
                "claude-opus-5-5", "claude-sonnet-5-5"),
        hooks_can_deny=True,
        headless="agy -p",
    )

    # --- where ---------------------------------------------------------------

    def config_dir(self, home: Path) -> Path:
        return home / CONFIG_DIR

    def install_paths(self, home: Path) -> InstallPaths:
        cfg = self.config_dir(home)
        return InstallPaths(
            mcp=cfg / MCP_FILE,
            rules=cfg / RULES_DIR,
            skills=cfg / SKILLS_DIR,
            agents=cfg / AGENTS_DIR,
            hooks=cfg / HOOKS_FILE,
        )

    def present(self, home: Path) -> bool:
        return (
            Path(APP_BUNDLE).is_dir()
            or (home / APP_DATA_DIR).is_dir()
            or (home / CLI_DATA_DIR).is_dir()
            or shutil.which(CLI_BINARY) is not None
        )

    def installed(self, home: Path) -> Installed:
        paths = self.install_paths(home)
        assert paths.rules is not None and paths.mcp is not None and paths.skills is not None
        missing: list[str] = []
        if not any(paths.rules.glob(f"{PREFIX}*.md")) if paths.rules.is_dir() else True:
            missing.append(f"no murmurent rules in {paths.rules}")
        try:
            data = json.loads(paths.mcp.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError):
            data = {}
        if not any(str(k).startswith("murmurent") for k in (data.get("mcpServers") or {})):
            missing.append(f"no murmurent MCP servers in {paths.mcp}")
        if not (paths.skills.is_dir() and any(p.name.startswith("murmurent") for p in paths.skills.iterdir())):
            missing.append(f"no murmurent skills in {paths.skills}")
        assert paths.hooks is not None
        try:
            hooks = json.loads(paths.hooks.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError):
            hooks = {}
        if HOOK_NAME not in hooks:
            missing.append(f"no governance hooks in {paths.hooks}")
        if missing:
            return Installed(False, "; ".join(missing) + " (run: murmurent install --harness antigravity)")
        return Installed(True, "rules, skills, MCP servers and the governance hooks in place")

    def headless_command(self, prompt: str, model: str, cwd: Path) -> list[str] | None:
        cmd = [CLI_BINARY, "-p", prompt]
        if model:
            cmd += ["--model", model]
        return cmd

    def transcript_stores(self, home: Path) -> list[TranscriptStore]:
        pattern = "brain/*/.system_generated/logs/transcript.jsonl"
        return [
            TranscriptStore(harness=self.facts.name, root=home / APP_DATA_DIR, pattern=pattern),
            TranscriptStore(harness=self.facts.name, root=home / CLI_DATA_DIR, pattern=pattern),
        ]

    # --- the session record (phase 4) ------------------------------------------

    def read_events(self, path: Path):
        """Every tool call in one Antigravity conversation transcript
        (``brain/<id>/.system_generated/logs/transcript.jsonl``), as an
        :class:`Event`. Read from the App 2.32.1's own files on 2026-11-16:
        one JSON object per step; a ``PLANNER_RESPONSE`` step carries
        ``tool_calls``, each ``{"name", "args"}``, and ``created_at``. The
        transcript names no model; the row's model is empty."""
        from .harness_policy import summarise

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        session = path.parents[2].name if len(path.parents) > 2 else path.stem
        for line in lines:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(d, dict):
                continue
            for call in d.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                yield Event(
                    t=str(d.get("created_at") or ""),
                    harness=self.facts.name,
                    model="",
                    place=self.facts.place,
                    session=session,
                    project="",
                    repo="",
                    tool=str(call.get("name") or ""),
                    summary=summarise(call.get("args")),
                    decision="",
                )

    # --- the hook contract (phase 2) --------------------------------------------

    def to_event(self, payload: dict[str, Any]) -> ToolEvent:
        call = payload.get("toolCall") or {}
        name = str(call.get("name") or "")
        args = call.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        kind = KINDS.get(name) or next((k for hint, k in KIND_HINTS if hint in name.lower()), "other")
        path = next((str(args[k]) for k in PATH_KEYS if args.get(k)), "")
        if not path and kind in ("write", "edit", "read"):
            # A key name we did not expect: take the first absolute path among
            # the arguments rather than see nothing.
            path = next((v for v in args.values() if isinstance(v, str) and v.startswith("/")), "")
        content = next((str(args[k]) for k in CONTENT_KEYS if args.get(k)), "")
        return ToolEvent(
            harness=self.facts.name,
            session=str(payload.get("conversationId") or ""),
            cwd=str(payload.get("cwd") or (payload.get("workspacePaths") or [""])[0] or ""),
            tool=kind,
            tool_name=name,
            command=(str(args.get(COMMAND_KEY)
                         or next((v for k, v in args.items() if isinstance(v, str) and ("command" in k.lower() or "cmd" in k.lower())), "")
                         or next((v for v in args.values() if isinstance(v, str)), ""))
                     if kind == "shell" else ""),
            path=path,
            content=content,
            raw=payload,
        )

    def from_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        """Antigravity's PreToolUse answer. A deny is a hard block. For allow
        the adapter says nothing (``{}``), so Antigravity's own permission
        rules still apply; an explicit ``allow`` would auto-approve the call
        and widen what the agent may do. (That ``{}`` means "no opinion" is
        how the docs' PostToolUse contract reads; for PreToolUse it is
        unconfirmed and is what the by-hand check of phase 2 verifies.)"""
        if decision.get("decision") != "deny":
            return {}
        return {"decision": "deny", "reason": decision.get("reason", "")}

    def hook_config(self, home: Path) -> RenderedFileList:
        """``hooks.json`` with murmurent's named hook merged in; every other
        named hook the person has is kept."""
        import sys

        target = self.install_paths(home).hooks
        assert target is not None
        data: dict[str, Any] = {}
        if target.is_file():
            try:
                data = json.loads(target.read_text(encoding="utf-8") or "{}")
            except json.JSONDecodeError:
                data = {}
        # The App is started from the Dock, with none of the shell's variables,
        # so the data root the guards protect is written into the command the
        # way Claude Code's hooks carry their own settings. Read at install
        # time; re-run the install when it changes.
        import os
        import shlex

        root = os.environ.get("MURMURENT_DATA_ROOT") or os.environ.get("MURMURENT_LAB_VM_ROOT") or ""
        prefix = f"MURMURENT_DATA_ROOT={shlex.quote(root)} " if root else ""
        adapter = f"{prefix}{sys.executable} -m murmurent.hooks.adapter --harness antigravity"
        data[HOOK_NAME] = {
            "PreToolUse": [{"matcher": GOVERNED_MATCHER,
                            "hooks": [{"type": "command", "command": f"{adapter} --event PreToolUse", "timeout": 20}]}],
            "PostToolUse": [{"matcher": "*",
                             "hooks": [{"type": "command", "command": f"{adapter} --event PostToolUse", "timeout": 20}]}],
            "SessionStart": [{"type": "command", "command": f"{adapter} --event SessionStart", "timeout": 20}],
            "PreInvocation": [{"type": "command", "command": f"{adapter} --event PreInvocation", "timeout": 20}],
        }
        return RenderedFileList(target, json.dumps(data, indent=2) + "\n", None)

    # --- rendering -------------------------------------------------------------

    def render_rules(self, rules: list[Path], home: Path) -> list[RenderedFileList]:
        """Each rule file becomes ``rules/murmurent_<name>.md`` with a trigger
        front matter. A file past Antigravity's per-file limit is not
        rendered (it would be truncated silently); the report says so."""
        out: list[RenderedFileList] = []
        folder = self.install_paths(home).rules
        assert folder is not None
        for src in rules:
            text = src.read_text(encoding="utf-8")
            rendered = _trigger_front_matter(src.name) + text
            size = len(rendered.encode("utf-8"))
            if size > RULE_FILE_LIMIT:
                out.append(RenderedFileList(folder / f"{PREFIX}{src.name}", "", src,
                                            skipped=f"{src.name} is {size:,} bytes, over Antigravity's "
                                                    f"{RULE_FILE_LIMIT:,}-byte limit for one rule file; it would be cut off"))
                continue
            out.append(RenderedFileList(folder / f"{PREFIX}{src.name}", rendered, src))
        return out

    def render_agents(self, agents: list[Path], home: Path) -> list[RenderedFileList]:
        """Each commons agent becomes a subagent file: ``name`` and
        ``description`` kept, ``model: inherit`` (Antigravity's tiers do not
        name Claude Code's models), ``tools`` only when every required tool
        maps to a confirmed Antigravity name, every other field dropped and
        named in the report. The body, the system prompt, is unchanged."""
        out: list[RenderedFileList] = []
        folder = self.install_paths(home).agents
        assert folder is not None
        for src in agents:
            text = src.read_text(encoding="utf-8")
            doc = _fm.parse_text(text); meta, body = doc.meta, doc.body
            name = str(meta.get("name") or src.stem)
            front: dict[str, Any] = {"name": name, "description": str(meta.get("description") or "").strip(),
                                     "model": "inherit"}
            dropped = [k for k in meta if k not in ("name", "description")]
            required = meta.get("required_tools") or meta.get("tools") or []
            unmapped = [t for t in required if t not in TOOL_MAP]
            if required and not unmapped:
                front["tools"] = sorted({TOOL_MAP[t] for t in required})
            rendered = _fm.dump_document(front, body)
            out.append(RenderedFileList(folder / f"{name}.md", rendered, src,
                                        dropped=dropped, unmapped=unmapped))
        return out

    def mcp_config(self, registrations: dict[str, dict[str, Any]], home: Path) -> RenderedFileList:
        """The registrations merged under ``mcpServers``; every other server
        the person has is kept."""
        target = self.install_paths(home).mcp
        assert target is not None
        data: dict[str, Any] = {}
        if target.is_file():
            try:
                data = json.loads(target.read_text(encoding="utf-8") or "{}")
            except json.JSONDecodeError:
                data = {}
        servers = data.setdefault("mcpServers", {})
        for name, spec in registrations.items():
            servers[name] = spec
        return RenderedFileList(target, json.dumps(data, indent=2) + "\n", None)

    # --- the install -------------------------------------------------------------

    def install(self, home: Path, commons: Path, *, dry_run: bool = False,
                all_skills: bool = False) -> InstallReport:
        from .harness_claude_code import MCP_REGISTRATIONS

        report = InstallReport(self.facts.name)
        paths = self.install_paths(home)
        assert paths.rules and paths.skills and paths.agents and paths.mcp

        # Rules: the shared ones, the deployment's own, and the output style.
        sources = sorted((commons / "rules").glob("*.md"))
        sources += sorted((commons / "rules" / "local").glob("*.md")) if (commons / "rules" / "local").is_dir() else []
        for extra in (commons / "output_styles" / "plain_english.md", commons / "CLAUDE.md",
                      commons.parent / "CLAUDE.md"):
            # The output style and the commons overview are rules here. CLAUDE.md
            # sits beside a clone's commons and one level up from a packaged copy.
            if extra.is_file() and extra.name not in {s.name for s in sources}:
                sources.append(extra)
                if extra.name == "CLAUDE.md":
                    break
        rendered = self.render_rules(sources, home)
        always_on = 0
        for r in rendered:
            if r.skipped:
                report.skipped.append(r.skipped)
                continue
            if "trigger: always_on" in r.text[:40]:
                always_on += len(r.text.encode("utf-8"))
            _write(r.path, r.text, dry_run, report)
        if always_on > RULES_BUDGET_TOKENS * BYTES_PER_TOKEN:
            report.warnings.append(
                f"the always-on rules come to about {always_on // BYTES_PER_TOKEN:,} tokens, over Antigravity's "
                f"{RULES_BUDGET_TOKENS:,}-token budget; it will demote the largest to a path the agent reads on demand")

        # Skills: links. A skill meant to be typed, never chosen by the model,
        # is left out unless asked for, since Antigravity ignores that guard.
        if not dry_run:
            paths.skills.mkdir(parents=True, exist_ok=True)
        for src in sorted(d for d in (commons / "skills").iterdir() if d.is_dir()):
            meta = _fm.parse_text((src / "SKILL.md").read_text(encoding="utf-8")).meta if (src / "SKILL.md").is_file() else {}
            if meta.get("disable-model-invocation") and not all_skills:
                report.skipped.append(f"skill {src.name}: meant to be typed by a person, and Antigravity would let "
                                      "the model choose it (--all-skills links it anyway)")
                continue
            dest = paths.skills / src.name
            if dest.exists() and not dest.is_symlink():
                report.skipped.append(f"skill {src.name}: {dest} is your own, not a link; left alone")
                continue
            if not dry_run:
                if dest.is_symlink():
                    dest.unlink()
                dest.symlink_to(src)
            report.linked.append(dest)

        # Agents: translated copies. What was dropped is said once, not per agent.
        dropped: set[str] = set()
        unmapped: set[str] = set()
        for r in self.render_agents(sorted((commons / "agents").glob("*.md")), home):
            _write(r.path, r.text, dry_run, report)
            dropped.update(r.dropped)
            unmapped.update(r.unmapped)
        if dropped:
            report.skipped.append("agents: fields Antigravity has no place for, left out of every agent: "
                                  + ", ".join(sorted(dropped)))
        if unmapped:
            report.notes.append("agents: no tools line, so each gets Antigravity's full set; these Claude Code "
                                "tools have no confirmed Antigravity name yet: " + ", ".join(sorted(unmapped)))

        # MCP servers.
        mcp = self.mcp_config(MCP_REGISTRATIONS, home)
        _write(mcp.path, mcp.text, dry_run, report)
        report.notes.append(
            "MCP tools run in ask mode until a permission rule allows them; add in Antigravity's settings: "
            + ", ".join(f"mcp({n}/*)" for n in MCP_REGISTRATIONS) + ", and command(murmurent)")
        # The governance hooks.
        hooks = self.hook_config(home)
        _write(hooks.path, hooks.text, dry_run, report)
        root = os.environ.get("MURMURENT_DATA_ROOT") or os.environ.get("MURMURENT_LAB_VM_ROOT") or ""
        if root:
            report.notes.append(f"the governance hooks carry the data root {root}; re-run this install if it changes")
        else:
            report.warnings.append("MURMURENT_DATA_ROOT is not set, so the hooks do not know the lab's data root "
                                   "and will not refuse writes under it; set it and run this install again")
        report.notes.append("the governance hooks run through murmurent.hooks.adapter; check them with: "
                            "murmurent harness smoke antigravity")
        report.warnings.append(DATA_WARNING)
        return report


class RenderedFileList:
    """One rendered file plus what the renderer wants the report to say.
    (A plain class rather than the frozen RenderedFile, since it carries notes.)"""

    def __init__(self, path: Path, text: str, source: Path | None, *, skipped: str = "",
                 dropped: list[str] | None = None, unmapped: list[str] | None = None) -> None:
        self.path = path
        self.text = text
        self.source = source
        self.skipped = skipped
        self.dropped = dropped or []
        self.unmapped = unmapped or []


def _write(path: Path, text: str, dry_run: bool, report: InstallReport) -> None:
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    report.written.append(path)


def chosen_here(home: Path | None = None) -> bool:
    """Whether this machine lists Antigravity among its harnesses."""
    from .harness_policy import machine_harnesses

    return "antigravity" in machine_harnesses()


__all__ = ["AntigravityProfile", "DATA_WARNING", "GOVERNED_MATCHER", "HOOK_NAME", "KINDS", "RULE_FILE_LIMIT", "TOOL_MAP", "chosen_here"]
