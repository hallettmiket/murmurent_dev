"""Tests for POST /api/vault/sync — the one-click "Sync vault" endpoint
(issue #80 Wave 3, Part A).

The endpoint pushes local vault edits, then ff-pulls what other machines
pushed, and returns a structured ``{pushed, pulled, diverged, message, as_of}``.
We monkeypatch ``murmurent.core.vault_sync`` so nothing touches git, the
network, or a real vault — the endpoint imports the module lazily inside the
handler, so patching the module attributes is what the handler sees.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from murmurent.core import vault_sync as VS
from murmurent.core.vault_sync import VaultSyncResult
from murmurent.dashboard.server import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _patch(monkeypatch, *, root, result):
    monkeypatch.setattr(VS, "personal_vault_root", lambda: root)
    monkeypatch.setattr(VS, "sync", lambda *a, **k: result)
    monkeypatch.setattr(VS, "vault_info",
                        lambda: VaultSyncResult(path=str(root or ""), is_git=True,
                                                ok=True, detail="", as_of="2026-07-20T10:00:00"))


def test_sync_pushes_and_pulls(client, monkeypatch, tmp_path):
    _patch(monkeypatch, root=tmp_path / "vault",
           result=VS.SyncResult(ok=True, pushed=True, pulled=True, diverged=False,
                                kept_local=[], message="synced", as_of="2026-07-21T09:00:00"))
    body = client.post("/api/vault/sync").json()
    assert body["pushed"] is True
    assert body["pulled"] is True
    assert body["diverged"] is False
    assert body["as_of"] == "2026-07-21T09:00:00"


def test_sync_divergence_flagged(client, monkeypatch, tmp_path):
    _patch(monkeypatch, root=tmp_path / "vault",
           result=VS.SyncResult(ok=False, pushed=False, pulled=False, diverged=True,
                                kept_local=[], message="this machine and another changed "
                                "the same note; nothing was lost."))
    body = client.post("/api/vault/sync").json()
    assert body["diverged"] is True
    assert body["pulled"] is False
    assert "nothing was lost" in body["message"]


def test_sync_reports_notes_kept_on_this_machine(client, monkeypatch, tmp_path):
    _patch(monkeypatch, root=tmp_path / "vault",
           result=VS.SyncResult(ok=True, pushed=True, pulled=True, diverged=False,
                                kept_local=["oracle/patients.md"],
                                message="synced; 1 protected or restricted note(s) kept"))
    body = client.post("/api/vault/sync").json()
    assert body["kept_local"] == ["oracle/patients.md"]


def test_sync_transient_failure_not_divergence(client, monkeypatch, tmp_path):
    _patch(monkeypatch, root=tmp_path / "vault",
           result=VS.SyncResult(ok=False, pushed=False, pulled=False, diverged=False,
                                kept_local=[], message="git timed out after 60s"))
    body = client.post("/api/vault/sync").json()
    assert body["diverged"] is False
    assert body["pulled"] is False
    assert body["pushed"] is False


def test_sync_no_vault_degrades(client, monkeypatch):
    # personal_vault_root() is None → calm "No personal vault" message, no error.
    monkeypatch.setattr(VS, "personal_vault_root", lambda: None)
    r = client.post("/api/vault/sync")
    assert r.status_code == 200
    body = r.json()
    assert body["pushed"] is False and body["pulled"] is False and body["diverged"] is False
    assert "no personal vault" in body["message"].lower()


def test_is_divergence_helper():
    assert VS.is_divergence("fatal: Not possible to fast-forward, aborting.") is True
    assert VS.is_divergence("Your branch and 'origin/main' have diverged") is True
    assert VS.is_divergence("Already up to date.") is False
    assert VS.is_divergence("git pull timed out after 60s") is False
    assert VS.is_divergence("") is False
