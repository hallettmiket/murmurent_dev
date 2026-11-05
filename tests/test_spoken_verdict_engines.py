"""The agent-event hook speaks a verdict with Piper when it is installed, with
the agent's own voice, and falls back to `say` when it is not (#272).

The hook is a bash script, so each test runs it with a fake PATH: a fake
`piper` and a fake player that record how they were called, and a fake
`say` that records too. HOME is a temporary directory so the on switch, the
voices and the once-only stamp are all private to the test.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "scripts" / "murmurent_log_agent_event.sh"
INSTALL = Path(__file__).resolve().parents[1] / "scripts" / "install_piper_voices.sh"


def _fake(bin_dir: Path, name: str, body: str) -> None:
    p = bin_dir / name
    p.write_text("#!/usr/bin/env bash\n" + body + "\n")
    p.chmod(0o755)


def _run_hook(home: Path, bin_dir: Path, agent: str, msg: str, until: str = "afplay") -> Path:
    env = {
        "HOME": str(home),
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "MURMURENT_SPEAK": "1",
        "MURMURENT_AGENT_LOG": str(home / "agents.log"),
        "TMPDIR": str(home),
    }
    payload = json.dumps(
        {"hook_event_name": "SubagentStop", "agent_type": agent, "last_assistant_message": msg}
    )
    subprocess.run(["bash", str(HOOK)], input=payload, text=True, env=env, check=True, timeout=30)
    calls = home / "calls.log"
    # The speech runs in a detached background job; wait for its last step.
    for _ in range(100):
        if calls.exists() and until in calls.read_text():
            break
        time.sleep(0.1)
    return calls


@pytest.fixture
def home(tmp_path: Path) -> Path:
    (tmp_path / ".murmurent").mkdir()
    return tmp_path


@pytest.fixture
def fakes(home: Path) -> Path:
    b = home / "bin"
    b.mkdir()
    log = home / "calls.log"
    _fake(b, "piper", f'echo "piper $*" >> "{log}"; cat >> "{home}/spoken.txt"; '
                      'for a in "$@"; do if [[ $prev == -f ]]; then : > "$a"; fi; prev=$a; done')
    _fake(b, "afplay", f'echo "afplay $*" >> "{log}"')
    _fake(b, "say", f'echo "say $*" >> "{log}"')
    return b


def _voices(home: Path, *names: str) -> Path:
    d = home / ".murmurent" / "voices"
    d.mkdir(parents=True, exist_ok=True)
    for n in names:
        (d / f"{n}.onnx").write_bytes(b"model")
        (d / f"{n}.onnx.json").write_text("{}")
    return d


def test_piper_speaks_the_agents_own_voice(home: Path, fakes: Path) -> None:
    voices = _voices(home, "en_US-lessac-medium", "en_GB-cori-high")
    calls = _run_hook(home, fakes, "adversary", "Pass, the folds are clean.").read_text()
    assert f"piper -m {voices}/en_GB-cori-high.onnx" in calls
    assert "afplay" in calls
    assert "say " not in calls


def test_piper_falls_back_to_the_default_voice_when_the_agents_is_missing(home: Path, fakes: Path) -> None:
    voices = _voices(home, "en_US-lessac-medium")
    calls = _run_hook(home, fakes, "scribe", "Revised, two changes.").read_text()
    assert f"piper -m {voices}/en_US-lessac-medium.onnx" in calls


def test_a_mac_say_name_left_in_the_speak_file_does_not_silence_piper(home: Path, fakes: Path) -> None:
    voices = _voices(home, "en_US-lessac-medium", "en_GB-cori-high")
    (home / ".murmurent" / "speak").write_text("adversary Tessa\n")
    calls = _run_hook(home, fakes, "adversary", "Pass.").read_text()
    assert f"piper -m {voices}/en_GB-cori-high.onnx" in calls


def test_without_piper_voices_the_mac_say_command_is_used(home: Path, fakes: Path) -> None:
    calls = _run_hook(home, fakes, "judge", "Presented, one candidate.", until="say").read_text()
    assert calls.startswith("say -v Daniel")
    assert "piper" not in calls


def test_the_speak_file_can_force_an_engine_and_override_a_voice(home: Path, fakes: Path) -> None:
    _voices(home, "en_US-lessac-medium", "en_GB-cori-medium")
    (home / ".murmurent" / "speak").write_text("engine piper\nadversary en_GB-cori-medium\n")
    calls = _run_hook(home, fakes, "adversary", "Questions, see the table.").read_text()
    assert "en_GB-cori-medium.onnx" in calls


def test_engine_say_is_honoured_even_when_piper_is_installed(home: Path, fakes: Path) -> None:
    _voices(home, "en_US-lessac-medium", "en_GB-cori-high")
    (home / ".murmurent" / "speak").write_text("engine say\n")
    calls = _run_hook(home, fakes, "adversary", "Pass.", until="say").read_text()
    assert calls.startswith("say -v Tessa")


def test_install_script_lists_the_same_table_as_the_hook() -> None:
    out = subprocess.run(["bash", str(INSTALL), "list"], text=True, capture_output=True, check=True).stdout
    for agent in ("adversary", "bookworm", "security_guard", "default"):
        assert agent in out, out
    assert "en_GB-cori-high" in out
    # One distinct voice per agent, so you can tell who finished without looking.
    voices = [line.split()[1] for line in out.strip().splitlines()]
    assert len(voices) == len(set(voices))


@pytest.mark.skipif(os.environ.get("CI") == "true", reason="needs bash features only")
def test_hook_header_names_both_engines() -> None:
    text = HOOK.read_text()
    assert "Piper" in text and "spd-say" in text


def test_piper_is_slowed_and_cleaned_by_default_and_tunable(home: Path, fakes: Path) -> None:
    _voices(home, "en_US-lessac-medium")
    calls = _run_hook(home, fakes, "scribe", "Revised.").read_text()
    assert "--length-scale 1.15 --noise-scale 0.4" in calls
    (home / "calls.log").unlink()
    (home / ".murmurent" / "speak").write_text("speed 1.3\nnoise 0.6\n")
    (home / ".murmurent" / ".last_spoken").unlink(missing_ok=True)
    calls = _run_hook(home, fakes, "scribe", "Revised again.").read_text()
    assert "--length-scale 1.3 --noise-scale 0.6" in calls


def test_the_aloud_line_is_spoken_instead_of_the_headline(home: Path, fakes: Path) -> None:
    _voices(home, "en_US-lessac-medium")
    msg = (
        "Pass — AUC 0.81 holds under LOSO CV; see /tmp/audit.md and https://example.org/x.\n"
        "Aloud: The model holds up. I re-ran it leaving each hospital out in turn and the accuracy barely moved.\n"
        "\n**Detail**\n- item"
    )
    _run_hook(home, fakes, "adversary", msg)
    spoken = (home / "spoken.txt").read_text()
    assert spoken.startswith("adversary. The model holds up.")
    assert "AUC" not in spoken and "example.org" not in spoken


def test_without_an_aloud_line_the_headline_is_spoken(home: Path, fakes: Path) -> None:
    _voices(home, "en_US-lessac-medium")
    _run_hook(home, fakes, "adversary", "Pass, the folds are clean. See /tmp/x.md\n\nDetail here.")
    spoken = (home / "spoken.txt").read_text()
    assert spoken.strip() == "adversary. Pass, the folds are clean."


def test_every_agent_asks_for_an_aloud_line() -> None:
    agents = Path(__file__).resolve().parents[1] / "agents"
    for f in sorted(agents.glob("*.md")):
        assert "Aloud:" in f.read_text(), f.name
