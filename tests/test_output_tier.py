"""The output tier: where an experiment's code writes, decided per experiment
or per repository, append_only unless said otherwise."""

from __future__ import annotations

from pathlib import Path

import pytest

from murmurent.commands import experiment_cmd, project_cmd
from murmurent.core import cluster as _cl
from murmurent.core import lab_vm
from murmurent.core import output_tier as _tier
from murmurent.core.frontmatter import parse_file


def _notebook(folder: Path, tier: str | None) -> None:
    line = f"output_tier: {tier}\n" if tier is not None else ""
    (folder / "notebook.md").write_text(f"---\nexperiment: x\n{line}---\n# x\n")


def test_default_is_append_only_outside_any_repository(tmp_path):
    got = _tier.resolve_output_tier(tmp_path)
    assert got.tier == "append_only" and got.source == "default" and not got.overwrites


def test_the_experiment_notebook_wins_over_the_repository(tmp_path):
    repo = tmp_path / "proj"
    exp = repo / "exp" / "1_build"
    exp.mkdir(parents=True)
    (repo / ".murmurent.yaml").write_text("name: proj\noutput_tier: append_only\n")
    _notebook(exp, "modifiable")
    got = _tier.resolve_output_tier(exp / "sub")  # a folder inside the experiment
    assert got.tier == "modifiable" and got.source == "experiment" and got.overwrites


def test_the_repository_sets_the_default_for_its_experiments(tmp_path):
    repo = tmp_path / "proj"
    exp = repo / "exp" / "1_build"
    exp.mkdir(parents=True)
    (repo / ".murmurent.yaml").write_text("name: proj\noutput_tier: modifiable\n")
    _notebook(exp, None)
    got = _tier.resolve_output_tier(exp)
    assert got.tier == "modifiable" and got.source == "repository"
    assert "modifiable" in got.describe() and ".murmurent.yaml" in got.describe()


def test_a_wrong_value_is_ignored_and_named(tmp_path):
    repo = tmp_path / "proj"
    exp = repo / "exp" / "1_build"
    exp.mkdir(parents=True)
    (repo / ".murmurent.yaml").write_text("name: proj\noutput_tier: scratch\n")
    _notebook(exp, "immutable")
    got = _tier.resolve_output_tier(exp)
    assert got.tier == "append_only" and got.source == "default"
    assert "immutable" in got.problem and "scratch" in got.problem


def test_legacy_and_sloppy_spellings_normalise():
    assert _tier.normalise_tier("refined") == "append_only"
    assert _tier.normalise_tier(" Modifiable ") == "modifiable"
    assert _tier.normalise_tier("append-only") == "append_only"
    assert _tier.normalise_tier("mothballed") is None
    assert _tier.normalise_tier(None) is None


def test_output_dir_follows_the_tier(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(tmp_path / "data"))
    assert _tier.experiment_output_dir("p", "1_a", "modifiable") == tmp_path / "data" / "modifiable" / "p" / "1_a"
    assert _tier.experiment_output_dir("p", "1_a", "append_only") == lab_vm.experiment_append_only_dir("p", "1_a")
    assert _tier.experiment_output_dir("p", "1_a", "nonsense") == lab_vm.experiment_append_only_dir("p", "1_a")


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_PROJECTS_ROOT", str(tmp_path / "repos"))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "lab-mgmt"))
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("MURMURENT_USER", "allie")
    (tmp_path / "lab-mgmt" / "projects").mkdir(parents=True)
    project_cmd.cmd_new("p", charter_path=None, members_csv="@allie", description="x",
                        sensitivity="standard", skip_github=True)
    return tmp_path


def test_experiment_new_records_the_tier_and_makes_the_folder(isolated_env):
    exp_dir = experiment_cmd.cmd_new("p", "build", performer=["@allie"], output_tier="modifiable")
    meta = parse_file(exp_dir / "notebook.md").meta
    assert meta["output_tier"] == "modifiable"
    assert (isolated_env / "data" / "modifiable" / "p" / "1_build").is_dir()
    assert _tier.resolve_output_tier(exp_dir).tier == "modifiable"

    plain = experiment_cmd.cmd_new("p", "fit", performer=["@allie"])
    assert parse_file(plain / "notebook.md").meta["output_tier"] == "append_only"
    assert lab_vm.experiment_append_only_dir("p", "2_fit").is_dir()


def test_experiment_new_takes_the_repository_default(isolated_env):
    from murmurent.core.projects import find_project
    repo = find_project("p")
    marker = repo.path / ".murmurent.yaml"
    text = marker.read_text() if marker.is_file() else ""
    marker.write_text(text.rstrip("\n") + "\noutput_tier: modifiable\n")
    exp_dir = experiment_cmd.cmd_new("p", "build", performer=["@allie"])
    assert parse_file(exp_dir / "notebook.md").meta["output_tier"] == "modifiable"


def test_experiment_new_refuses_an_unknown_tier(isolated_env):
    import click
    with pytest.raises(click.ClickException):
        experiment_cmd.cmd_new("p", "build", performer=["@allie"], output_tier="mothballed")
