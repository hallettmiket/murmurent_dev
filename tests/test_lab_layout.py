"""The lab folder protocol and its check (#206). Temporary folders only."""

from __future__ import annotations

from pathlib import Path

from murmurent.core import lab_layout as L


def _lab(tmp_path: Path) -> Path:
    root = tmp_path / "lab_xx"
    for d in ("immutable/brca", "append_only/brca", "append_only/stray", "modifiable",
              "mothballed/old_study", "release/brca", "cottage/bob", "cottage/nobody",
              "tools/bwa", "db/hg38", "campervans", "mystery", "raw/brca"):
        (root / d).mkdir(parents=True)
    (root / "notes.txt").write_text("x")
    (root / "append_only" / "loose.csv").write_text("x")
    (root / "tools" / "installer.sh").write_text("x")
    return root


def test_check_reports_each_kind(tmp_path):
    root = _lab(tmp_path)
    found = L.check(root, projects={"brca", "old_study"}, logins={"bob"})
    by = {(f.kind, Path(f.path).name) for f in found}
    assert ("unexpected", "mystery") in by
    assert ("phasing-out", "campervans") in by
    assert ("loose-file", "notes.txt") in by
    assert ("loose-file", "loose.csv") in by
    assert ("loose-file", "installer.sh") not in by          # normal in shared tools/
    assert ("not-a-project", "stray") in by
    assert ("not-a-person", "nobody") in by
    assert not any(n in ("bob", "brca", "hg38", "bwa", "old_study") for _, n in by)
    assert ("both-names", "raw") in by                        # raw/ beside immutable/


def test_describe_is_plain_and_grouped(tmp_path):
    found = L.check(_lab(tmp_path), projects={"brca"}, logins={"bob"})
    text = "\n".join(L.describe(found))
    assert "Being phased out" in text and "Not one of the lab's folders" in text
    assert L.describe([]) == ["The lab folder follows the lab's folder protocol."]


def test_a_lab_can_declare_its_own_layout(tmp_path, monkeypatch):
    policy = tmp_path / "lab-mgmt" / "policy"
    policy.mkdir(parents=True)
    (policy / "lab_folders.yaml").write_text(
        "folders:\n  data: per-project\n  scratch: shared\nphasing_out: [junk]\n")
    from murmurent.core import millwright_policy
    monkeypatch.setattr(millwright_policy, "lab_policy_path",
                        lambda env=None: policy / "millwright.yaml")
    known, phasing = L.folders()
    assert set(known) == {"data", "scratch"} and phasing == {"junk"}
    root = tmp_path / "lab"
    for d in ("data/p1", "scratch/x", "junk", "immutable"):
        (root / d).mkdir(parents=True)
    kinds = {(f.kind, Path(f.path).name) for f in L.check(root, projects={"p1"}, logins=set())}
    assert kinds == {("phasing-out", "junk"), ("unexpected", "immutable")}


def test_present_folders_for_the_dashboard(tmp_path):
    root = _lab(tmp_path)
    rows = {r["name"]: r for r in L.present_folders(root)}
    assert rows["cottage"]["present"] and rows["cottage"]["kind"] == L.PER_PERSON
    assert not rows["refined"]["present"] and rows["refined"]["legacy_of"] == "append_only"
