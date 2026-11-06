"""Agents speak their verdicts in a language the machine chooses (#279).

The choice is a ``language <code>`` line in ``~/.murmurent/speak``. The
agent-event hook tells each subagent at start which language to write its
``Aloud:`` line in, and speaks that line with a voice for the language; the
installer fetches that voice; ``murmurent config speak-language`` writes the
line. English, the default, leaves everything as it was.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from murmurent.commands import install_cmd
from murmurent.core import speak as speak_mod

from tests.test_spoken_verdict_engines import HOOK, INSTALL, _run_hook, _voices, fakes, home  # noqa: F401


def _start(home: Path, agent: str = "adversary", speak: str = "1") -> str:
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "MURMURENT_SPEAK": speak,
           "MURMURENT_AGENT_LOG": str(home / "agents.log")}
    payload = json.dumps({"hook_event_name": "SubagentStart", "agent_type": agent, "agent_id": "x"})
    return subprocess.run(["bash", str(HOOK)], input=payload, text=True, env=env,
                          check=True, capture_output=True, timeout=30).stdout


def test_subagent_start_tells_the_agent_the_language(home: Path) -> None:
    (home / ".murmurent" / "speak").write_text("language fr_FR\n")
    out = json.loads(_start(home))
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SubagentStart"
    assert "French" in ctx and "Aloud:" in ctx
    assert not (home / "agents.log").read_text().strip()


def test_subagent_start_is_silent_for_english_and_when_muted(home: Path) -> None:
    assert _start(home) == ""
    (home / ".murmurent" / "speak").write_text("language en\n")
    assert _start(home) == ""
    (home / ".murmurent" / "speak").write_text("language de_DE\n")
    assert _start(home, speak="0") == ""


def test_an_unlisted_language_is_still_named_by_its_code(home: Path) -> None:
    (home / ".murmurent" / "speak").write_text("language xx_XX\nvoice xx_XX-someone-medium\n")
    ctx = json.loads(_start(home))["hookSpecificOutput"]["additionalContext"]
    assert "code xx_XX" in ctx


def test_the_language_voice_is_used_for_every_agent(home: Path, fakes: Path) -> None:
    voices = _voices(home, "en_US-lessac-medium", "en_GB-cori-high", "fr_FR-siwis-medium")
    (home / ".murmurent" / "speak").write_text("language fr_FR\n")
    calls = _run_hook(home, fakes, "adversary", "Pass.\nAloud: Le modèle tient.").read_text()
    assert f"piper -m {voices}/fr_FR-siwis-medium.onnx" in calls
    assert "cori" not in calls
    assert "Le modèle tient" in (home / "spoken.txt").read_text()


def test_a_voice_line_or_an_agent_line_wins_over_the_table(home: Path, fakes: Path) -> None:
    voices = _voices(home, "en_US-lessac-medium", "fr_FR-siwis-medium", "fr_FR-tom-medium", "fr_FR-upmc-medium")
    (home / ".murmurent" / "speak").write_text("language fr_FR\nvoice fr_FR-tom-medium\n")
    calls = _run_hook(home, fakes, "scribe", "Revised.").read_text()
    assert f"piper -m {voices}/fr_FR-tom-medium.onnx" in calls
    (home / "calls.log").unlink()
    (home / ".murmurent" / ".last_spoken").unlink(missing_ok=True)
    (home / ".murmurent" / "speak").write_text("language fr_FR\nscribe fr_FR-upmc-medium\n")
    calls = _run_hook(home, fakes, "scribe", "Revised again.").read_text()
    assert f"piper -m {voices}/fr_FR-upmc-medium.onnx" in calls


def test_no_english_voice_reads_a_french_line(home: Path, fakes: Path) -> None:
    """The language's voice is missing: say nothing with Piper rather than
    read French with an English voice. The engine then falls to `say`, which
    uses the Mac voice for the language."""
    _voices(home, "en_US-lessac-medium", "en_GB-cori-high")
    (home / ".murmurent" / "speak").write_text("language fr_FR\n")
    calls = _run_hook(home, fakes, "adversary", "Pass.", until="say").read_text()
    assert calls.startswith("say -v Thomas")
    assert "piper" not in calls


def test_install_script_fetches_the_language_voice_and_lists_languages(home: Path) -> None:
    out = subprocess.run(["bash", str(INSTALL), "languages"], text=True, capture_output=True, check=True).stdout
    rows = [l.split() for l in out.strip().splitlines()]
    assert ["fr_FR", "French", "fr_FR-siwis-medium", "Thomas"] in rows
    assert len(rows) == len(speak_mod.languages())
    assert [r[0] for r in rows] == [l.code for l in speak_mod.languages()]
    # Every language's voice is a real Piper voice name shape, and distinct.
    assert all(r[2].startswith(r[0] + "-") for r in rows)
    assert len({r[2] for r in rows}) == len(rows)


def test_speak_module_reads_and_writes_the_language_line(tmp_path: Path) -> None:
    p = tmp_path / "speak"
    p.write_text("engine piper\nadversary en_GB-cori-high\n")
    assert speak_mod.current(p) == ("", "")
    speak_mod.set_language("fr_FR", path=p)
    assert speak_mod.current(p) == ("fr_FR", "")
    assert p.read_text() == "engine piper\nadversary en_GB-cori-high\nlanguage fr_FR\n"
    speak_mod.set_language("xx_XX", voice="xx_XX-v-medium", path=p)
    assert speak_mod.current(p) == ("xx_XX", "xx_XX-v-medium")
    speak_mod.set_language("en", path=p)
    assert speak_mod.current(p) == ("", "")
    assert "language" not in p.read_text() and "voice" not in p.read_text()


def test_config_speak_language_command(tmp_path: Path, monkeypatch) -> None:
    from murmurent.cli import cli

    p = tmp_path / "speak"
    monkeypatch.setenv("MURMURENT_SPEAK_FILE", str(p))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")  # no piper: nothing is fetched
    r = CliRunner()
    assert "English" in r.invoke(cli, ["config", "speak-language"]).output
    out = r.invoke(cli, ["config", "speak-language", "--list"]).output
    assert "fr_FR" in out and "German" in out
    res = r.invoke(cli, ["config", "speak-language", "fr_FR"])
    assert res.exit_code == 0, res.output
    assert "French" in res.output and "Piper is not installed" in res.output
    assert "language fr_FR" in p.read_text()
    assert "French (fr_FR)" in r.invoke(cli, ["config", "speak-language"]).output
    bad = r.invoke(cli, ["config", "speak-language", "xx_XX"])
    assert bad.exit_code != 0 and "--voice" in bad.output
    assert "language fr_FR" in p.read_text()
    ok = r.invoke(cli, ["config", "speak-language", "xx_XX", "--voice", "xx_XX-v-medium"])
    assert ok.exit_code == 0 and "voice xx_XX-v-medium" in p.read_text()
    assert "English again" in r.invoke(cli, ["config", "speak-language", "en"]).output


def test_install_registers_the_subagent_start_hook(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    settings = json.loads(target.read_text(encoding="utf-8"))
    entries = settings["hooks"]["SubagentStart"]
    assert any("murmurent_log_agent_event.sh" in h["command"]
               for e in entries for h in e["hooks"])


def test_every_agent_and_the_rule_name_the_language_setting() -> None:
    root = Path(__file__).resolve().parents[1]
    for f in sorted((root / "agents").glob("*.md")):
        assert "speak-language" in f.read_text(), f.name
    assert "speak-language" in (root / "rules" / "headline_first.md").read_text()
