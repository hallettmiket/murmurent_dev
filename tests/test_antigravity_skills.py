"""Skills linked into ``~/.agents/skills`` for Antigravity (lookout #369, item 2).

Antigravity 2.36.0 finds skills in ``~/.agents/skills``. ``murmurent setup``
links the commons skills there too, but only when Antigravity is on the machine
(``~/.gemini`` exists) or the shared folder already does, and it never touches a
member's own skill directory. Everything is redirected into ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from murmurent.commands import setup_cmd


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "commons"
    (root / "agents").mkdir(parents=True)
    (root / "agents" / "oracle.md").write_text("# oracle\n", encoding="utf-8")
    skill = root / "skills" / "murmurent-push"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    monkeypatch.setenv("MURMURENT_COMMONS_ROOT", str(root))
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("MURMURENT_CC_DIR", str(home / ".claude"))
    monkeypatch.setenv("MURMURENT_AGENTS_DIR", str(home / ".agents"))
    return home


def test_no_antigravity_no_shared_folder(home):
    assert setup_cmd.cmd_setup(show_next_step=False) == 0
    assert (home / ".claude" / "skills" / "murmurent-push").is_symlink()
    assert not (home / ".agents").exists()


def test_antigravity_gets_the_skills(home):
    (home / ".gemini").mkdir()
    assert setup_cmd.cmd_setup(show_next_step=False) == 0
    link = home / ".agents" / "skills" / "murmurent-push"
    assert link.is_symlink()
    assert (link / "SKILL.md").is_file()


def test_existing_shared_folder_is_enough(home):
    (home / ".agents" / "skills").mkdir(parents=True)
    setup_cmd.cmd_setup(show_next_step=False)
    assert (home / ".agents" / "skills" / "murmurent-push").is_symlink()


def test_a_members_own_skill_is_left_alone(home):
    own = home / ".agents" / "skills" / "murmurent-push"
    own.mkdir(parents=True)
    (own / "SKILL.md").write_text("# mine\n", encoding="utf-8")
    setup_cmd.cmd_setup(show_next_step=False)
    assert not own.is_symlink()
    assert (own / "SKILL.md").read_text(encoding="utf-8") == "# mine\n"


def test_a_redirected_install_leaves_the_real_home_alone(home, monkeypatch):
    monkeypatch.delenv("MURMURENT_AGENTS_DIR")
    assert setup_cmd._agents_dir() is None


def test_setup_sh_links_the_shared_folder():
    setup = (Path(__file__).resolve().parents[1] / "scripts" / "setup.sh").read_text(encoding="utf-8")
    assert ".agents/skills" in setup
    assert ".gemini" in setup
