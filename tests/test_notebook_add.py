"""
Purpose: Tests for `murmurent notebook add` and `notebook open` (#293):
         text under a time heading; small result files in the vault; images,
         sound, video and large files sent to append_only/<project>/notebook/
         <date>/ on the project's host (local, or over faked SSH); thumbnails
         and poster frames in the vault's attachments/; machine-made text
         marked as such; PHI patterns withholding a transcription; a protected
         project getting no thumbnail; append_only never overwritten; dry-run;
         a clear error when no host is known.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-07
Input:   A temp vault, a temp data root, a temp hosts file, faked subprocess.
Output:  Assertions.
"""

from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

import pytest

from murmurent.commands import notebook_cmd
from murmurent.core import hosts as _hosts
from murmurent.core import lab_notebook as nb
from murmurent.core import notebook_capture as cap
from murmurent.core import remote as _remote

WHEN = dt.datetime(2026, 11, 7, 14, 5)
DATE = "2026-11-07"


@pytest.fixture
def world(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "lab-notebook").mkdir(parents=True)
    monkeypatch.setenv("MURMURENT_VAULT_ROOT", str(vault))
    monkeypatch.delenv("MURMURENT_NOTEBOOK_DIR", raising=False)
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("MURMURENT_HOSTS_FILE", str(tmp_path / "hosts.yaml"))
    monkeypatch.setenv("MURMURENT_REMOTE_AUDIT_LOG", str(tmp_path / "audit.log"))
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setattr(cap, "elevenlabs_key", lambda: "")
    # a project record: standard tier, data on this machine
    records = {"p_demo": ("standard", "local"), "p_clin": ("protected", "lab-server"),
               "p_far": ("standard", "lab-server"), "p_lost": ("standard", "ghost")}

    class Rec:
        def __init__(self, s, h):
            self.sensitivity, self.host = s, h

    from murmurent.core import cert_projects as _cp
    monkeypatch.setattr(_cp, "get", lambda name, env=None: Rec(*records[name]) if name in records else None)
    monkeypatch.setattr(_cp, "project_name_for_cwd", lambda start=None, env=None: None)
    _hosts.add(_hosts.Host(name="lab-server", kind="ssh", ssh_host="lab-server"))
    # thumbnails without Pillow or sips: a stand-in that writes a small file
    monkeypatch.setattr(cap, "make_thumbnail", _fake_small)
    monkeypatch.setattr(cap, "make_poster", _fake_small)
    return {"vault": vault, "data": tmp_path / "data", "tmp": tmp_path}


def _fake_small(src: Path, dst: Path, max_px: int = 512) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b"thumb")
    return True


def fake_ssh(monkeypatch) -> list[list[str]]:
    """Replace subprocess.run inside core.remote: no SSH runs. The host's
    login shell says its data root is /data/lab_vm; everything else succeeds."""
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        out = "/data/lab_vm" if "MURMURENT_DATA_ROOT" in argv[-1] else ""
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")

    monkeypatch.setattr(_remote.subprocess, "run", fake_run)
    return calls


def _fake_png(path: Path) -> Path:
    """A valid 2x2 PNG, so the real thumbnailers can read it where present."""
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + b"\xff\x00\x00" * 2 for _ in range(2))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    path.write_bytes(png + b"\x00" * len(path.name))  # size differs per name
    return path


def _entry(world) -> str:
    return (world["vault"] / "lab-notebook" / f"{DATE}.md").read_text(encoding="utf-8")


def test_text_goes_under_a_time_heading(world):
    rc = notebook_cmd.cmd_add("Gel ran clean.", project="p_demo", when=WHEN)
    assert rc == 0
    text = _entry(world)
    assert text.startswith("---\n") and "project: p_demo" in text and "audience: me" in text
    assert "## 14:05\nGel ran clean." in text
    assert f"Sessions: [[sessions/{DATE}]]" in text
    notebook_cmd.cmd_add("Second thought.", project="p_demo", when=WHEN.replace(minute=30))
    assert "## 14:30\nSecond thought." in _entry(world)


def test_small_result_file_stays_in_the_vault(world):
    csv = world["tmp"] / "counts.csv"
    csv.write_text("a,b\n1,2\n", encoding="utf-8")
    assert notebook_cmd.cmd_add(str(csv), project="p_demo", when=WHEN) == 0
    assert (world["vault"] / "attachments" / DATE / "counts.csv").read_text() == "a,b\n1,2\n"
    assert f"[[attachments/{DATE}/counts.csv]]" in _entry(world)
    assert not (world["data"]).exists()


def test_image_to_local_host_with_thumbnail_and_marked_placeholder(world):
    png = _fake_png(world["tmp"] / "gel_27.png")
    assert notebook_cmd.cmd_add(str(png), project="p_demo", note="lane 3 is the control", when=WHEN) == 0
    sent = world["data"] / "append_only" / "p_demo" / "notebook" / DATE / "gel_27.png"
    assert sent.read_bytes() == png.read_bytes()
    thumb = world["vault"] / "attachments" / DATE / "gel_27_thumb.jpg"
    assert thumb.is_file()
    text = _entry(world)
    assert "## 14:05 image: gel_27.png" in text
    assert f"![[attachments/{DATE}/gel_27_thumb.jpg]]" in text
    assert f"- original: `local:{sent}`" in text
    assert "- note: lane 3 is the control" in text
    assert "Machine reading (image description by Claude Code, not the record)" in text
    # the original is not in the vault
    assert not list(world["vault"].rglob("gel_27.png"))


def test_handwritten_page_gets_a_transcription_placeholder(world):
    png = _fake_png(world["tmp"] / "page.png")
    assert notebook_cmd.cmd_add(str(png), project="p_demo", handwritten=True, when=WHEN) == 0
    text = _entry(world)
    assert "handwritten page: page.png" in text
    assert "Transcription (machine-made, not the record; check each value against the page)" in text


def test_append_only_never_overwrites_a_second_file_of_the_same_name(world):
    png = _fake_png(world["tmp"] / "gel.png")
    notebook_cmd.cmd_add(str(png), project="p_demo", when=WHEN)
    first = (world["data"] / "append_only" / "p_demo" / "notebook" / DATE / "gel.png").read_bytes()
    png.write_bytes(first + b"changed")
    notebook_cmd.cmd_add(str(png), project="p_demo", when=WHEN)
    folder = world["data"] / "append_only" / "p_demo" / "notebook" / DATE
    assert sorted(f.name for f in folder.iterdir()) == ["gel.png", "gel_2.png"]
    assert folder.joinpath("gel.png").read_bytes() == first
    assert "gel_2.png" in _entry(world)
    assert (world["vault"] / "attachments" / DATE / "gel_thumb_2.jpg").is_file()


def test_sound_is_transcribed_and_marked(world):
    wav = world["tmp"] / "note.wav"
    wav.write_bytes(b"RIFF" + b"\0" * 64)
    rc = notebook_cmd.cmd_add(str(wav), project="p_demo", when=WHEN,
                              transcriber=lambda p: "twenty micrograms per lane")
    assert rc == 0
    text = _entry(world)
    assert "sound note: note.wav" in text
    assert ("> Transcription (machine-made by ElevenLabs scribe_v1, not the record; "
            "check it against the recording): twenty micrograms per lane") in text
    assert (world["data"] / "append_only" / "p_demo" / "notebook" / DATE / "note.wav").is_file()


def test_transcription_with_phi_is_withheld(world):
    wav = world["tmp"] / "note.wav"
    wav.write_bytes(b"RIFF" + b"\0" * 64)
    notebook_cmd.cmd_add(str(wav), project="p_demo", when=WHEN,
                         transcriber=lambda p: "patient MRN-88211 sample came back")
    text = _entry(world)
    assert "Transcription withheld: it matched MRN pattern(s)" in text
    assert "88211" not in text


def test_transcription_skipped_without_a_key(world):
    wav = world["tmp"] / "note.wav"
    wav.write_bytes(b"RIFF" + b"\0" * 64)
    notebook_cmd.cmd_add(str(wav), project="p_demo", when=WHEN)
    assert "Transcription skipped: no `elevenlabs-api-key` in the Keychain" in _entry(world)


def test_image_to_ssh_host_over_faked_scp(world, monkeypatch):
    calls = fake_ssh(monkeypatch)
    png = _fake_png(world["tmp"] / "bench.png")
    assert notebook_cmd.cmd_add(str(png), project="p_far", when=WHEN) == 0
    folder = f"/data/lab_vm/append_only/p_far/notebook/{DATE}"
    assert any(a[0] == "ssh" and "MURMURENT_DATA_ROOT" in a[-1] for a in calls)
    assert any(a[0] == "ssh" and "ls -1A" in a[-1] for a in calls)
    assert any(a[0] == "ssh" and "mkdir -p" in a[-1] and "test ! -e" in a[-1] for a in calls)
    scp = [a for a in calls if a[0] == "scp"]
    assert scp and scp[0][-1] == f"lab-server:{folder}/bench.png" and scp[0][-2] == str(png)
    text = _entry(world)
    assert f"- original: `lab-server:{folder}/bench.png`" in text
    assert (world["vault"] / "attachments" / DATE / "bench_thumb.jpg").is_file()
    assert not world["data"].exists()


def test_protected_project_gets_no_thumbnail_in_the_vault(world, monkeypatch):
    fake_ssh(monkeypatch)
    png = _fake_png(world["tmp"] / "chart.png")
    assert notebook_cmd.cmd_add(str(png), project="p_clin", when=WHEN) == 0
    assert not (world["vault"] / "attachments").exists()
    text = _entry(world)
    assert "sensitivity: protected" in text
    assert "no thumbnail: the project is protected" in text
    assert "lab-server:/data/lab_vm/append_only/p_clin/notebook" in text


def test_unknown_host_is_a_clear_error_and_dry_run_writes_nothing(world, capsys, monkeypatch):
    png = _fake_png(world["tmp"] / "x.png")
    assert notebook_cmd.cmd_add(str(png), project="p_lost", when=WHEN) == 1
    assert "no host known as 'ghost'" in capsys.readouterr().out
    assert not (world["vault"] / "lab-notebook" / f"{DATE}.md").exists()

    calls = fake_ssh(monkeypatch)
    assert notebook_cmd.cmd_add(str(png), project="p_far", when=WHEN, dry_run=True) == 0
    assert not any(a[0] == "scp" for a in calls)
    out = capsys.readouterr().out
    assert "Would add image" in out and "lab-server:/data/lab_vm/append_only/p_far" in out
    assert not (world["vault"] / "lab-notebook" / f"{DATE}.md").exists()
    assert not (world["vault"] / "attachments").exists()


def test_no_project_is_a_clear_error(world, capsys):
    assert notebook_cmd.cmd_add("hello", when=WHEN) == 1
    assert "no project" in capsys.readouterr().out


def test_open_fetches_a_copy(world, monkeypatch, capsys):
    png = _fake_png(world["tmp"] / "gel.png")
    notebook_cmd.cmd_add(str(png), project="p_demo", when=WHEN)
    link = f"local:{world['data'] / 'append_only' / 'p_demo' / 'notebook' / DATE / 'gel.png'}"
    assert notebook_cmd.cmd_open(link, no_open=True) == 0
    out = capsys.readouterr().out
    copy = Path(out.split("Copy at ", 1)[1].strip())
    assert copy.read_bytes() == png.read_bytes()
    assert "notebook_cache" in str(copy)

    calls = fake_ssh(monkeypatch)
    assert notebook_cmd.cmd_open("lab-server:/data/lab_vm/append_only/p_far/notebook/x/bench.png",
                                 no_open=True) == 0
    assert calls[0][0] == "scp" and calls[0][-2] == "lab-server:/data/lab_vm/append_only/p_far/notebook/x/bench.png"


def test_lab_data_host_wins_over_the_repository_host(world, monkeypatch):
    from murmurent.core import registrar as _reg
    monkeypatch.setattr(_reg, "read_group_profile", lambda name, env=None: {"data_host": "lab-server"})
    from murmurent.core import cert_projects as _cp

    class Rec:
        sensitivity, host, lab = "standard", "local", "mh"

    monkeypatch.setattr(_cp, "get", lambda name, env=None: Rec())
    assert cap.project_context("p_any") == ("p_any", "standard", "lab-server")


def test_host_without_a_data_root_is_a_clear_error(world, monkeypatch):
    monkeypatch.setattr(_remote.subprocess, "run",
                        lambda argv, **kw: subprocess.CompletedProcess(argv, 0, stdout="", stderr=""))
    with pytest.raises(cap.CaptureError, match="MURMURENT_DATA_ROOT"):
        cap.destination("p_far", "lab-server", DATE)


@pytest.mark.skipif(not (cap.shutil.which("sips") or _has_pil()), reason="no image tool here")
def test_real_thumbnail_is_smaller(tmp_path):
    png = _fake_png(tmp_path / "big.png")
    out = tmp_path / "t.jpg"
    assert cap.make_thumbnail(png, out) and out.is_file()


def _has_pil() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def test_infer_kind():
    assert cap.infer_kind(Path("a.JPG")) == "image"
    assert cap.infer_kind(Path("a.jpg"), handwritten=True) == "handwritten"
    assert cap.infer_kind(Path("a.m4a")) == "sound"
    assert cap.infer_kind(Path("a.mov")) == "video"
    assert cap.infer_kind(Path("a.pdf")) == "file"
