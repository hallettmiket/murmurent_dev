"""
Purpose: The routing table (phase 3 of ``docs/harnesses_plan.md``): which
         harness, which model and which place take which kind of task,
         declared by the lab in ``policy/models.yaml`` of its records
         repository and read the way the machines and harnesses files are.
         It is the "thalamus" of the design note: small, written by people,
         reviewed by the PI, never learned.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-16
Input:   ``policy/models.yaml``; ``$MURMURENT_MODELS_FILE`` for trying a file
         before the PI adopts it; the harness profiles; a project's record
         for its sensitivity.
Output:  :class:`RoutePolicy` (the routes and any problems found), and
         :func:`route_for`, which refuses a route a project's sensitivity
         forbids.

Harness, model and place are three fields, because any pairing can occur
and data sensitivity depends on the place alone (rule 2 of the plan). A row
whose ``harness`` murmurent does not know, whose ``place`` is not the
harness's, or whose ``data`` names a tier that does not exist is reported
and dropped; the other rows stand.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import harness_policy as _hp

MODELS_ENV = "MURMURENT_MODELS_FILE"
MODELS_RELATIVE_PATH = Path("policy") / "models.yaml"


@dataclass(frozen=True)
class Route:
    """One row: a kind of task and who takes it."""

    kind: str
    harness: str
    model: str
    place: str
    #: The sensitivity tiers a project may carry for this route to apply.
    data: tuple[str, ...]
    agent: str = ""
    why: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "harness": self.harness, "model": self.model, "place": self.place,
                "data": list(self.data), "agent": self.agent, "why": self.why}

    def allows(self, sensitivity: str) -> bool:
        return sensitivity in self.data


@dataclass
class RoutePolicy:
    routes: dict[str, Route] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def kinds(self) -> list[str]:
        return list(self.routes)


def _read_yaml(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return None, f"{path}: could not read it ({exc.__class__.__name__})"
    if not isinstance(data, dict):
        return None, f"{path}: expected a mapping at the top"
    return data, None


def _route_from(kind: str, raw: dict[str, Any], where: str, harnesses: _hp.HarnessPolicy,
                problems: list[str]) -> Route | None:
    harness = str(raw.get("harness") or "")
    if harness not in harnesses.harnesses:
        problems.append(f"{where}: harness {harness!r} is not one murmurent knows "
                        f"({', '.join(harnesses.names())}); row dropped")
        return None
    if not harnesses.allowed(harness):
        problems.append(f"{where}: harness {harness!r} is not allowed by the lab (enabled: in "
                        f"policy/harnesses.yaml); row dropped")
        return None
    facts = harnesses.harnesses[harness]
    place = str(raw.get("place") or facts.place)
    if place != facts.place:
        problems.append(f"{where}: place {place!r} is not where {harness} runs ({facts.place}); "
                        f"kept {facts.place!r}")
        place = facts.place
    model = str(raw.get("model") or "")
    if not model:
        problems.append(f"{where}: no model named; row dropped")
        return None
    data_raw = raw.get("data", list(_hp.TIERS))
    if not isinstance(data_raw, list) or not data_raw:
        problems.append(f"{where}: 'data' must be a list of tiers; kept every tier")
        data_raw = list(_hp.TIERS)
    tiers: list[str] = []
    for t in data_raw:
        if t == "clinical":  # the former name of protected
            t = "protected"
        if t not in _hp.TIERS:
            problems.append(f"{where}: data tier {t!r} is not one of {', '.join(_hp.TIERS)}; ignored")
            continue
        tiers.append(str(t))
    if not tiers:
        problems.append(f"{where}: no valid data tier left; row dropped")
        return None
    return Route(kind=kind, harness=harness, model=model, place=place, data=tuple(tiers),
                 agent=str(raw.get("agent") or ""), why=str(raw.get("why") or ""))


def _apply_file(policy: RoutePolicy, path: Path, harnesses: _hp.HarnessPolicy) -> None:
    data, problem = _read_yaml(path)
    if problem:
        policy.problems.append(problem)
        return
    policy.sources.append(str(path))
    routes = data.get("routes", data)
    if not isinstance(routes, dict):
        policy.problems.append(f"{path}: 'routes' must be a mapping of task kind to settings")
        return
    for kind, raw in routes.items():
        kind = str(kind)
        if not isinstance(raw, dict):
            policy.problems.append(f"{path}: route {kind!r} must be a mapping")
            continue
        route = _route_from(kind, raw, f"{path}: {kind}", harnesses, policy.problems)
        if route is not None:
            policy.routes[kind] = route


def lab_models_path(env: dict[str, str] | None = None) -> Path | None:
    """``policy/models.yaml`` in the lab's records repository, if that is known."""
    try:
        from .repo import lab_mgmt_repo_root

        return lab_mgmt_repo_root(env) / MODELS_RELATIVE_PATH
    except Exception:  # noqa: BLE001 - no lab records on this machine
        return None


def load_routes(env: dict[str, str] | None = None,
                harnesses: _hp.HarnessPolicy | None = None) -> RoutePolicy:
    """The lab's file, then the override file. No built-in rows: a lab that
    has written none has no routes, and ``murmurent route`` says so."""
    env = os.environ if env is None else env
    harnesses = harnesses or _hp.load_harnesses(env)
    policy = RoutePolicy()
    policy.problems.extend(harnesses.problems)
    lab_path = lab_models_path(env)
    if lab_path is not None and lab_path.is_file():
        _apply_file(policy, lab_path, harnesses)
    override = env.get(MODELS_ENV)
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            _apply_file(policy, path, harnesses)
        else:
            policy.problems.append(f"${MODELS_ENV} names {path}, which does not exist")
    return policy


@dataclass(frozen=True)
class Answer:
    """What ``murmurent route`` says: the route, or why not."""

    route: Route | None
    refused: str = ""     # the reason, when a route exists but may not be used
    missing: str = ""     # the reason, when no route exists

    @property
    def ok(self) -> bool:
        return self.route is not None and not self.refused


def project_sensitivity(project: str | None) -> tuple[str, str]:
    """``(tier, note)`` for a project name, or for the project of the current
    folder when none is given; ``standard`` with a note when unknown."""
    try:
        from . import cert_projects as _cp

        name = project or _cp.project_name_for_cwd() or ""
        if not name:
            return "standard", "no project here; treated as standard"
        rec = _cp.get(name)
        if rec is None:
            return "standard", f"no record for project {name!r}; treated as standard"
        return rec.sensitivity, f"project {name}: {rec.sensitivity}"
    except Exception as exc:  # noqa: BLE001
        return "standard", f"project record unreadable ({exc.__class__.__name__}); treated as standard"


def route_for(kind: str, *, project: str | None = None,
              policy: RoutePolicy | None = None) -> Answer:
    """The route for a kind of task, refused when the project's sensitivity
    is not in the route's ``data`` list. The refusal reads the place."""
    policy = policy or load_routes()
    route = policy.routes.get(kind)
    if route is None:
        kinds = ", ".join(policy.kinds()) or "none declared"
        return Answer(None, missing=f"no route: {kind!r} (kinds: {kinds})")
    tier, note = project_sensitivity(project)
    if not route.allows(tier):
        return Answer(route, refused=(
            f"{kind} goes to {route.harness} ({route.model}) at {route.place}, which the lab allows for "
            f"{', '.join(route.data)} data only; {note}. Not routed."))
    return Answer(route)


def headless_command(route: Route, prompt: str, cwd: Path | None = None) -> list[str] | None:
    """The command line the route's harness would run for ``prompt``. Built,
    never run (running is a later branch)."""
    profile = _hp.profiles().get(route.harness)
    if profile is None:
        return None
    return profile.headless_command(prompt, route.model, cwd or Path.cwd())
