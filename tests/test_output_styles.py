"""The shipped output style stays valid, and practises what it requires.

An output style is the only mechanism that replaces Claude Code's own
instructions about how to write, rather than adding to them. Murmurent ships
one because every document this project produces is read by working
researchers, and the default register is written for software engineers.

These tests guard the two ways it could quietly stop working: frontmatter
Claude Code cannot read, and a rule the file itself breaks. The second matters
more than it looks. A style document that violates its own instruction is
evidence the instruction is unusable, and it is read by the model as an
example.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
STYLES_DIR = REPO / "output_styles"

EM_DASH = "—"


def _styles() -> list[Path]:
    return sorted(STYLES_DIR.glob("*.md"))


def _split_frontmatter(text: str) -> tuple[dict, str]:
    assert text.startswith("---\n"), "an output style must open with YAML frontmatter"
    _, fm, body = text.split("---\n", 2)
    return yaml.safe_load(fm) or {}, body


def test_there_is_at_least_one_style():
    assert _styles(), f"no output styles in {STYLES_DIR}"


@pytest.mark.parametrize("path", _styles(), ids=lambda p: p.name)
def test_frontmatter_is_readable_and_complete(path: Path):
    """Claude Code reads these fields; a typo makes the style silently absent."""
    meta, body = _split_frontmatter(path.read_text(encoding="utf-8"))

    assert isinstance(meta.get("name"), str) and meta["name"].strip()
    assert isinstance(meta.get("description"), str) and meta["description"].strip()
    assert body.strip(), "the body is the instruction; an empty one does nothing"

    # Known fields only. An unrecognised key is ignored rather than reported,
    # so a misspelling of keep-coding-instructions would silently drop the
    # coding instructions and change how code is written.
    assert set(meta) <= {"name", "description", "keep-coding-instructions",
                         "force-for-plugin"}, f"unknown frontmatter in {path.name}"


def test_plain_english_keeps_the_coding_instructions():
    """The style changes prose only.

    Without ``keep-coding-instructions: true`` a custom style REPLACES Claude
    Code's software engineering instructions, which would change how code is
    written, scoped and verified. That is not what this style is for.
    """
    meta, _ = _split_frontmatter(
        (STYLES_DIR / "plain_english.md").read_text(encoding="utf-8")
    )
    assert meta.get("keep-coding-instructions") is True


def test_the_style_contains_no_em_dash_outside_its_own_definition():
    """It forbids the em dash, so it may only contain the one it names.

    The single permitted occurrence is the line that quotes the character in
    order to prohibit it; naming it any other way leaves the reader guessing
    which character is meant.
    """
    text = (STYLES_DIR / "plain_english.md").read_text(encoding="utf-8")
    offenders = [
        f"line {i}: {line.strip()}"
        for i, line in enumerate(text.splitlines(), 1)
        if EM_DASH in line and "anywhere" not in line
    ]
    assert not offenders, (
        "the style file must not use the character it forbids: " + "; ".join(offenders)
    )


def test_setup_links_output_styles_into_claude():
    """Shipping the file is not enough; setup.sh has to link it.

    ``~/.claude/output-styles/`` is where Claude Code looks. The directory name
    differs from this repository's ``output_styles/`` (hyphen against
    underscore), which is exactly the sort of mismatch that silently links
    nothing.
    """
    setup = (REPO / "scripts" / "setup.sh").read_text(encoding="utf-8")
    assert "output_styles" in setup, "setup.sh does not read the source directory"
    assert ".claude/output-styles" in setup or "output-styles" in setup, \
        "setup.sh does not write the directory Claude Code reads"
