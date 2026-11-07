"""
Purpose: Tests for the agent-movie hook: it reminds once per session when an
         agent file is edited and its movie is stamped with another hash of
         that file, and stays silent otherwise.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-07
Input:   A temp commons root with agents/ and training/index.yaml.
Output:  Assertions.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from murmurent.commands import install_cmd
from murmurent.hooks import agent_movie as hook

INDEX = """# header
movies:
- agent: oracle
  title: The oracle
  version: 2026.11.0
  date: 2026-11-07
  agent_sha256: {sha}
  file: training/agents/oracle/oracle_narrated.mp4
  make: python3 training/agents/oracle/make.py
  seconds: 134
  chapters:
    - ["0:00", "Welcome"]
- agent: bookworm
  version: 2026.11.0
  date: 2026-11-07
  agent_sha256: deadbeef
"""


def _root(tmp_path: Path, monkeypatch, agent_text: str = "# The oracle\n", stamped: str | None = None) -> Path:
    root = tmp_path / "commons"
    (root / "agents").mkdir(parents=True)
    (root / "training").mkdir()
    (root / "agents" / "oracle.md").write_text(agent_text, encoding="utf-8")
    sha = stamped or hashlib.sha256(agent_text.encode()).hexdigest()
    (root / "training" / "index.yaml").write_text(INDEX.format(sha=sha), encoding="utf-8")
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "home"))
    return root


def _call(path: str, session: str = "s1", tool: str = "Edit") -> dict:
    return {"tool_name": tool, "tool_input": {"file_path": path}, "session_id": session}


def test_silent_when_the_movie_matches_the_file(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    assert hook.evaluate(_call(str(root / "agents" / "oracle.md")), root) is None


def test_prompts_once_when_the_file_differs_from_the_stamp(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch, stamped="0" * 64)
    note = hook.evaluate(_call(str(root / "agents" / "oracle.md")), root)
    assert note is not None
    assert "agents/oracle.md changed" in note
    assert "2026.11.0" in note and "2026-11-07" in note
    assert "python3 training/agents/oracle/make.py" in note
    # the same session is not told twice
    assert hook.evaluate(_call(str(root / "agents" / "oracle.md")), root) is None
    # another session is
    assert hook.evaluate(_call(str(root / "agents" / "oracle.md"), session="s2"), root) is not None


def test_ignores_other_files_and_tools(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch, stamped="0" * 64)
    assert hook.evaluate(_call(str(root / "docs" / "oracle.md")), root) is None
    assert hook.evaluate(_call(str(root / "agents" / "oracle.md"), tool="Read"), root) is None
    assert hook.evaluate({"tool_name": "Bash", "tool_input": {"command": "vi agents/oracle.md"}}, root) is None


def test_silent_for_an_agent_with_no_movie(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch, stamped="0" * 64)
    (root / "agents" / "newcomer.md").write_text("# new\n", encoding="utf-8")
    assert hook.evaluate(_call(str(root / "agents" / "newcomer.md")), root) is None


def test_main_writes_hook_output(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch, stamped="0" * 64)
    monkeypatch.setenv("MURMURENT_COMMONS_ROOT", str(root))
    out = io.StringIO()
    code = hook.main(stdin=io.StringIO(json.dumps(_call(str(root / "agents" / "oracle.md")))), stdout=out)
    assert code == 0
    payload = json.loads(out.getvalue())
    assert payload["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "re-render it?" in payload["hookSpecificOutput"]["additionalContext"]


def test_main_is_quiet_on_garbage():
    out = io.StringIO()
    assert hook.main(stdin=io.StringIO("not json"), stdout=out) == 0
    assert out.getvalue() == ""


def test_parse_index_reads_the_real_file():
    real = Path(__file__).resolve().parents[1] / "training" / "index.yaml"
    movies = hook.parse_index(real.read_text(encoding="utf-8"))
    assert "oracle" in movies
    assert len(movies["oracle"]["agent_sha256"]) == 64


def test_install_registers_the_hook(tmp_path):
    target = tmp_path / "settings.json"
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    settings = json.loads(target.read_text(encoding="utf-8"))
    names = [h.get("name") for e in settings["hooks"]["PostToolUse"] for h in e["hooks"]]
    assert "murmurent-agent-movie" in names
