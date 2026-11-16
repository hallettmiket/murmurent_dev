"""Phase 3 of docs/harnesses_plan.md: the routing table. The lab's file
read with the harnesses' facts, a wrong row reported and dropped, the
project's sensitivity refusing a route by its place, the command line built
and not run, and `murmurent route`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from murmurent.commands.route_cmd import route_command
from murmurent.core import harness_policy as _hp
from murmurent.core import route_policy as _rp

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "models.yaml"


@pytest.fixture
def lab(monkeypatch, tmp_path):
    """No lab records; the template as the routes file; a fake project record."""
    monkeypatch.setattr(_hp, "lab_harnesses_path", lambda env=None: None)
    monkeypatch.setattr(_rp, "lab_models_path", lambda env=None: None)
    monkeypatch.delenv(_hp.HARNESSES_ENV, raising=False)
    monkeypatch.setenv(_rp.MODELS_ENV, str(TEMPLATE))
    tiers = {"open_proj": "standard", "patients": "protected", "pending": "restricted"}
    monkeypatch.setattr(_rp, "project_sensitivity",
                        lambda project: (tiers.get(project or "", "standard"),
                                         f"project {project}: {tiers.get(project or '', 'standard')}"))
    return tmp_path


def test_template_loads_with_no_problems(lab):
    policy = _rp.load_routes()
    assert policy.problems == []
    assert set(policy.kinds()) == {"software_build", "literature_scan"}
    r = policy.routes["literature_scan"]
    assert (r.harness, r.model, r.place, r.data, r.agent) == (
        "antigravity", "gemini-4-argon", "google_personal", ("standard",), "bookworm")


def test_wrong_rows_are_reported_and_the_rest_stand(lab, monkeypatch, tmp_path):
    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump({"routes": {
        "a": {"harness": "faraday", "model": "qwen"},
        "b": {"harness": "antigravity", "model": "gemini-4-argon", "place": "lab_server", "data": ["standard", "clinical", "secret"]},
        "c": {"harness": "claude_code"},
        "d": "nope",
        "e": {"harness": "claude_code", "model": "claude-opus-5-5"},
    }}), encoding="utf-8")
    monkeypatch.setenv(_rp.MODELS_ENV, str(path))
    policy = _rp.load_routes()
    text = "\n".join(policy.problems)
    assert "'faraday' is not one murmurent knows" in text
    assert "place 'lab_server' is not where antigravity runs" in text
    assert "data tier 'secret'" in text
    assert "c: no model named" in text and "route 'd' must be a mapping" in text
    assert set(policy.kinds()) == {"b", "e"}
    assert policy.routes["b"].place == "google_personal"
    assert policy.routes["b"].data == ("standard", "protected")   # clinical read as protected
    assert policy.routes["e"].data == _hp.TIERS                   # no data: every tier


def test_a_harness_the_lab_disabled_drops_its_rows(lab, monkeypatch, tmp_path):
    path = tmp_path / "harnesses.yaml"
    path.write_text("enabled: [claude_code]\n", encoding="utf-8")
    monkeypatch.setenv(_hp.HARNESSES_ENV, str(path))
    policy = _rp.load_routes()
    assert "literature_scan" not in policy.routes
    assert any("not allowed by the lab" in p for p in policy.problems)


def test_sensitivity_refuses_by_place(lab):
    assert _rp.route_for("literature_scan", project="open_proj").ok
    ans = _rp.route_for("literature_scan", project="patients")
    assert not ans.ok and "google_personal" in ans.refused and "standard data only" in ans.refused
    assert "project patients: protected" in ans.refused
    assert not _rp.route_for("literature_scan", project="pending").ok
    assert _rp.route_for("software_build", project="patients").ok
    missing = _rp.route_for("docking")
    assert missing.route is None and "no route: 'docking'" in missing.missing and "software_build" in missing.missing


def test_headless_command_is_built_not_run(lab):
    route = _rp.load_routes().routes["literature_scan"]
    assert _rp.headless_command(route, "find papers") == ["agy", "-p", "find papers", "--model", "gemini-4-argon"]
    route = _rp.load_routes().routes["software_build"]
    assert _rp.headless_command(route, "build it")[:2] == ["claude", "-p"]


def test_route_command(lab):
    runner = CliRunner()
    res = runner.invoke(route_command, [])
    assert res.exit_code == 0 and "literature_scan" in res.output and "software_build" in res.output
    res = runner.invoke(route_command, ["literature_scan", "--project", "open_proj", "--command", "find papers"])
    assert res.exit_code == 0, res.output
    assert "literature_scan: antigravity (gemini-4-argon) at google_personal, agent bookworm" in res.output
    assert "command (not run): agy -p 'find papers' --model gemini-4-argon" in res.output
    res = runner.invoke(route_command, ["literature_scan", "--project", "patients"])
    assert res.exit_code == 0 and res.output.startswith("refused:")
    res = runner.invoke(route_command, ["docking", "--json"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["route"] is None and data["ok"] is False and "no route" in data["missing"]
    res = runner.invoke(route_command, ["literature_scan", "--project", "patients", "--json"])
    data = json.loads(res.output)
    assert data["ok"] is False and data["route"]["harness"] == "antigravity" and data["refused"]


def test_route_with_no_file_says_so(lab, monkeypatch):
    monkeypatch.delenv(_rp.MODELS_ENV)
    res = CliRunner().invoke(route_command, [])
    assert res.exit_code == 0 and "no routes declared" in res.output
    res = CliRunner().invoke(route_command, ["software_build"])
    assert "no route" in res.output and "none declared" in res.output
