"""
Purpose: The Claude Code profile: what ``murmurent install --hooks`` has
         always done (hook and MCP entries merged into ``~/.claude/settings.json``
         and ``~/.claude.json``), behind the :class:`~.harness_policy.Profile`
         interface. Moved here from ``commands/install_cmd.py`` in phase 0 of
         ``docs/harnesses_plan.md`` with no change in effect: a test renders
         the install and compares it byte for byte with what ``main`` wrote.
Author:  Mike Hallett (with Claude Code)
Date:    2026-05-07 (the registrations); 2026-11-16 (the profile)
Input:   An existing ``settings.json`` and ``~/.claude.json``, or none.
Output:  The two files with murmurent's entries merged in; whether anything changed.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .harness_policy import Event, Harness, InstallPaths, Installed, Profile, ToolEvent, TranscriptStore

DEFAULT_SETTINGS_PATH = Path("~/.claude/settings.json").expanduser()


HOOK_REGISTRATIONS: list[dict[str, Any]] = [
    {
        # murmurent agent reporter — writes coloured one-line events for
        # PreToolUse(Agent) and SubagentStop to ~/.murmurent/agents.log,
        # which the VSCode BR pane tails. Uses ``command`` rather than
        # ``module`` because the hook is a bash script, not a Python
        # entrypoint.
        "event": "PreToolUse",
        "matcher": "Agent",
        "command": "bash <MURMURENT_COMMONS>/scripts/murmurent_log_agent_event.sh",
        "env": {},
        "label": "murmurent-agent-report-pre",
    },
    {
        "event": "SubagentStop",
        "matcher": None,
        "command": "bash <MURMURENT_COMMONS>/scripts/murmurent_log_agent_event.sh",
        "env": {},
        "label": "murmurent-agent-report-stop",
    },
    {
        # Tells each subagent, before its first prompt, which language to
        # write its spoken "Aloud:" line in when the machine has chosen one
        # (`murmurent config speak-language`, #279). Prints nothing for
        # English, so a machine with no choice is unchanged.
        "event": "SubagentStart",
        "matcher": None,
        "command": "bash <MURMURENT_COMMONS>/scripts/murmurent_log_agent_event.sh",
        "env": {},
        "label": "murmurent-agent-report-start",
    },
    {
        "event": "PreToolUse",
        "matcher": "Write|Edit|Bash|NotebookEdit",
        "module": "murmurent.hooks.raw_guard",
        "env": {},
        "label": "murmurent-raw-guard",
    },
    {
        # Refined data + Obsidian notebook are write-once: new files OK,
        # overwriting / deleting existing files denied (lab versioning
        # convention: write file_2.csv, never overwrite file.csv).
        "event": "PreToolUse",
        "matcher": "Write|Edit|Bash|NotebookEdit",
        "module": "murmurent.hooks.protected_paths",
        "env": {},
        "label": "murmurent-protected-paths",
    },
    {
        # The rest of the data root: modifiable/ is free, mothballed/ takes
        # new files only, and everywhere else a new file is fine, an
        # overwrite is refused and a delete asks the member first.
        "event": "PreToolUse",
        "matcher": "Write|Edit|Bash|NotebookEdit",
        "module": "murmurent.hooks.data_root_guard",
        "env": {},
        "label": "murmurent-data-root-guard",
    },
    {
        "event": "PreToolUse",
        "matcher": "Bash|WebFetch|WebSearch|mcp__slack__.*|mcp__claude_ai_Slack__.*",
        "module": "murmurent.hooks.phi_check",
        "env": {"MURMURENT_PHI_HOOK_MODE": "pre"},
        "label": "murmurent-phi-pre",
    },
    {
        "event": "PostToolUse",
        "matcher": ".*",
        "module": "murmurent.hooks.phi_check",
        "env": {"MURMURENT_PHI_HOOK_MODE": "post"},
        "label": "murmurent-phi-post",
    },
    {
        "event": "UserPromptSubmit",
        "matcher": ".*",
        "module": "murmurent.hooks.context_inject",
        "env": {},
        "label": "murmurent-context-inject",
    },
    {
        # Records each prompt in the personal vault's sessions/<date>/ stream
        # with the time, project, repository and commit (#292), so nobody
        # pastes prompts into the lab notebook. Withholds a prompt that
        # matches a PHI or secret pattern and says so. Never blocks.
        "event": "UserPromptSubmit",
        "matcher": ".*",
        "module": "murmurent.hooks.session_log",
        "env": {},
        "label": "murmurent-session-log",
    },
    {
        "event": "PostToolUse",
        "matcher": ".*",
        "module": "murmurent.hooks.audit",
        "env": {},
        "label": "murmurent-audit",
    },
    {
        # Harvests the "## Gap register" table out of conscience reports under
        # outputs/conscience/ into ~/.murmurent/edid_gaps/ (append-only, per member) and
        # regenerates a local ranked register, so the EDID pool learns what
        # it is missing from reviews that needed something rather than from
        # someone remembering. Never writes docs/edid_resources.md — only the
        # bookworm, with a person's approval, changes what may be cited.
        "event": "PostToolUse",
        "matcher": "Write|Edit|NotebookEdit",
        "module": "murmurent.hooks.conscience_gaps",
        "env": {},
        "label": "murmurent-conscience-gaps",
    },
    {
        # When agents/<x>.md is edited, remind the session once that the agent's
        # training movie was checked against an older version of the file and
        # name the command that re-renders it (#288). A prompt, never a block.
        "event": "PostToolUse",
        "matcher": "Write|Edit|MultiEdit|NotebookEdit",
        "module": "murmurent.hooks.agent_movie",
        "env": {},
        "label": "murmurent-agent-movie",
    },
    # The personal vault follows you between machines without a button:
    # brought in when a session starts, sent as soon as a session writes a
    # note in it, and checked at the end of each reply. Notes marked protected
    # or restricted are never sent. See murmurent.hooks.vault_sync.
    {
        "event": "SessionStart",
        "matcher": None,
        "module": "murmurent.hooks.vault_sync",
        "env": {},
        "label": "murmurent-vault-sync-start",
    },
    {
        "event": "PostToolUse",
        "matcher": "Write|Edit|MultiEdit|NotebookEdit|mcp__murmurent-oracle__.*",
        "module": "murmurent.hooks.vault_sync",
        "env": {},
        "label": "murmurent-vault-sync-write",
    },
    {
        "event": "Stop",
        "matcher": None,
        "module": "murmurent.hooks.vault_sync",
        "env": {},
        "label": "murmurent-vault-sync-stop",
    },
]

MCP_REGISTRATIONS: dict[str, dict[str, Any]] = {
    "murmurent-inventory": {
        "command": sys.executable,
        "args": ["-m", "murmurent.mcp.inventory_server"],
        "env": {},
    },
    # Personal + Lab Oracle search/get/list/publish. Uses the same
    # python so the server has access to murmurent.core.* (vault
    # resolution, frontmatter parsing, publish flow).
    "murmurent-oracle": {
        "command": sys.executable,
        "args": ["-m", "murmurent.mcp.oracle_server"],
        "env": {},
    },
    # Per-job deliverable reader for core services. Members of a
    # requesting lab pull their job files through this MCP from any
    # CC session connected to the lab server (Phases 5d + 7).
    "murmurent-core-data": {
        "command": sys.executable,
        "args": ["-m", "murmurent.mcp.core_data_server"],
        "env": {},
    },
    # Arbitrary reference files (PDFs, spreadsheets, protocols, images,
    # text) under a vault's murmurent_data/ folder — list + read on
    # demand. Distinct from the Oracle (schema-validated markdown facts).
    "murmurent-data": {
        "command": sys.executable,
        "args": ["-m", "murmurent.mcp.data_server"],
        "env": {},
    },
}

#: Environment settings murmurent sets in ``settings.json`` for every member,
#: unless the member has already chosen a value. The feedback survey interrupts
#: a working session to ask for a rating; the lab asked for it off (#154).
DEFAULT_ENV: dict[str, str] = {
    "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "1",
}

#: The hook whose presence says the commons are installed (the first guard).
INSTALLED_MARKER = "murmurent-raw-guard"


def _expand_placeholders(text: str) -> str:
    """Replace ``<MURMURENT_COMMONS>`` with this machine's commons root.

    Resolved through :func:`commons_root` rather than the clone path, because a
    ``uv tool install`` has no clone: the hook used to point at
    ``~/repos/murmurent/scripts/``, which did not exist there (#159).
    """
    if "<MURMURENT_COMMONS>" not in text:
        return text
    from .commons import commons_root
    return text.replace("<MURMURENT_COMMONS>", str(commons_root()))


def _resolve_command(reg: dict[str, Any]) -> str:
    """Render the shell command for a hook registration.

    Two registration shapes are supported:
      - ``module``: a Python module entrypoint — gets ``$PYTHON -m <module>``
        with optional env-var prefixes (the historic shape; covers
        raw_guard, phi_check, audit, etc.).
      - ``command``: a literal shell command — typically a path to a
        bash script. Use ``<MURMURENT_COMMONS>`` as a placeholder for the
        commons root (a clone, or the copy inside the installed package);
        it's expanded at install time so the resulting absolute path is
        correct on this machine.
    """
    env = reg.get("env") or {}
    if "command" in reg:
        cmd = _expand_placeholders(str(reg["command"]))
        parts = [f"{k}={v}" for k, v in env.items()] + [cmd]
        return " ".join(parts)
    parts = [f"{k}={v}" for k, v in env.items()]
    parts.extend([sys.executable, "-m", reg["module"]])
    return " ".join(parts)


def _matches_existing(entry: dict[str, Any], reg: dict[str, Any]) -> bool:
    """Decide whether ``entry`` corresponds to ``reg`` (so we can replace it).

    Identity carries through the ``label`` (always present) and the
    body of the command — either the Python module name (``module``
    registrations) or the script path (``command`` registrations).
    """
    # Matcher equality: both ``None`` and missing-key mean "no matcher"
    # for our purposes; treat them as equivalent so we don't fail to
    # match an existing entry just because the old shape stored
    # ``matcher: null`` and the new shape omits the key.
    if (entry.get("matcher") or None) != (reg.get("matcher") or None):
        return False
    body = _expand_placeholders(reg.get("module") or reg.get("command") or "")
    hooks = entry.get("hooks") or []
    for h in hooks:
        # The label is written as the hook's ``name``. Matching on it lets a
        # re-install replace an entry whose path has since moved (a clone path
        # on a machine that now runs from the package) instead of leaving the
        # broken one in place beside the new one.
        if reg.get("label") and h.get("name") == reg["label"]:
            return True
        cmd = h.get("command", "")
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        if body and body in cmd:
            return True
        if reg.get("label") and reg["label"] in cmd:
            return True
    return False


def _ensure_hook(settings: dict[str, Any], reg: dict[str, Any]) -> bool:
    """Ensure ``reg`` is present under ``settings.hooks[reg.event]``.

    Returns True if anything changed.

    The ``matcher`` key is only emitted when the registration carries
    a non-None value. CC's settings parser rejects ``matcher: null``
    (``Expected strings, but received null``), and events like
    ``SubagentStop`` and ``Stop`` don't conceptually have a matcher —
    they fire on every occurrence. Omitting the key is the right
    encoding for matcher-less hooks.
    """
    hooks = settings.setdefault("hooks", {})
    bucket = hooks.setdefault(reg["event"], [])
    new_entry: dict[str, Any] = {
        "hooks": [
            {
                "type": "command",
                "command": _resolve_command(reg),
                "name": reg["label"],
            }
        ],
    }
    matcher = reg.get("matcher")
    if matcher is not None:
        new_entry["matcher"] = matcher
    # Preserve insertion order for diff stability: when an entry has
    # both matcher and hooks, put matcher first to match the existing
    # on-disk shape.
    if "matcher" in new_entry:
        new_entry = {"matcher": new_entry["matcher"], "hooks": new_entry["hooks"]}
    for i, entry in enumerate(bucket):
        if _matches_existing(entry, reg):
            if entry == new_entry:
                return False
            bucket[i] = new_entry
            return True
    bucket.append(new_entry)
    return True


def _ensure_env(settings: dict[str, Any]) -> bool:
    """Add each ``DEFAULT_ENV`` entry to ``settings.env`` if it is not there.

    A value the member already set is left alone, even if it differs: this is
    a default, not a policy. Returns True if anything changed.
    """
    env = settings.setdefault("env", {})
    changed = False
    for key, value in DEFAULT_ENV.items():
        if key not in env:
            env[key] = value
            changed = True
    return changed


def _ensure_mcp(settings: dict[str, Any]) -> bool:
    """Ensure each entry in ``MCP_REGISTRATIONS`` is in ``settings.mcpServers``.

    Kept for back-compat: prior murmurent releases wrote MCPs to
    ``~/.claude/settings.json``. Claude Code actually reads them from
    ``~/.claude.json`` (see :func:`_ensure_mcp_claude_json`), so this
    function's writes are effectively no-ops for runtime — but other
    tooling may still inspect ~/.claude/settings.json, so we keep
    populating it.
    """
    changed = False
    servers = settings.setdefault("mcpServers", {})
    for name, spec in MCP_REGISTRATIONS.items():
        if servers.get(name) != spec:
            servers[name] = spec
            changed = True
    return changed


def _ensure_mcp_claude_json(target: Path | None = None) -> bool:
    """Write MCP entries to ``~/.claude.json`` so Claude Code actually
    picks them up. Without this, ``claude mcp list`` doesn't see our
    servers and members can't reach the murmurent MCPs.

    Idempotent. Preserves any entries the user added by hand (e.g.
    slack). Writes at user scope (top-level ``mcpServers`` key).
    """
    target = target or (Path.home() / ".claude.json")
    data: dict[str, Any] = {}
    if target.is_file():
        try:
            data = json.loads(target.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            data = {}
    servers = data.setdefault("mcpServers", {})
    changed = False
    for name, spec in MCP_REGISTRATIONS.items():
        if servers.get(name) != spec:
            servers[name] = spec
            changed = True
    if changed:
        target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


class SettingsUnreadable(Exception):
    """An existing settings file that is not JSON; the caller says what to do."""


def install(settings_path: Path | None = None, *, backup: bool = True,
            mcp_path: Path | None = None) -> tuple[Path, bool]:
    """Merge murmurent's hooks, environment and MCP servers into Claude Code's
    files. Returns the settings path and whether anything changed."""
    target = settings_path or DEFAULT_SETTINGS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    settings: dict[str, Any] = {}
    if target.is_file():
        try:
            settings = json.loads(target.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise SettingsUnreadable(f"could not parse existing {target}: {exc}; back it up and retry.")

    if backup and target.is_file():
        shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))

    changed = False
    for reg in HOOK_REGISTRATIONS:
        if _ensure_hook(settings, reg):
            changed = True
    if _ensure_env(settings):
        changed = True
    if _ensure_mcp(settings):
        changed = True
    # ALSO write MCP entries to ~/.claude.json — that's where Claude Code
    # actually reads from. (~/.claude/settings.json's mcpServers block
    # is a legacy murmurent convention that CC ignores at runtime.)
    if _ensure_mcp_claude_json(mcp_path):
        changed = True

    target.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return target, changed


class ClaudeCodeProfile(Profile):
    """Claude Code: Anthropic's harness, the one murmurent was built on."""

    facts = Harness(
        name="claude_code",
        description="Claude Code, Anthropic's terminal and desktop harness; the commons' home",
        place="anthropic_cloud",
        # Anthropic's current models. Not checked against the harness at
        # install time in phase 0; the routing table never trusts this list.
        models=("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-2"),
        hooks_can_deny=True,
        headless="claude -p",
    )

    def install_paths(self, home: Path) -> InstallPaths:
        claude = home / ".claude"
        return InstallPaths(
            settings=claude / "settings.json",
            mcp=home / ".claude.json",
            rules=claude / "rules",
            skills=claude / "skills",
            agents=claude / "agents",
            output_styles=claude / "output-styles",
        )

    def present(self, home: Path) -> bool:
        return shutil.which("claude") is not None or (home / ".claude").is_dir()

    def installed(self, home: Path) -> Installed:
        paths = self.install_paths(home)
        assert paths.settings is not None and paths.mcp is not None
        missing: list[str] = []
        try:
            settings = json.loads(paths.settings.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError):
            settings = {}
        names = {
            h.get("name")
            for bucket in (settings.get("hooks") or {}).values()
            for entry in bucket
            for h in (entry.get("hooks") or [])
        }
        if INSTALLED_MARKER not in names:
            missing.append(f"hooks not in {paths.settings}")
        try:
            data = json.loads(paths.mcp.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError):
            data = {}
        if not set(MCP_REGISTRATIONS) <= set(data.get("mcpServers") or {}):
            missing.append(f"MCP servers not in {paths.mcp}")
        if not (paths.agents and paths.agents.is_dir()):
            missing.append(f"no {paths.agents}")
        if missing:
            return Installed(False, "; ".join(missing) + " (run: murmurent install --hooks)")
        return Installed(True, "hooks, MCP servers and agents in place")

    def headless_command(self, prompt: str, model: str, cwd: Path) -> list[str] | None:
        cmd = ["claude", "-p", prompt]
        if model:
            cmd += ["--model", model]
        return cmd

    def transcript_stores(self, home: Path) -> list[TranscriptStore]:
        return [TranscriptStore(harness=self.facts.name, root=home / ".claude" / "projects",
                                pattern="*/*.jsonl")]

    # --- the session record (phase 4) ------------------------------------------

    def read_events(self, path: Path):
        """Every tool call in one Claude Code session transcript, as an
        :class:`Event`. Transcripts are one JSON object per line; a tool
        call is a ``tool_use`` block inside an ``assistant`` line's message.
        Lines that are not JSON, or not that shape, are skipped."""
        from .harness_policy import project_for_cwd, summarise

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        for line in lines:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(d, dict) or d.get("type") != "assistant":
                continue
            msg = d.get("message") or {}
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            cwd = str(d.get("cwd") or "")
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                yield Event(
                    t=str(d.get("timestamp") or ""),
                    harness=self.facts.name,
                    model=str(msg.get("model") or ""),
                    place=self.facts.place,
                    session=str(d.get("sessionId") or path.stem),
                    project=project_for_cwd(cwd),
                    repo=Path(cwd).name if cwd else "",
                    tool=str(block.get("name") or ""),
                    summary=summarise(block.get("input")),
                    decision="",
                )

    # --- the hook contract (phase 2) --------------------------------------------

    #: Claude Code's tool names and murmurent's kind for each.
    KINDS: dict[str, str] = {
        "Bash": "shell", "Write": "write", "Edit": "edit", "MultiEdit": "edit",
        "NotebookEdit": "notebook", "Read": "read", "Agent": "agent",
    }

    def to_event(self, payload: dict[str, Any]) -> ToolEvent:
        name = str(payload.get("tool_name") or payload.get("tool") or "")
        args = payload.get("tool_input") or payload.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        kind = self.KINDS.get(name, "other")
        return ToolEvent(
            harness=self.facts.name,
            session=str(payload.get("session_id") or ""),
            cwd=str(payload.get("cwd") or ""),
            tool=kind,
            tool_name=name,
            command=str(args.get("command") or "") if kind == "shell" else "",
            path=str(args.get("file_path") or args.get("notebook_path") or ""),
            content=str(args.get("content") or args.get("new_string") or ""),
            raw=payload,
        )

    def from_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        """Claude Code's modern hook shape: nothing for allow, a
        ``hookSpecificOutput`` block for deny."""
        if decision.get("decision") != "deny":
            return {}
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": decision.get("reason", ""),
            },
        }
