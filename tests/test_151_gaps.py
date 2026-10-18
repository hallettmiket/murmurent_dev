"""Gaps carried forward on #151: the access check uses a project's own data
folders, `murmurent project set`, project activity on the dashboard, and a
Slack warning when a job would fill its disk."""

from __future__ import annotations

from types import SimpleNamespace

from murmurent.core import project_access as pa
from murmurent.core import run_launcher as rl


def test_access_check_uses_the_records_data_folders(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(tmp_path))
    cp = SimpleNamespace(name="p", data_folders=("immutable/shared_src", "append_only/p_out"),
                         repos=())
    dirs = pa.project_data_dirs(cp, None)
    got = {(d.path.name, d.needs_write) for d in dirs}
    assert got == {("shared_src", False), ("p_out", True)}
    default = SimpleNamespace(name="p", data_folders=(), repos=())
    assert {d.label for d in pa.project_data_dirs(default, None)} == {
        "immutable data", "append_only data"}


def test_disk_warning_names_no_paths():
    card = SimpleNamespace(name="align", user="bob")
    text = rl.disk_warning_text(card, 5.4, 2 * 1024 ** 4)
    assert "align (bob)" in text and "about 5 h" in text and "/" not in text.split("free")[0][-40:]


def test_post_notice_sends_the_given_text():
    card = SimpleNamespace(project="p", notify={"enabled": True, "channel": "C1"},
                           state="running")
    sent = []
    ok = rl.post_notice(card, poster=lambda ch, text, token: sent.append(text) or True,
                        token_resolver=lambda project, group: "tok", text="custom line")
    assert ok and sent == ["custom line"]


def test_project_set_command(monkeypatch):
    from click.testing import CliRunner
    from murmurent.cli import cli
    from murmurent.commands import project_cmd
    from murmurent.core import cert_projects as cps
    calls = {}
    monkeypatch.setattr(cps, "get", lambda name, env=None: SimpleNamespace(lab="mh"))
    monkeypatch.setattr(cps, "upsert", lambda name, **kw: calls.update(kw))
    monkeypatch.setattr(project_cmd, "cmd_status", lambda name: 0)
    out = CliRunner().invoke(cli, ["project", "set", "p", "--data-folder", "append_only/p",
                                   "--retain-until", "2030-01-01", "--clear", "reads-from"])
    assert out.exit_code == 0, out.output
    assert calls == {"lab": "mh", "data_folders": ["append_only/p"], "reads_from": [],
                     "retain_until": "2030-01-01"}
    nothing = CliRunner().invoke(cli, ["project", "set", "p"])
    assert nothing.exit_code != 0 and "nothing to set" in nothing.output
