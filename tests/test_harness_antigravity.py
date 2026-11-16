"""Phase 1 of docs/harnesses_plan.md: the commons rendered into Antigravity,
the lab's and the machine's choice of harnesses, `murmurent install
--harness`, and the rule-6 acceptance test: a machine with no ~/.claude at
all installs, lists and passes doctor. Antigravity itself is never run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from murmurent.commands import harness_cmd
from murmurent.core import harness_antigravity as _ag
from murmurent.core import harness_policy as _hp

COMMONS = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(monkeypatch, tmp_path):
    """A home of its own, no lab file, no choice made, Antigravity 'present'."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("MURMURENT_COMMONS_ROOT", str(COMMONS))
    monkeypatch.delenv(_hp.HARNESSES_ENV, raising=False)
    monkeypatch.delenv(_hp.MACHINE_ENV, raising=False)
    monkeypatch.setattr(_hp, "lab_harnesses_path", lambda env=None: None)
    monkeypatch.setattr(_hp, "_machine_file", lambda: tmp_path / ".murmurent" / "machine.yaml")
    (tmp_path / _ag.APP_DATA_DIR).mkdir(parents=True)     # the App's data folder = present
    return tmp_path


def _install(home: Path, **kw) -> _hp.InstallReport:
    return _hp.profiles()["antigravity"].install(home, COMMONS, **kw)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_rules_get_a_trigger_and_the_voice_and_overview_are_considered(home):
    rep = _install(home)
    rules = home / _ag.CONFIG_DIR / _ag.RULES_DIR
    names = sorted(p.name for p in rules.glob("murmurent_*.md"))
    assert "murmurent_voice.md" in names and "murmurent_plain_english.md" in names
    assert "murmurent_data-storage.md" in names
    text = (rules / "murmurent_voice.md").read_text(encoding="utf-8")
    assert text.startswith("---\ntrigger: always_on\n---\n\n")
    schema = (rules / "murmurent_oracle_schema.md").read_text(encoding="utf-8")
    assert "trigger: model_decision" in schema and "description:" in schema
    # The commons overview is over Antigravity's per-file limit: skipped and said.
    assert any("CLAUDE.md" in s and "24,000" in s for s in rep.skipped)
    assert not (rules / "murmurent_CLAUDE.md").exists()


def test_a_rule_over_the_limit_is_skipped_not_cut(home, tmp_path):
    big = tmp_path / "big.md"
    big.write_text("x" * (_ag.RULE_FILE_LIMIT + 1), encoding="utf-8")
    out = _hp.profiles()["antigravity"].render_rules([big], home)
    assert out[0].skipped and "big.md" in out[0].skipped


def test_agents_become_subagents_with_inherit_and_no_wrong_tools(home):
    _install(home)
    agents = home / _ag.CONFIG_DIR / _ag.AGENTS_DIR
    oracle = (agents / "oracle.md").read_text(encoding="utf-8")
    front = oracle.split("---")[1]
    assert oracle.startswith("---\nname: oracle\n")
    assert "model: inherit" in front
    assert "required_tools" not in front and "freeze" not in front
    assert "tools:" not in front             # Glob and Grep have no confirmed name yet
    assert "MANDATORY OUTPUT RULE" in oracle  # the body is the prompt, unchanged
    assert len(list(agents.glob("*.md"))) == len(list((COMMONS / "agents").glob("*.md")))


def test_an_agent_whose_tools_all_map_gets_a_tools_line(home, tmp_path):
    src = tmp_path / "tiny.md"
    src.write_text("---\nname: tiny\ndescription: a test\nrequired_tools:\n- Read\n- Bash\n---\n\nHello.\n",
                   encoding="utf-8")
    out = _hp.profiles()["antigravity"].render_agents([src], home)
    assert "tools:\n- run_command\n- view_file\n" in out[0].text


def test_skills_are_linked_except_those_meant_to_be_typed(home):
    rep = _install(home)
    skills = home / _ag.CONFIG_DIR / _ag.SKILLS_DIR
    assert (skills / "murmurent-push").is_symlink()
    assert not (skills / "murmurent-machines").exists()
    assert any("murmurent-machines" in s for s in rep.skipped)
    rep = _install(home, all_skills=True)
    assert (skills / "murmurent-machines").is_symlink()


def test_mcp_config_merges_and_keeps_other_servers(home):
    cfg = home / _ag.CONFIG_DIR / _ag.MCP_FILE
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"mcpServers": {"theirs": {"command": "x"}}}), encoding="utf-8")
    _install(home)
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert "theirs" in data["mcpServers"]
    assert "murmurent-oracle" in data["mcpServers"]
    assert data["mcpServers"]["murmurent-oracle"]["args"] == ["-m", "murmurent.mcp.oracle_server"]


def test_dry_run_writes_nothing_and_reports_everything(home):
    rep = _install(home, dry_run=True)
    assert not (home / _ag.CONFIG_DIR).exists()
    assert len(rep.written) > 20 and len(rep.linked) >= 5
    assert any("telemetry" in w for w in rep.warnings)   # the data-handling warning, every time


def test_install_is_idempotent_and_installed_reports(home):
    prof = _hp.profiles()["antigravity"]
    assert prof.installed(home).yes is False
    _install(home)
    first = {p: p.read_text() for p in (home / _ag.CONFIG_DIR).rglob("*.md")}
    _install(home)
    second = {p: p.read_text() for p in (home / _ag.CONFIG_DIR).rglob("*.md")}
    assert first == second
    assert prof.installed(home).yes is True


# ---------------------------------------------------------------------------
# The choice
# ---------------------------------------------------------------------------


def test_machine_choice_is_recorded_and_kept_beside_other_settings(home):
    machine = home / ".murmurent" / "machine.yaml"
    machine.parent.mkdir()
    machine.write_text("repos_root: ~/repos\n", encoding="utf-8")
    assert _hp.machine_harnesses() == []
    _hp.set_machine_harnesses(["antigravity"])
    data = yaml.safe_load(machine.read_text(encoding="utf-8"))
    assert data == {"repos_root": "~/repos", "harnesses": ["antigravity"]}
    assert _hp.machine_harnesses() == ["antigravity"]


def test_env_overrides_the_choice(home, monkeypatch):
    monkeypatch.setenv(_hp.MACHINE_ENV, "claude_code, antigravity")
    assert _hp.machine_harnesses() == ["claude_code", "antigravity"]


def test_chosen_falls_back_to_what_is_present(home):
    # No ~/.claude and no `claude` on the path in this home... but `claude` may
    # be on the real PATH; only assert Antigravity, which is present by fixture.
    chosen = _hp.chosen_harnesses()
    assert "antigravity" in chosen
    _hp.set_machine_harnesses(["claude_code"])
    assert _hp.chosen_harnesses() == ["claude_code"]


def test_lab_enabled_list_restricts_and_reports(home, monkeypatch, tmp_path):
    path = tmp_path / "harnesses.yaml"
    path.write_text(yaml.safe_dump({"enabled": ["claude_code", "faraday"],
                                    "harnesses": {"antigravity": {"place": "google_cloud"}}}), encoding="utf-8")
    monkeypatch.setenv(_hp.HARNESSES_ENV, str(path))
    policy = _hp.load_harnesses()
    assert policy.enabled == ("claude_code",)
    assert policy.allowed("claude_code") and not policy.allowed("antigravity")
    assert any("faraday" in p for p in policy.problems)
    runner = CliRunner()
    res = runner.invoke(harness_cmd.harness_group, ["enable", "antigravity"])
    assert res.exit_code != 0 and "not allowed by the lab" in res.output
    res = runner.invoke(harness_cmd.harness_group, ["list"])
    assert "not allowed by the lab" in res.stdout


def test_enable_and_disable(home):
    runner = CliRunner()
    res = runner.invoke(harness_cmd.harness_group, ["enable", "antigravity"])
    assert res.exit_code == 0, res.output
    assert "this machine's harnesses: antigravity" in res.output
    res = runner.invoke(harness_cmd.harness_group, ["enable", "nope"])
    assert res.exit_code != 0 and "not a harness murmurent knows" in res.output
    res = runner.invoke(harness_cmd.harness_group, ["disable", "antigravity"])
    assert "(none)" in res.output
    assert _hp.machine_harnesses() == []


def test_install_targets(home):
    assert harness_cmd.install_targets([], hooks_only=True) == ["claude_code"]
    assert harness_cmd.install_targets(["antigravity"]) == ["antigravity"]
    assert _hp.machine_harnesses() == ["antigravity"]          # recorded
    assert harness_cmd.install_targets([]) == ["antigravity"]   # the machine's choice
    _hp.set_machine_harnesses([])
    assert "antigravity" in harness_cmd.install_targets([])    # what is present
    with pytest.raises(Exception, match="not a harness"):
        harness_cmd.install_targets(["nope"])


# ---------------------------------------------------------------------------
# Rule 6: a machine with no ~/.claude at all
# ---------------------------------------------------------------------------


def test_a_machine_without_claude_code_installs_lists_and_passes_doctor(home, monkeypatch):
    from murmurent.cli import cli

    monkeypatch.setenv("MURMURENT_CC_DIR", str(home / ".claude"))   # which does not exist
    _hp.set_machine_harnesses(["antigravity"])
    runner = CliRunner()
    res = runner.invoke(cli, ["install", "--harness", "antigravity", "--no-launcher"])
    assert res.exit_code == 0, res.output
    assert "antigravity: writing the commons into" in res.output
    assert not (home / ".claude").exists()
    res = runner.invoke(cli, ["harness", "list"])
    assert res.exit_code == 0, res.output
    assert "antigravity" in res.stdout and "yes" in res.stdout
    res = runner.invoke(cli, ["doctor"])
    assert res.exit_code == 0, res.output
    assert "antigravity: rules, skills, MCP servers and the governance hooks in place" in res.output
    assert "agents:" not in res.output and "hooks:" not in res.output   # Claude Code's checks did not run
    assert "✗" not in res.output
