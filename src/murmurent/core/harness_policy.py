"""
Purpose: The harness registry: every program that can run murmurent's agents
         (Claude Code today; Google Antigravity, OpenCode and Qwen Code later)
         behind one interface, the way :mod:`machine_policy` puts every
         machine behind one. A harness is a **profile**; the lab may override
         a profile's facts in ``policy/harnesses.yaml`` of its records
         repository.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-16
Input:   The built-in profiles; ``policy/harnesses.yaml`` in the lab records
         repository, if any; ``$MURMURENT_HARNESSES_FILE`` for trying a file
         before the PI adopts it.
Output:  :class:`HarnessPolicy` (the harnesses and any problems found),
         :class:`Profile` objects with the fixed questions every harness
         answers, and the shapes later phases fill in (:class:`ToolEvent`,
         :class:`Event`, :class:`TranscriptStore`).

Design (``docs/harnesses_plan.md``): a **harness** is the program around a
model that gives it tools, rules and memory; a **model** is what it talks to;
a **place** is where the model runs and the conversation is kept. The three
are separate fields everywhere, because any pairing can occur and data
sensitivity depends on the place alone.

Phase 0 of the plan: the interface, and Claude Code behind it with no change
in effect. The other methods raise :class:`NotImplementedError` with the phase
that fills them in, so a caller never gets a silent empty answer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterator

import yaml

HARNESSES_ENV = "MURMURENT_HARNESSES_FILE"
HARNESSES_RELATIVE_PATH = Path("policy") / "harnesses.yaml"

#: Where a model runs and where the conversation is kept. The routing table's
#: sensitivity check reads this field and nothing else.
PLACES: tuple[str, ...] = ("anthropic_cloud", "google_personal", "google_cloud", "lab_server")

#: The three sensitivity tiers a project may carry (``cert_projects``).
TIERS: tuple[str, ...] = ("standard", "restricted", "protected")

#: What the lab may change about a profile in ``policy/harnesses.yaml``.
OVERRIDABLE: tuple[str, ...] = ("description", "place", "models")


# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Harness:
    """The facts about one harness that the commands and the routing table read."""

    name: str
    description: str
    place: str
    #: What it can run today. Read from the harness's own list at install
    #: time where the harness has one; never trusted from a table.
    models: tuple[str, ...] = ()
    #: Whether it has a pre-tool hook that can refuse a call before it runs.
    hooks_can_deny: bool = False
    #: The command that runs one prompt and exits, or an empty string.
    headless: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "place": self.place,
            "models": list(self.models),
            "hooks_can_deny": self.hooks_can_deny,
            "headless": self.headless,
        }


@dataclass(frozen=True)
class RenderedFile:
    """One file an install writes: where, and the whole text."""

    path: Path
    text: str


@dataclass(frozen=True)
class InstallPaths:
    """Where a harness keeps each kind of thing the commons provides. A key
    the harness has no place for is absent."""

    settings: Path | None = None       # hooks and environment
    mcp: Path | None = None            # MCP server registrations
    rules: Path | None = None          # a folder of rule files
    skills: Path | None = None         # a folder of skill folders
    agents: Path | None = None         # a folder of agent files
    hooks: Path | None = None          # the hooks file, when separate from settings
    output_styles: Path | None = None  # a folder of output styles, if the harness has them

    def as_dict(self) -> dict[str, str]:
        return {k: str(v) for k, v in self.__dict__.items() if v is not None}


@dataclass(frozen=True)
class Installed:
    """Whether the commons are installed into a harness on this machine, and why not."""

    yes: bool
    detail: str


# ---------------------------------------------------------------------------
# Shapes later phases fill in
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolEvent:
    """One tool call, in murmurent's own vocabulary, whatever harness made it.
    Phase 2 gives every hook this instead of the harness's raw payload."""

    harness: str
    session: str
    cwd: str
    #: shell | write | edit | read | notebook | agent | other
    tool: str
    command: str = ""   # the shell line, for tool == shell
    path: str = ""      # the file, for write | edit | read | notebook
    content: str = ""   # new content, for write | edit
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    """One row of the record every harness's sessions are reduced to (phase 4)."""

    t: str
    harness: str
    model: str
    place: str
    session: str
    project: str
    repo: str
    tool: str
    summary: str
    decision: str
    hook: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class TranscriptStore:
    """Where a harness keeps its sessions on disk: a folder and a glob under it."""

    harness: str
    root: Path
    pattern: str

    def files(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return sorted(self.root.glob(self.pattern))


# ---------------------------------------------------------------------------
# The profile: the fixed questions every harness answers
# ---------------------------------------------------------------------------


class Profile:
    """One class per harness. Every method is a function of paths and text;
    nothing here talks to a network, and nothing here runs the harness.

    A method a phase has not yet filled in raises :class:`NotImplementedError`
    naming the phase, so a caller never mistakes "not written" for "none".
    """

    facts: Harness

    #: The phase of ``docs/harnesses_plan.md`` that fills in each method.
    PHASES: dict[str, int] = {
        "render_rules": 1, "render_agents": 1, "mcp_config": 1, "hook_config": 2,
        "to_event": 2, "from_decision": 2, "read_events": 4,
    }

    def _later(self, method: str) -> NotImplementedError:
        return NotImplementedError(
            f"{self.facts.name}.{method} is written in phase {self.PHASES.get(method, '?')} "
            "of docs/harnesses_plan.md"
        )

    # Phase 0 ---------------------------------------------------------------

    def install_paths(self, home: Path) -> InstallPaths:
        raise NotImplementedError(f"{self.facts.name}.install_paths")

    def installed(self, home: Path) -> Installed:
        raise NotImplementedError(f"{self.facts.name}.installed")

    def headless_command(self, prompt: str, model: str, cwd: Path) -> list[str] | None:
        """The command line that runs one prompt and exits; None when the
        harness has no headless mode. Built, never run."""
        return None

    def transcript_stores(self, home: Path) -> list[TranscriptStore]:
        return []

    # Phase 1 ---------------------------------------------------------------

    def render_rules(self, rules: list[Path], home: Path) -> list[RenderedFile]:
        raise self._later("render_rules")

    def render_agents(self, agents: list[Path], home: Path) -> list[RenderedFile]:
        raise self._later("render_agents")

    def mcp_config(self, registrations: dict[str, dict[str, Any]], home: Path) -> RenderedFile:
        raise self._later("mcp_config")

    # Phase 2 ---------------------------------------------------------------

    def hook_config(self, home: Path) -> RenderedFile:
        raise self._later("hook_config")

    def to_event(self, payload: dict[str, Any]) -> ToolEvent:
        raise self._later("to_event")

    def from_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        raise self._later("from_decision")

    # Phase 4 ---------------------------------------------------------------

    def read_events(self, path: Path) -> Iterator[Event]:
        raise self._later("read_events")


# ---------------------------------------------------------------------------
# The registry and the lab's overrides
# ---------------------------------------------------------------------------


def profiles() -> dict[str, Profile]:
    """Every built-in profile by name. Imported here, not at module load, so
    a profile module may import this one."""
    from .harness_claude_code import ClaudeCodeProfile

    built_in: list[Profile] = [ClaudeCodeProfile()]
    return {p.facts.name: p for p in built_in}


@dataclass
class HarnessPolicy:
    harnesses: dict[str, Harness] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def names(self) -> list[str]:
        return list(self.harnesses)


def _read_yaml(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return None, f"{path}: could not read it ({exc.__class__.__name__})"
    if not isinstance(data, dict):
        return None, f"{path}: expected a mapping at the top"
    return data, None


def _override(harness: Harness, raw: dict[str, Any], where: str, problems: list[str]) -> Harness:
    """Apply the lab's overrides to a built-in profile's facts. A wrong value
    is reported and the profile's value kept, so a typo never empties a row."""
    out = harness
    for key, value in raw.items():
        if key not in OVERRIDABLE:
            problems.append(f"{where}: {key!r} cannot be changed by the lab "
                            f"(only {', '.join(OVERRIDABLE)})")
            continue
        if key == "place":
            if value not in PLACES:
                problems.append(f"{where}: place {value!r} is not one of {', '.join(PLACES)}; kept {harness.place!r}")
                continue
            out = replace(out, place=str(value))
        elif key == "models":
            if not isinstance(value, list) or not all(isinstance(m, str) for m in value):
                problems.append(f"{where}: models must be a list of names; kept the profile's")
                continue
            out = replace(out, models=tuple(value))
        else:
            if not isinstance(value, str):
                problems.append(f"{where}: {key} must be text; kept the profile's")
                continue
            out = replace(out, description=value)
    return out


def _apply_file(policy: HarnessPolicy, path: Path) -> None:
    data, problem = _read_yaml(path)
    if problem:
        policy.problems.append(problem)
        return
    policy.sources.append(str(path))
    harnesses = data.get("harnesses", data)
    if not isinstance(harnesses, dict):
        policy.problems.append(f"{path}: 'harnesses' must be a mapping of harness name to settings")
        return
    for name, raw in harnesses.items():
        name = str(name)
        if name not in policy.harnesses:
            policy.problems.append(
                f"{path}: {name!r} is not a harness murmurent knows "
                f"(it knows {', '.join(policy.harnesses)}); a new kind needs a profile in core/"
            )
            continue
        if not isinstance(raw, dict):
            policy.problems.append(f"{path}: harness {name!r} must be a mapping")
            continue
        policy.harnesses[name] = _override(policy.harnesses[name], raw, f"{path}: {name}", policy.problems)


def lab_harnesses_path(env: dict[str, str] | None = None) -> Path | None:
    """``policy/harnesses.yaml`` in the lab's records repository, if that is known."""
    try:
        from .repo import lab_mgmt_repo_root

        return lab_mgmt_repo_root(env) / HARNESSES_RELATIVE_PATH
    except Exception:  # noqa: BLE001 - no lab records on this machine
        return None


def load_harnesses(env: dict[str, str] | None = None) -> HarnessPolicy:
    """The built-in profiles' facts, then the lab's file, then the override file."""
    env = os.environ if env is None else env
    policy = HarnessPolicy()
    for name, profile in profiles().items():
        policy.harnesses[name] = profile.facts
    lab_path = lab_harnesses_path(env)
    if lab_path is not None and lab_path.is_file():
        _apply_file(policy, lab_path)
    override = env.get(HARNESSES_ENV)
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            _apply_file(policy, path)
        else:
            policy.problems.append(f"${HARNESSES_ENV} names {path}, which does not exist")
    return policy
