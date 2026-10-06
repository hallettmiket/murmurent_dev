"""
Purpose: Repo-level murmurent READINESS — distinct from projects.
Author: Mike Hallett (with Claude Code)
Date: 2026-07-15
Input: A git working tree (``~/repos/<name>``) + the murmurent commons clone.
Output: A ``.murmurent.yaml`` marker at the repo root + the layer-2 CC
        bootstrap (commons agent symlinks, CLAUDE.md stub, chrome).

Terminology (the point of this module): a repo with the murmurent
bootstrap is **murmurent-ready** — nothing more. A *project* is a
different, bigger thing: a named set of repos + a set of members (+
Slack channel, certificates), recorded in the lab_mgmt registry
(``cert_projects/``). Adopting a repo makes it ready; creating a
project attaches ready repos to a project record. Historically the two
were fused — adopting wrote a project-ish ``CHARTER.md`` into the repo
AND minted a one-repo project — which is how five trial adoptions
polluted a Projects panel (issue context: 2026-07-15).

The marker also solves the upgrade problem: agent CONTENT updates flow
automatically (agents are symlinks into the commons clone), but
structural changes — new commons agents, marker schema, refreshed
stubs — are frozen at bootstrap time. ``upgrade()`` re-runs the
bootstrap idempotently against the current commons and re-stamps
``bootstrap_version``; for a legacy CHARTER.md bootstrap it stamps the
marker while PRESERVING the CHARTER.md (which may be a project document —
readiness just stops keying on it; issue #28).
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .preflight import Probe
from .commons import commons_root

MARKER_FILENAME = ".murmurent.yaml"
# Versions the SHAPE of the .murmurent.yaml marker — independent of the
# murmurent release version (murmurent.__version__). Bump only when the marker
# format changes; do NOT bump it to match a release. (issue #24)
MARKER_SCHEMA = 1
LEGACY_MARKER = "CHARTER.md"   # pre-split repos carried a project charter


def _version() -> str:
    try:
        from .. import __version__
        return str(__version__)
    except Exception:  # noqa: BLE001
        return "unknown"


@dataclass
class Readiness:
    """Repo-level readiness verdict for one working tree."""

    path: Path
    marker: dict | None = None          # parsed .murmurent.yaml, if present
    legacy_charter: bool = False        # CHARTER.md present (pre-split bootstrap)
    has_agents: bool = False            # at least one LINKED .claude/agents/*.md

    @property
    def ready(self) -> bool:
        # Readiness keys on the .murmurent.yaml marker ONLY (issue #28). A
        # legacy CHARTER.md no longer signals readiness — it's a project
        # document (project/lead/members), not a bootstrap marker. Repos that
        # only carry a CHARTER migrate via `murmurent repo upgrade`, which
        # stamps a marker and PRESERVES the CHARTER.
        #
        # The second half counts LINKED AGENTS, not the mere existence of
        # `.claude/agents/`. That directory is created by the bootstrap before
        # anything is linked into it, so testing `.is_dir()` reported ✓ ready
        # for a repo wired to zero agents — which is how an agent-less adopt
        # went unnoticed. An empty (or wholly dangling) directory is not ready.
        return self.marker is not None and self.has_agents

    @property
    def needs_upgrade(self) -> bool:
        """True when a marker-ready repo was bootstrapped by an older marker
        shape (schema/version lags), OR when a repo still carries only a legacy
        CHARTER.md bootstrap and wants a one-time marker stamp."""
        if self.marker is None:
            return self.legacy_charter
        if int(self.marker.get("murmurent") or 0) < MARKER_SCHEMA:
            return True
        return str(self.marker.get("bootstrap_version") or "") != _version()


def read_marker(repo: Path) -> dict | None:
    f = Path(repo) / MARKER_FILENAME
    if not f.is_file():
        return None
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def linked_agents(repo: Path) -> list[str]:
    """The agents actually wired into ``repo`` (``.claude/agents/*.md``).

    ``Path.exists()`` follows symlinks, so a link left pointing at an agent
    that has since been renamed out of the commons does NOT count. That is
    deliberate and matches the remote probe in :mod:`core.adopt`: a repo whose
    only links are dangling has no working agents, whatever the listing says.
    """
    d = Path(repo).expanduser() / ".claude" / "agents"
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.md") if p.exists())


def readiness(repo: Path) -> Readiness:
    repo = Path(repo).expanduser()
    return Readiness(
        path=repo,
        marker=read_marker(repo),
        legacy_charter=(repo / LEGACY_MARKER).is_file(),
        has_agents=bool(linked_agents(repo)),
    )


#: The marker fields readiness owns. Every other field belongs to someone else
#: (a choreography's ``kind: choreography`` declaration, for one) and is kept.
READINESS_FIELDS: tuple[str, ...] = (
    "murmurent", "lab", "ready_since", "bootstrap_version", "agents",
)


def _write_marker(repo: Path, *, lab: str, agents: list[str],
                  ready_since: str | None = None) -> Path:
    """Write the readiness fields, keeping every other field already there.

    This used to write the five readiness fields and nothing else, so
    ``repo upgrade`` (and ``adopt --all-agents`` on a ready repo) silently
    erased a choreography's declaration, after which ``choreography install``
    refused the repo as not being one.
    """
    marker = {
        "murmurent": MARKER_SCHEMA,
        "lab": lab or "",
        "ready_since": ready_since or _dt.date.today().isoformat(),
        "bootstrap_version": _version(),
        "agents": sorted(set(agents or [])),
    }
    for key, value in (read_marker(repo) or {}).items():
        if key not in READINESS_FIELDS:
            marker[key] = value
    f = Path(repo) / MARKER_FILENAME
    f.write_text(yaml.safe_dump(marker, sort_keys=False), encoding="utf-8")
    return f


def update_marker(repo: Path, fields: dict) -> Path:
    """Merge ``fields`` into an existing marker, leaving readiness fields alone.

    For a caller that owns fields other than readiness, such as the choreography
    declaration. Refuses to create a marker: a repo is made ready by
    :func:`make_ready`, not by acquiring unrelated fields.
    """
    repo = Path(repo).expanduser()
    marker = read_marker(repo)
    if marker is None:
        raise FileNotFoundError(
            f"{repo / MARKER_FILENAME} does not exist; make the repo ready first")
    clash = sorted(set(fields) & set(READINESS_FIELDS))
    if clash:
        raise ValueError(f"readiness owns these marker fields: {', '.join(clash)}")
    marker.update(fields)
    f = repo / MARKER_FILENAME
    f.write_text(yaml.safe_dump(marker, sort_keys=False), encoding="utf-8")
    return f


def _commons_agent_names(root: Path) -> list[str]:
    """Every agent shipped by the commons clone at ``root``.

    Takes the root explicitly because :func:`upgrade` accepts a
    ``murmurent_root`` override and must read the same clone it links against.
    """
    commons = Path(root) / "agents"
    if not commons.is_dir():
        return []
    return sorted(p.stem for p in commons.glob("*.md"))


def _resolve_agents(existing: dict | None, agents: list[str] | None,
                    root: Path) -> list[str]:
    """Which agents to wire: explicit list > the marker's own picks > the
    whole commons at ``root``.

    The last step is the one that was missing. ``agents=None`` fell through to
    an empty list, so a plain ``murmurent repo adopt`` on a fresh clone created
    ``.claude/agents/``, linked nothing into it, and recorded ``agents: []``,
    while the docs promise the standard set. The commons default is what makes
    the no-flag case do the documented thing.

    An explicit ``[]`` is a CHOICE (deliberately no agents) and survives, so
    the fallback keys on the marker having no recorded picks at all — not on
    those picks being empty. Otherwise a caller could never opt out.

    ``root`` is passed in rather than resolved here so the default names come
    from the SAME clone the caller links against. ``agent_forks`` resolves the
    commons through ``repo.murmurent_repo_root()``, which disagrees with
    :func:`commons.commons_root` on a machine holding both a release clone and
    a development one — the divergence :func:`make_ready` already documents.
    Defaulting from one clone while symlinking into the other would record
    agents that were never wired.
    """
    if agents is not None:
        return list(agents)
    recorded = (existing or {}).get("agents")
    if isinstance(recorded, list):
        return list(recorded)
    return _commons_agent_names(root)


def ensure_marker(repo: Path, *, lab: str = "",
                  agents: list[str] | None = None) -> Path:
    """Idempotently write the ``.murmurent.yaml`` readiness marker.

    Preserves an existing marker (keeps its recorded agent picks when
    ``agents`` is None). Used by paths that make a repo ready but do their
    own CC bootstrap — e.g. :mod:`core.projectize`, which writes a project's
    CHARTER + registry + manifest and now also stamps the readiness marker so
    a project repo is marker-ready (not CHARTER-ready). Returns the marker path.
    """
    repo = Path(repo).expanduser()
    existing = read_marker(repo)
    if existing is not None and agents is None:
        return repo / MARKER_FILENAME
    picked = list(agents) if agents is not None else list(
        (existing or {}).get("agents") or [])
    return _write_marker(
        repo, lab=lab or str((existing or {}).get("lab") or ""),
        agents=picked,
        ready_since=str((existing or {}).get("ready_since") or "") or None)


def make_ready(clone_path: Path, *, lab: str = "",
               agents: list[str] | None = None,
               murmurent_root: Path | None = None) -> list[Probe]:
    """Make ``clone_path`` murmurent-ready: marker + CC bootstrap.

    The agent symlinks point into :func:`commons.commons_root` — the same
    commons ``murmurent setup``, ``install`` and ``doctor`` read, which is the
    clone you installed rather than whatever sits at ``~/repos/murmurent``.
    This used to call ``repo.murmurent_repo_root()`` instead, and the two
    disagree on a machine holding both a release clone and a development one:
    ``doctor`` would report the commons coming from ``~/repos/murmurent_dev``
    while the repo adopted a moment earlier was linked into
    ``~/repos/murmurent``. An agent edited in the clone you are working on was
    then live in ``~/.claude/agents/`` and silently absent from the repo, which
    is the worst shape a failure like this can take: no error, and the thing
    you just changed appears not to work.

    Deliberately does NOT create a project, write a charter, or touch
    the lab registry — attach the repo to a project separately. ``lab``
    is recorded so multi-lab machines know whose commons this repo
    follows. Idempotent: an existing marker is preserved (its agent
    picks win when ``agents`` is None); re-running refreshes symlinks.
    A fresh clone with no ``agents`` gets the whole commons, not nothing —
    see :func:`_resolve_agents` for the precedence and why.
    """
    from . import project_cc_init as _cci

    repo = Path(clone_path).expanduser()
    probes: list[Probe] = []
    root = murmurent_root or commons_root()
    existing = read_marker(repo)
    picked = _resolve_agents(existing, agents, root)

    # Keep an existing marker only when it already records its own picks.
    # A legacy marker with no `agents` key just resolved to the commons, so
    # re-stamp it — otherwise the marker would keep claiming nothing while
    # fourteen agents sit linked beside it.
    if (existing is not None and agents is None
            and isinstance(existing.get("agents"), list)):
        probes.append(Probe(name="marker", status="ok",
                            detail=f"{MARKER_FILENAME} already present — kept",
                            required=False))
    else:
        f = _write_marker(repo, lab=lab or str((existing or {}).get("lab") or ""),
                          agents=picked,
                          ready_since=str((existing or {}).get("ready_since") or "") or None)
        probes.append(Probe(name="marker", status="ok",
                            detail=f"wrote {f}", required=False))

    probes.extend(_cci.bootstrap_local(repo, root, agents=picked,
                                       project_name=repo.name))
    return probes


def upgrade(clone_path: Path, *, add_agents: list[str] | None = None,
            all_agents: bool = False,
            murmurent_root: Path | None = None) -> list[Probe]:
    """Bring a ready repo up to the current murmurent release.

    - Legacy CHARTER.md bootstrap → a ``.murmurent.yaml`` marker is stamped
      (lab lifted from the charter). The CHARTER.md is **preserved** — it may
      be a project document (project/lead/members) still read by
      :mod:`core.projects`; readiness simply stops keying on it (issue #28,
      never drop project metadata during migration).
    - Marker schema migrated; ``bootstrap_version`` re-stamped.
    - Agent symlinks re-created against the current commons; new agents
      join via ``add_agents`` or ``all_agents=True`` (every commons
      agent). Content updates never need this — symlinks track the
      commons clone automatically.
    """
    repo = Path(clone_path).expanduser()
    r = readiness(repo)
    if not (r.marker or r.legacy_charter):
        return [Probe(name="upgrade", status="fail",
                      detail=f"{repo} is not murmurent-ready — adopt it first",
                      required=True)]
    probes: list[Probe] = []
    root = murmurent_root or commons_root()
    lab = str((r.marker or {}).get("lab") or "")
    agents = list((r.marker or {}).get("agents") or [])

    if r.legacy_charter and r.marker is None:
        # Stamp the marker from the legacy CHARTER bootstrap: lift the lab and
        # any existing agent links out of it. The CHARTER.md is PRESERVED — it
        # may be a project document still read by core.projects; readiness no
        # longer keys on it, so it just stops being a bootstrap marker (issue
        # #28). If it holds project metadata not yet in cert_projects, run
        # `cert_projects.backfill_from_charter()` to register it.
        try:
            from .frontmatter import parse_file
            meta = parse_file(repo / LEGACY_MARKER).meta or {}
            lab = str(meta.get("lab") or "")
        except Exception:  # noqa: BLE001
            pass
        # Lift whatever the legacy bootstrap actually wired. If it wired
        # nothing, fall back to the whole commons rather than to none: there
        # is no marker here, so there are no recorded picks to respect, and
        # readiness now counts LINKED agents. Migrating a legacy repo into a
        # permanent "partial" is not a migration.
        agents = linked_agents(repo) or _commons_agent_names(root)
        probes.append(Probe(name="upgrade", status="ok",
                            detail=f"stamped {MARKER_FILENAME} from legacy "
                                   "CHARTER.md bootstrap (CHARTER.md preserved)",
                            required=False))

    if all_agents:
        agents = _commons_agent_names(root) or agents
    for a in (add_agents or []):
        if a not in agents:
            agents.append(a)

    _write_marker(repo, lab=lab, agents=agents,
                  ready_since=str((r.marker or {}).get("ready_since") or "") or None)
    probes.append(Probe(name="marker", status="ok",
                        detail=f"schema {MARKER_SCHEMA}, bootstrap_version "
                               f"{_version()}", required=False))
    from . import project_cc_init as _cci
    probes.extend(_cci.bootstrap_local(repo, root, agents=agents,
                                       project_name=repo.name))
    return probes
