"""
Purpose: Decide which storage tier an experiment's code writes its output to.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-12
Input: An experiment folder (its ``notebook.md`` front matter), the
       repository's ``.murmurent.yaml`` marker, and the data root.
Output: The tier name, where it was decided, and the output folder.

Every experiment's output went to ``append_only/<project>/<experiment>/``,
where nothing is ever overwritten or deleted. That is right for a result a
paper will rest on and wrong for a build that rewrites hundreds of gigabytes
of intermediate files on every run: the folder only grows, and the server
pays for every attempt. The lab folder protocol already has
``modifiable/<project>/`` for working data that may change, and this module
lets an experiment or a project choose it.

Resolution, first match wins:

1. ``output_tier:`` in the experiment's ``notebook.md`` front matter;
2. ``output_tier:`` at the top of the repository's ``.murmurent.yaml``, the
   default for every experiment of that repository;
3. ``append_only``.

Only ``append_only`` and ``modifiable`` are tiers code may write to. The
legacy name ``refined`` reads as ``append_only``. Any other value is ignored
with its reason recorded, and the default stands, so a typo can never send
output somewhere the hooks do not know.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import lab_vm as _lv

DEFAULT_OUTPUT_TIER = "append_only"
OUTPUT_TIERS: tuple[str, ...] = ("append_only", "modifiable")
_LEGACY_NAMES = {"refined": "append_only"}
FIELD = "output_tier"


@dataclass(frozen=True)
class OutputTier:
    """Where an experiment's output goes and why."""

    tier: str
    source: str          # "experiment", "repository" or "default"
    problem: str = ""    # a value that was set but could not be used

    @property
    def overwrites(self) -> bool:
        """True when code may overwrite its own earlier output there."""
        return self.tier == "modifiable"

    def describe(self) -> str:
        where = {"experiment": "set in the experiment's notebook.md",
                 "repository": "the repository's default in .murmurent.yaml",
                 "default": "the default"}[self.source]
        text = f"{self.tier} ({where})"
        if self.problem:
            text += f"; {self.problem}"
        return text


def normalise_tier(value: object) -> str | None:
    """``append_only`` or ``modifiable`` for a recognised value, else ``None``."""
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "_")
    text = _LEGACY_NAMES.get(text, text)
    return text if text in OUTPUT_TIERS else None


def _read_notebook_tier(exp_dir: Path) -> tuple[object, bool]:
    """The ``output_tier`` value of ``<exp_dir>/notebook.md``, and whether the
    notebook exists at all."""
    notebook = exp_dir / "notebook.md"
    if not notebook.is_file():
        return None, False
    try:
        from .frontmatter import parse_file
        meta = parse_file(notebook).meta or {}
    except Exception:  # noqa: BLE001
        return None, True
    return meta.get(FIELD), True


def experiment_folder(folder: Path) -> Path | None:
    """The experiment folder ``folder`` is or sits inside: the nearest ancestor
    that holds a ``notebook.md``, else ``None``."""
    folder = Path(folder).expanduser()
    if folder.is_file():
        folder = folder.parent
    for candidate in (folder, *folder.parents):
        if (candidate / "notebook.md").is_file():
            return candidate
        if (candidate / _MARKER).is_file():
            break
    return None


_MARKER = ".murmurent.yaml"


def resolve_output_tier(folder: Path | str, marker: dict | None = None) -> OutputTier:
    """The output tier for work run from ``folder``.

    ``marker`` is the repository's ``.murmurent.yaml`` contents when the caller
    already has them; otherwise it is read from the nearest repository above
    ``folder``.
    """
    folder = Path(folder).expanduser()
    problems: list[str] = []

    exp_dir = experiment_folder(folder)
    if exp_dir is not None:
        raw, _ = _read_notebook_tier(exp_dir)
        tier = normalise_tier(raw)
        if tier:
            return OutputTier(tier, "experiment")
        if raw is not None:
            problems.append(f"notebook.md sets {FIELD}: {raw!r}, which is not one of "
                            f"{', '.join(OUTPUT_TIERS)}; ignored")

    if marker is None:
        marker = _marker_for(folder)
    raw = (marker or {}).get(FIELD)
    tier = normalise_tier(raw)
    if tier:
        return OutputTier(tier, "repository", "; ".join(problems))
    if raw is not None:
        problems.append(f".murmurent.yaml sets {FIELD}: {raw!r}, which is not one of "
                        f"{', '.join(OUTPUT_TIERS)}; ignored")
    return OutputTier(DEFAULT_OUTPUT_TIER, "default", "; ".join(problems))


def _marker_for(folder: Path) -> dict:
    try:
        from .repo import find_project_repo
        from .repo_ready import read_marker
    except Exception:  # noqa: BLE001
        return {}
    repo = find_project_repo(folder)
    if repo is None:
        return {}
    return read_marker(repo.path) or {}


def project_output_dir(project: str, tier: str, env: dict[str, str] | None = None) -> Path:
    """``<data-root>/<tier>/<project>`` for a tier code may write to."""
    tier = normalise_tier(tier) or DEFAULT_OUTPUT_TIER
    if tier == "modifiable":
        return _lv.project_modifiable_dir(project, env)
    return _lv.project_append_only_dir(project, env)


def experiment_output_dir(project: str, experiment: str, tier: str,
                          env: dict[str, str] | None = None) -> Path:
    """``<data-root>/<tier>/<project>/<experiment>``."""
    return project_output_dir(project, tier, env) / experiment
