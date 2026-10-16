"""The lab policy file for the run launcher and the millwright (#151, step 1).

What matters: the built-in defaults are generic; the lab's file in its
management repository overrides them; the environment variable overrides both;
and a bad value is reported and ignored rather than removing a limit.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

from murmurent.core import millwright_policy as mp

REPO = Path(__file__).resolve().parent.parent


def _write(path: Path, data: dict | str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else yaml.safe_dump(data)
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_are_generic(tmp_path):
    policy = mp.load_policy({"MURMURENT_LAB_MGMT_REPO": str(tmp_path / "none")})
    assert policy.priority == 19
    assert policy.max_cores_per_person == 16
    assert policy.hold_new_work_at_load_fraction == 0.8
    assert policy.min_free_memory_fraction == 0.20
    assert policy.memory_per_person_fraction == 0.25
    assert policy.project_quiet_months == 12
    assert policy.project_dormant_months == 24
    assert policy.sources == ()
    assert policy.problems == ()


def test_lab_file_in_the_management_repository_overrides_defaults(tmp_path):
    lab = tmp_path / "lab_mgmt"
    _write(
        lab / "policy" / "millwright.yaml",
        {
            "max_cores_per_person": 100,
            "gpus_per_person_working_hours": 4,
            "gpus_per_person_outside_hours": "all",
        },
    )
    policy = mp.load_policy({"MURMURENT_LAB_MGMT_REPO": str(lab)})
    assert policy.max_cores_per_person == 100
    assert policy.gpus_per_person_working_hours == 4
    assert policy.gpus_per_person_outside_hours == mp.ALL_IDLE_GPUS
    assert policy.sources == (str(lab / "policy" / "millwright.yaml"),)


def test_environment_file_overrides_the_lab_file(tmp_path):
    lab = tmp_path / "lab_mgmt"
    _write(lab / "policy" / "millwright.yaml", {"max_cores_per_person": 100})
    override = _write(tmp_path / "try.yaml", {"max_cores_per_person": 8})
    policy = mp.load_policy({"MURMURENT_LAB_MGMT_REPO": str(lab), mp.POLICY_ENV: str(override)})
    assert policy.max_cores_per_person == 8
    assert len(policy.sources) == 2


def test_bad_values_are_reported_and_ignored(tmp_path):
    override = _write(
        tmp_path / "bad.yaml",
        {
            "priority": 40,
            "hold_new_work_at_load_fraction": 80,
            "max_cores_per_person": "lots",
            "colour": "blue",
            "working_hours": {"start": "25:00"},
        },
    )
    policy = mp.load_policy(
        {mp.POLICY_ENV: str(override), "MURMURENT_LAB_MGMT_REPO": str(tmp_path / "none")}
    )
    assert policy.priority == 19
    assert policy.hold_new_work_at_load_fraction == 0.8
    assert policy.max_cores_per_person == 16
    assert policy.working_hours.start == "08:00"
    joined = " ".join(policy.problems)
    for key in (
        "priority",
        "hold_new_work_at_load_fraction",
        "max_cores_per_person",
        "colour",
        "working_hours",
    ):
        assert key in joined


def test_broken_yaml_and_missing_override_do_not_stop_anything(tmp_path):
    broken = _write(tmp_path / "broken.yaml", "priority: [unclosed")
    policy = mp.load_policy(
        {mp.POLICY_ENV: str(broken), "MURMURENT_LAB_MGMT_REPO": str(tmp_path / "none")}
    )
    assert policy.priority == 19 and "not valid YAML" in policy.problems[0]
    missing = mp.load_policy(
        {
            mp.POLICY_ENV: str(tmp_path / "nope.yaml"),
            "MURMURENT_LAB_MGMT_REPO": str(tmp_path / "none"),
        }
    )
    assert "does not exist" in missing.problems[0]


def test_dormant_must_not_be_shorter_than_quiet(tmp_path):
    override = _write(tmp_path / "p.yaml", {"project_quiet_months": 30})
    policy = mp.load_policy(
        {mp.POLICY_ENV: str(override), "MURMURENT_LAB_MGMT_REPO": str(tmp_path / "none")}
    )
    assert (policy.project_quiet_months, policy.project_dormant_months) == (12, 24)
    assert any("project_dormant_months" in p for p in policy.problems)


def test_working_hours_and_gpu_allowance():
    policy = mp.Policy(
        gpus_per_person_working_hours=4, gpus_per_person_outside_hours=mp.ALL_IDLE_GPUS
    )
    friday_morning = dt.datetime(2026, 10, 16, 9, 0)
    friday_night = dt.datetime(2026, 10, 16, 22, 0)
    saturday = dt.datetime(2026, 10, 17, 11, 0)
    assert policy.working_hours.contains(friday_morning)
    assert not policy.working_hours.contains(friday_night)
    assert not policy.working_hours.contains(saturday)
    assert policy.gpu_allowance(friday_morning, idle_gpu_count=8) == 4
    assert policy.gpu_allowance(friday_night, idle_gpu_count=8) == 8
    # Never fewer than the daytime allowance, even when few GPUs are idle.
    assert policy.gpu_allowance(saturday, idle_gpu_count=1) == 4


def test_the_shipped_example_is_valid_and_carries_the_lab_numbers():
    example = REPO / "templates" / "millwright_policy.yaml"
    policy = mp.load_policy(
        {mp.POLICY_ENV: str(example), "MURMURENT_LAB_MGMT_REPO": "/nonexistent"}
    )
    assert policy.problems == ()
    assert policy.max_cores_per_person == 100
    assert policy.hold_new_work_at_load_fraction == 0.8
    assert policy.min_free_memory_fraction == 0.20
    assert policy.memory_per_person_fraction == 0.25
    assert policy.gpus_per_person_working_hours == 4
    assert policy.gpus_per_person_outside_hours == mp.ALL_IDLE_GPUS
    assert (policy.home_folder_heads_up_gb, policy.home_folder_firm_gb) == (100, 150)
    assert (policy.project_quiet_months, policy.project_dormant_months) == (12, 24)
    assert policy.working_hours == mp.WorkingHours(
        ("mon", "tue", "wed", "thu", "fri"), "08:00", "18:00"
    )


def test_describe_policy_names_its_sources_and_problems(tmp_path):
    override = _write(tmp_path / "p.yaml", {"priority": 99})
    lines = mp.describe_policy(
        mp.load_policy({mp.POLICY_ENV: str(override), "MURMURENT_LAB_MGMT_REPO": "/nonexistent"})
    )
    assert lines[0].startswith("Rules from: built-in defaults, ")
    assert any(line.strip().startswith("Problem:") for line in lines)
    assert not any("\u2014" in line for line in lines)
