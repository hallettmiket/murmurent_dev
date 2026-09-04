"""Obtaining a choreography from a git URL (#136).

A third party had no way to discover a choreography or install one; the only
path was `git clone` plus `murmurent repo adopt`, which needs the URL already.

The rule these tests pin down: **a choreography describes itself, and only a
repo that says it is one is treated as one.** Guessing would mean installing
arbitrary code as a choreography because it happened to be cloned by this
command.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from murmurent.core import choreography_registry as cr

MARKER = """\
kind: choreography
name: inhibition
title: Dance with Inhibition
summary: >
  Four approaches to covalent Pin1 inhibitors, judged against one shared
  control.
mode: compositional
target: Pin1 (PPIase, Cys113)
approaches: [t1_de_novo, t2_atra_crem, t3_reinvent, t4_combinatorial]
agents: [blacksmith, adversary, judge]
data:
  root_subdir: inhibition
  scale: ~54k molecules docked and ranked
requires:
  murmurent: ">=2026.9.0"
  gpu: true
"""


def _git_repo(path: Path, files: dict[str, str]) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    for name, text in files.items():
        (path / name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.email=t@e", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        check=True,
    )
    return path


def test_reads_a_choreographys_own_description(tmp_path):
    clone = tmp_path / "inhibition"
    clone.mkdir()
    (clone / cr.MARKER).write_text(MARKER, encoding="utf-8")

    info = cr.read_marker(clone)
    assert info.name == "inhibition"
    assert info.title == "Dance with Inhibition"
    assert info.approaches == ["t1_de_novo", "t2_atra_crem", "t3_reinvent",
                               "t4_combinatorial"]
    assert info.requires_gpu is True
    assert info.requires_murmurent == ">=2026.9.0"
    assert info.data_subdir == "inhibition"
    # The summary is folded to one line, so a YAML block scalar renders sanely.
    assert "\n" not in info.summary


def test_a_repo_without_a_marker_is_refused(tmp_path):
    clone = tmp_path / "plain"
    clone.mkdir()
    with pytest.raises(cr.ChoreographyError) as exc:
        cr.read_marker(clone)
    assert cr.MARKER in str(exc.value)
    assert "repo adopt" in str(exc.value), "should point at the plain-repo route"


def test_a_repo_of_another_kind_is_refused(tmp_path):
    """`kind` is an allowlist of one. A marker for something else is not a
    choreography, and treating it as one is how unrelated code gets installed."""
    clone = tmp_path / "other"
    clone.mkdir()
    (clone / cr.MARKER).write_text("kind: project\nname: x\n", encoding="utf-8")
    with pytest.raises(cr.ChoreographyError, match="not 'choreography'"):
        cr.read_marker(clone)


def test_a_marker_without_a_name_is_refused(tmp_path):
    clone = tmp_path / "anon"
    clone.mkdir()
    (clone / cr.MARKER).write_text("kind: choreography\n", encoding="utf-8")
    with pytest.raises(cr.ChoreographyError, match="no `name`"):
        cr.read_marker(clone)


def test_invalid_yaml_says_so(tmp_path):
    clone = tmp_path / "bad"
    clone.mkdir()
    (clone / cr.MARKER).write_text("kind: [unclosed\n", encoding="utf-8")
    with pytest.raises(cr.ChoreographyError, match="not valid YAML"):
        cr.read_marker(clone)


def test_clone_then_read_round_trip(tmp_path):
    src = _git_repo(tmp_path / "src", {cr.MARKER: MARKER, "README.md": "# x\n"})
    dest = tmp_path / "out" / "inhibition"
    got = cr.clone_choreography(str(src), dest=dest)
    assert got == dest
    assert cr.read_marker(got).title == "Dance with Inhibition"


def test_clone_refuses_to_overwrite(tmp_path):
    """A fresh clone must never quietly replace someone's existing directory."""
    src = _git_repo(tmp_path / "src", {cr.MARKER: MARKER})
    dest = tmp_path / "taken"
    dest.mkdir()
    (dest / "mine.txt").write_text("keep me", encoding="utf-8")
    with pytest.raises(cr.ChoreographyError, match="already exists"):
        cr.clone_choreography(str(src), dest=dest)
    assert (dest / "mine.txt").read_text(encoding="utf-8") == "keep me"


def test_a_failed_clone_reports_gits_own_message(tmp_path):
    with pytest.raises(cr.ChoreographyError, match="git clone failed"):
        cr.clone_choreography(str(tmp_path / "does-not-exist"),
                              dest=tmp_path / "out")


def test_missing_agents_are_reported_not_installed(tmp_path, monkeypatch):
    """A choreography naming an agent nobody has is a fact to surface up front."""
    from murmurent.core import commons

    fake = tmp_path / "commons"
    (fake / "agents").mkdir(parents=True)
    for name in ("blacksmith", "judge"):
        (fake / "agents" / f"{name}.md").write_text("x", encoding="utf-8")
    monkeypatch.setenv("MURMURENT_COMMONS_ROOT", str(fake))

    info = cr.ChoreographyInfo(name="x", agents=["blacksmith", "adversary", "judge"])
    assert cr.missing_agents(info) == ["adversary"]


# ---------------------------------------------------------------------------
# the public index (#136, third piece): locations only, and install-by-name
# ---------------------------------------------------------------------------

INDEX = """\
# comments and blank lines are skipped

inhibition\thttps://github.com/tt8804/inhibition_public.git
half_a_row
"""


def _index_url(tmp_path, text=INDEX):
    p = tmp_path / "choreographies.tsv"
    p.write_text(text, encoding="utf-8")
    return p.as_uri()


def test_index_rows_are_name_and_url(tmp_path):
    from murmurent.commands import choreography_install_cmd as ci

    rows = ci._fetch_index(_index_url(tmp_path), 5.0)
    assert rows == [("inhibition",
                     "https://github.com/tt8804/inhibition_public.git")]


def test_a_row_with_no_url_is_dropped_not_offered(tmp_path):
    """A half-filled row must not become something the user can try to install."""
    from murmurent.commands import choreography_install_cmd as ci

    with pytest.raises(ci.IndexUnavailable, match="not in the public index"):
        ci._resolve_name("half_a_row", index_url=_index_url(tmp_path),
                         timeout=5.0)


def test_install_by_name_resolves_through_the_index(tmp_path):
    from murmurent.commands import choreography_install_cmd as ci

    url = ci._resolve_name("inhibition", index_url=_index_url(tmp_path),
                           timeout=5.0)
    assert url == "https://github.com/tt8804/inhibition_public.git"


def test_an_unknown_name_lists_the_known_ones_rather_than_guessing(tmp_path):
    """Installing a repo because its name was close is worse than being told."""
    from murmurent.commands import choreography_install_cmd as ci

    with pytest.raises(ci.IndexUnavailable, match="Published: inhibition"):
        ci._resolve_name("inhibiton", index_url=_index_url(tmp_path),
                         timeout=5.0)


def test_a_missing_index_still_points_at_the_url_route(tmp_path):
    from murmurent.commands import choreography_install_cmd as ci

    missing = (tmp_path / "nope.tsv").as_uri()
    with pytest.raises(ci.IndexUnavailable, match="repository URL"):
        ci._fetch_index(missing, 5.0)


def test_a_git_url_never_touches_the_index(tmp_path):
    """The index is a convenience for finding one, not a gate in front of it."""
    from murmurent.commands import choreography_install_cmd as ci

    src = _git_repo(tmp_path / "src", {cr.MARKER: MARKER})
    rc = ci.cmd_install(source=str(src), dest=str(tmp_path / "out"), branch="",
                        lab="", adopt=False,
                        index_url="http://127.0.0.1:1/unreachable.tsv")
    assert rc == 0
    assert (tmp_path / "out" / cr.MARKER).is_file()
