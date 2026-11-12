"""
Purpose: Describe the compute clusters a lab may send work to: how to reach
         one, which scheduler account and partition give the lab its access,
         and what each storage tier on it is for.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-12
Input:   Built-in profiles (today only ``alliance``, the Digital Research
         Alliance of Canada layout); then ``<lab-mgmt>/policy/clusters.yaml`` in
         the lab's records repository; then the file named by
         ``$MURMURENT_CLUSTERS_FILE`` (tests, or trying a cluster before the PI
         adopts it).
Output:  :class:`Cluster` records, each with its :class:`StorageTier` list, and
         the problems found in the files.

A cluster is described in two layers so that another institution changes as
little as possible:

1. A **profile** holds what is true of every cluster of that family. The
   Alliance profile knows the five standard tiers (home, scratch, project,
   nearline, node-local), that ``diskusage_report`` prints the quotas, and the
   login-node rule.
2. The lab's **clusters.yaml** names its own cluster, the SSH alias, the
   scheduler account that gives the lab its access, the partitions, and any tier
   whose path or facts differ from the profile. Every field is optional; what is
   left out comes from the profile.

Each member's own login on a cluster is not policy. It lives in that person's
``~/.murmurent/hosts.yaml`` (``murmurent cluster add``), because the lab's file
is shared and a login name is personal.

A bad value never stops a submission: it is listed in ``problems`` and the
profile's value is kept.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

CLUSTERS_ENV = "MURMURENT_CLUSTERS_FILE"
CLUSTERS_RELATIVE_PATH = Path("policy") / "clusters.yaml"


@dataclass(frozen=True)
class StorageTier:
    """One kind of storage on a cluster, and what a person should know about it."""

    name: str
    path: str
    purpose: str
    backed_up: bool = False
    purged: bool = False
    quota: str = ""
    notes: str = ""

    def describe(self) -> str:
        """One plain phrase for a usage report."""
        facts = ["backed up" if self.backed_up else "not backed up"]
        if self.purged:
            facts.append("old files are deleted automatically")
        if self.quota:
            facts.append(f"quota {self.quota}")
        return f"{self.purpose} ({'; '.join(facts)})"


@dataclass(frozen=True)
class Cluster:
    """Everything murmurent needs to send work to one cluster."""

    name: str
    profile: str = "alliance"
    description: str = ""
    scheduler: str = "slurm"
    ssh_host: str = ""
    account: str = ""
    group: str = ""
    partition_cpu: str = ""
    partition_gpu: str = ""
    gpu_type: str = ""
    default_time: str = "01:00:00"
    max_time: str = ""
    poll_minutes: int = 2
    work_root: str = "{scratch}/murmurent"
    usage_command: str = "diskusage_report"
    login_node_rule: str = ""
    modules: tuple[str, ...] = ()
    setup: tuple[str, ...] = ()
    tiers: tuple[StorageTier, ...] = ()
    notes: str = ""

    def tier(self, name: str) -> StorageTier | None:
        for t in self.tiers:
            if t.name == name:
                return t
        return None

    def partition_for(self, gpus: int) -> str:
        """The partition a job goes to, by whether it asks for a GPU."""
        if gpus > 0 and self.partition_gpu:
            return self.partition_gpu
        return self.partition_cpu or self.partition_gpu


@dataclass
class ClusterPolicy:
    """The clusters a lab knows, with where they were read from."""

    clusters: dict[str, Cluster] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def get(self, name: str) -> Cluster | None:
        return self.clusters.get(name)

    def names(self) -> list[str]:
        return sorted(self.clusters)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

ALLIANCE_LOGIN_RULE = (
    "The login node is shared by everyone. Run nothing there that takes more "
    "than about ten CPU-minutes or four gigabytes of memory; submit it as a job."
)

ALLIANCE_TIERS: tuple[StorageTier, ...] = (
    StorageTier(
        name="home",
        path="/home/{user}",
        purpose="code, scripts and small files",
        backed_up=True,
        purged=False,
        quota="about 50 GB and 500 thousand files",
        notes="Small and slow. Not for data.",
    ),
    StorageTier(
        name="scratch",
        path="/scratch/{user}",
        purpose="working data for running jobs",
        backed_up=False,
        purged=True,
        quota="large, shared by everyone on the cluster",
        notes="Files untouched for about two months are deleted. Copy results out.",
    ),
    StorageTier(
        name="project",
        path="/project/{account}",
        purpose="the group's shared large-scale storage",
        backed_up=True,
        purged=False,
        quota="the group's allocation, shared by all its members",
        notes="Counted against the group, not the person.",
    ),
    StorageTier(
        name="nearline",
        path="/nearline/{account}",
        purpose="long-term archive on tape",
        backed_up=True,
        purged=False,
        quota="the group's allocation",
        notes="Slow to read back. Write only what is finished, with the PI's agreement.",
    ),
    StorageTier(
        name="local",
        path="/local",
        purpose="fast disk on the compute node itself, for the duration of a job",
        backed_up=False,
        purged=True,
        quota="whatever the node has",
        notes="Gone when the job ends. Use $SLURM_TMPDIR inside a job.",
    ),
)

PROFILES: dict[str, dict[str, Any]] = {
    "alliance": {
        "description": "A cluster of the Digital Research Alliance of Canada",
        "scheduler": "slurm",
        "usage_command": "diskusage_report",
        "login_node_rule": ALLIANCE_LOGIN_RULE,
        "work_root": "{scratch}/murmurent",
        "poll_minutes": 2,
        "tiers": ALLIANCE_TIERS,
    },
}


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return None, f"{path}: could not read it ({exc.__class__.__name__})"
    if not isinstance(data, dict):
        return None, f"{path}: expected a mapping at the top"
    return data, None


def _tier_from(name: str, raw: Any, base: StorageTier | None, where: str,
               problems: list[str]) -> StorageTier | None:
    if not isinstance(raw, dict):
        problems.append(f"{where}: a tier must be a mapping")
        return base
    tier = base or StorageTier(name=name, path="", purpose="")
    changes: dict[str, Any] = {}
    for key in ("path", "purpose", "quota", "notes"):
        if key in raw and raw[key] is not None:
            changes[key] = str(raw[key])
    for key in ("backed_up", "purged"):
        if key in raw:
            if isinstance(raw[key], bool):
                changes[key] = raw[key]
            else:
                problems.append(f"{where}.{key}: expected true or false")
    tier = replace(tier, name=name, **changes)
    if not tier.path:
        problems.append(f"{where}: a tier needs a path")
        return base
    return tier


_TEXT_KEYS = ("description", "scheduler", "ssh_host", "account", "group", "partition_cpu",
              "partition_gpu", "gpu_type", "default_time", "max_time", "work_root",
              "usage_command", "login_node_rule", "notes")


def _cluster_from(name: str, raw: dict[str, Any], where: str, problems: list[str]) -> Cluster:
    profile_name = str(raw.get("profile") or "alliance")
    profile = PROFILES.get(profile_name)
    if profile is None:
        problems.append(f"{where}: unknown profile {profile_name!r}; using 'alliance'")
        profile_name, profile = "alliance", PROFILES["alliance"]
    cluster = Cluster(name=name, profile=profile_name, **profile)

    changes: dict[str, Any] = {}
    for key in _TEXT_KEYS:
        if key in raw and raw[key] is not None:
            changes[key] = str(raw[key])
    if "poll_minutes" in raw:
        try:
            minutes = int(raw["poll_minutes"])
            if minutes < 1:
                raise ValueError
            changes["poll_minutes"] = minutes
        except (TypeError, ValueError):
            problems.append(f"{where}.poll_minutes: expected a whole number of minutes, 1 or more")
    for key in ("modules", "setup"):
        if key in raw:
            value = raw[key]
            if isinstance(value, str):
                value = [value]
            if isinstance(value, list) and all(isinstance(v, str) for v in value):
                changes[key] = tuple(value)
            else:
                problems.append(f"{where}.{key}: expected a list of strings")
    cluster = replace(cluster, **changes)

    tiers_raw = raw.get("tiers")
    if tiers_raw is not None:
        if not isinstance(tiers_raw, dict):
            problems.append(f"{where}.tiers: expected a mapping of tier name to settings")
        else:
            tiers = {t.name: t for t in cluster.tiers}
            for tier_name, tier_raw in tiers_raw.items():
                tier = _tier_from(str(tier_name), tier_raw, tiers.get(str(tier_name)),
                                  f"{where}.tiers.{tier_name}", problems)
                if tier is not None:
                    tiers[str(tier_name)] = tier
            cluster = replace(cluster, tiers=tuple(tiers.values()))
    return cluster


def _apply_file(policy: ClusterPolicy, path: Path) -> None:
    data, problem = _read_yaml(path)
    if problem:
        policy.problems.append(problem)
        return
    policy.sources.append(str(path))
    clusters = data.get("clusters", data)
    if not isinstance(clusters, dict):
        policy.problems.append(f"{path}: 'clusters' must be a mapping of cluster name to settings")
        return
    for name, raw in clusters.items():
        if not isinstance(raw, dict):
            policy.problems.append(f"{path}: cluster {name!r} must be a mapping")
            continue
        policy.clusters[str(name)] = _cluster_from(str(name), raw, f"{path}: {name}", policy.problems)


def lab_clusters_path(env: dict[str, str] | None = None) -> Path | None:
    """``policy/clusters.yaml`` in the lab's records repository, if that is known."""
    try:
        from .repo import lab_mgmt_repo_root

        return lab_mgmt_repo_root(env) / CLUSTERS_RELATIVE_PATH
    except Exception:  # noqa: BLE001 - no lab records on this machine
        return None


def load_clusters(env: dict[str, str] | None = None) -> ClusterPolicy:
    """The clusters this lab knows: the lab file, then the override file."""
    env = os.environ if env is None else env
    policy = ClusterPolicy()
    lab_path = lab_clusters_path(env)
    if lab_path is not None and lab_path.is_file():
        _apply_file(policy, lab_path)
    override = env.get(CLUSTERS_ENV)
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            _apply_file(policy, path)
        else:
            policy.problems.append(f"${CLUSTERS_ENV} names {path}, which does not exist")
    return policy


def expand_path(template: str, *, user: str, account: str = "", group: str = "",
                tiers: dict[str, str] | None = None) -> str:
    """Fill a tier or work-root template in for one member.

    ``{scratch}``, ``{home}`` and the other tier names expand to that tier's
    expanded path, so ``work_root: "{scratch}/murmurent"`` works.
    """
    text = template.replace("{user}", user).replace("{account}", account).replace("{group}", group)
    for name, path in (tiers or {}).items():
        text = text.replace("{" + name + "}", path)
    return text


def expanded_tiers(cluster: Cluster, *, user: str) -> dict[str, str]:
    """Every tier's path for one member, by tier name."""
    account = cluster.account
    group = cluster.group or account
    return {
        t.name: expand_path(t.path, user=user, account=account, group=group)
        for t in cluster.tiers
    }


def describe_cluster(cluster: Cluster) -> list[str]:
    """The cluster's settings in plain lines, for ``murmurent cluster policy``."""
    lines = [f"{cluster.name}: {cluster.description or cluster.profile + ' profile'}"]
    lines.append(f"  reach it: ssh {cluster.ssh_host or '(no address set)'}")
    lines.append(f"  scheduler: {cluster.scheduler}; account {cluster.account or '(none)'}; "
                 f"partitions cpu={cluster.partition_cpu or '-'} gpu={cluster.partition_gpu or '-'}")
    if cluster.group:
        lines.append(f"  access: members of the group {cluster.group}")
    if cluster.max_time:
        lines.append(f"  longest job: {cluster.max_time}; default {cluster.default_time}")
    lines.append(f"  jobs are staged under: {cluster.work_root}")
    lines.append(f"  polled every {cluster.poll_minutes} min")
    lines.append("  storage:")
    for tier in cluster.tiers:
        lines.append(f"    {tier.name:<9} {tier.path:<24} {tier.describe()}")
    if cluster.login_node_rule:
        lines.append(f"  {cluster.login_node_rule}")
    if cluster.notes:
        lines.append(f"  note: {cluster.notes}")
    return lines
