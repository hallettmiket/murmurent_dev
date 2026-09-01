"""`uv tool install murmurent` must be a COMPLETE install (#133).

Until 2026.9.3 the wheel held `src/murmurent` only, so a PyPI install produced
a CLI with no agents, rules or skills to wire up and every install needed a
clone first. The wheel now force-includes the commons.

These tests are cheap stand-ins for the expensive check (build a wheel, install
it into a clean HOME, run `murmurent install`), which is documented in
DEVELOPING.md and should be run before a release. They catch the specific way
this broke in development: `CLAUDE.md` was force-included into the wheel but
missing from the sdist's include list, and since the wheel is built FROM the
sdist, the build failed. A force-include that names a file the sdist does not
carry is the shape to guard against.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
WHEEL = PYPROJECT["tool"]["hatch"]["build"]["targets"]["wheel"]
SDIST = PYPROJECT["tool"]["hatch"]["build"]["targets"]["sdist"]
FORCED = WHEEL["force-include"]

# What core.commons.commons_root() and commands/setup_cmd.py expect to find.
REQUIRED = ("agents", "rules", "skills", "CLAUDE.md")


@pytest.mark.parametrize("name", REQUIRED)
def test_the_wheel_ships_what_setup_needs(name: str):
    assert name in FORCED, (
        f"{name!r} is not force-included into the wheel, so a PyPI install "
        "would wire up an incomplete commons. See [tool.hatch.build.targets."
        "wheel.force-include]."
    )
    assert FORCED[name].startswith("murmurent/commons/"), (
        f"{name!r} must land under murmurent/commons/ where commons_root() looks"
    )


@pytest.mark.parametrize("name", sorted(FORCED))
def test_every_forced_include_exists_on_disk(name: str):
    assert (REPO / name).exists(), (
        f"force-include names {name!r}, which does not exist. The build fails "
        "with FileNotFoundError rather than shipping a partial wheel."
    )


@pytest.mark.parametrize("name", sorted(FORCED))
def test_every_forced_include_is_also_in_the_sdist(name: str):
    """The wheel is built FROM the sdist, so anything forced must be in it.

    This is the exact failure hit while implementing it: CLAUDE.md was forced
    into the wheel but absent from the sdist include list, and the build died.
    """
    top = name.split("/")[0]
    assert top in SDIST["include"], (
        f"{name!r} is force-included into the wheel but {top!r} is not in the "
        "sdist include list. The wheel builds from the sdist, so this fails "
        "the build."
    )


def test_deployment_rules_are_excluded_from_the_package():
    """`rules/local/` must never be embedded in a wheel built from this clone."""
    for target in (WHEEL, SDIST):
        assert "rules/local" in target.get("exclude", []), (
            "rules/local holds this deployment's private repos and Slack IDs. "
            "force-include of 'rules' would otherwise embed it in the wheel."
        )


def test_commons_root_prefers_a_clone_over_the_packaged_copy(tmp_path, monkeypatch):
    """A developer editing an agent must see the edit take effect."""
    from murmurent.core import commons

    clone = tmp_path / "clone"
    for d in ("agents", "rules", "skills"):
        (clone / d).mkdir(parents=True)
    (clone / "agents" / "oracle.md").write_text("x", encoding="utf-8")

    monkeypatch.delenv("MURMURENT_COMMONS_ROOT", raising=False)
    monkeypatch.setattr(commons, "murmurent_repo_root", lambda: clone)
    assert commons.commons_root() == clone
    assert commons.commons_source() == "clone"


def test_an_empty_clone_dir_does_not_beat_the_packaged_copy(tmp_path, monkeypatch):
    """A failed clone must not leave a member with no agents at all.

    The directory exists but holds nothing; resolving by name rather than by
    content would hand back an empty commons and wire up nothing. Only
    meaningful when a packaged copy exists to fall back to, which is the case
    in a real install but not in a source checkout, so it is supplied here.
    """
    from murmurent.core import commons

    empty = tmp_path / "repos" / "murmurent"
    empty.mkdir(parents=True)

    packaged = tmp_path / "site-packages" / "murmurent" / "commons"
    for d in ("agents", "rules", "skills"):
        (packaged / d).mkdir(parents=True)
    (packaged / "agents" / "oracle.md").write_text("x", encoding="utf-8")

    monkeypatch.delenv("MURMURENT_COMMONS_ROOT", raising=False)
    monkeypatch.setattr(commons, "murmurent_repo_root", lambda: empty)
    monkeypatch.setattr(commons, "packaged_commons_root", lambda: packaged)
    assert commons.commons_root() == packaged
