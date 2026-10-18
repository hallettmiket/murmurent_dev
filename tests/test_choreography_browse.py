"""Browsing and installing published choreographies from the dashboard (#185).

The public index and git are replaced by fakes: no network.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from murmurent.commands import choreography_install_cmd as ci
from murmurent.core import adopt
from murmurent.core import choreography_registry as cr


def test_published_list_marks_installed(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(tmp_path))
    (tmp_path / "inhibition").mkdir()
    monkeypatch.setattr(ci, "_fetch_index", lambda url, timeout: [
        ("inhibition", "https://x/inhibition.git"), ("other", "https://x/other.git")])
    from murmurent.dashboard.server import create_app
    rows = TestClient(create_app()).get("/api/choreographies/published").json()["rows"]
    assert [(r["name"], r["installed"]) for r in rows] == [("inhibition", True), ("other", False)]


def test_published_list_reports_an_unreachable_index(monkeypatch):
    def down(url, timeout):
        raise ci.IndexUnavailable("could not reach the index (offline).\nmore")
    monkeypatch.setattr(ci, "_fetch_index", down)
    from murmurent.dashboard.server import create_app
    body = TestClient(create_app()).get("/api/choreographies/published").json()
    assert body["rows"] == [] and body["error"] == "could not reach the index (offline)."


def test_install_by_name(monkeypatch, tmp_path):
    clone = tmp_path / "other"
    clone.mkdir()
    monkeypatch.setattr(ci, "_resolve_name", lambda name, index_url, timeout: "https://x/other.git")
    monkeypatch.setattr(cr, "clone_choreography", lambda url, dest=None, branch="": clone)
    monkeypatch.setattr(cr, "read_marker", lambda c: cr.ChoreographyInfo(
        name="other", title="Other study", agents=["judge", "nonexistent_agent"]))
    monkeypatch.setattr(cr, "missing_agents", lambda info: ["nonexistent_agent"])
    adopted = []
    monkeypatch.setattr(adopt, "adopt_clone", lambda **kw: adopted.append(kw["clone_path"]))
    from murmurent.dashboard.server import create_app
    res = TestClient(create_app()).post("/api/choreographies/install", json={"name": "other"})
    body = res.json()
    assert res.status_code == 200 and body["adopted"] and adopted == [str(clone)]
    assert "nonexistent_agent" in body["detail"]
