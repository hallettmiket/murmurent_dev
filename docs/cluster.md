# Running work on a compute cluster

`murmurent cluster` sends a job to a compute cluster, watches it, and brings
the results back into the experiment's output folder. It was built for
the clusters of the Digital Research Alliance of Canada (the national research
computing service, formerly Compute Canada), which schedule work with **Slurm**:
a program that takes a request for cores, memory, GPUs and a time limit, and
runs the job on a compute node when the resources are free. Any Slurm cluster
reached over SSH works the same way.

Nothing is installed on the cluster. Your laptop or the lab server does the
submitting over SSH, so the cluster's rules about what may run on its login
node are never a concern: the only thing murmurent runs there is the handful of
scheduler commands you would type yourself, and `rsync`.

## The idea in one paragraph

A lab describes its cluster once, in `policy/clusters.yaml` of its records
repository: how to reach it, which scheduler **account** gives the lab its
access, which **partition** (group of nodes) its jobs go to, and what each
storage tier is for. Each member records their own login once. After that,
`murmurent cluster submit` from an experiment folder copies the folder to the
cluster's scratch space, writes a job script that charges the lab's account,
submits it, and starts a watcher. The watcher asks the scheduler every few
minutes and, when the job ends, copies the results back and tells the project's
Slack channel.

## Why the account matters

On a **contributed system**, nodes a lab bought and placed in a national
cluster, the lab's account (the Alliance names them `ctb-<lab>`) is what gives
its jobs priority on those nodes, a long time limit and no caps. A job charged
to the default account everyone has (`def-<lab>`) queues behind funded
projects. murmurent always charges the account in the policy, and refuses to
submit when the member is not in it, with the reason: the PI adds members to
the account on the Alliance's website (CCDB), which is what puts them in the
Unix group the partition admits.

## One-time setup

**The PI**, once per cluster, copies `templates/clusters.yaml` into the lab
records repository as `policy/clusters.yaml` and edits it. For an Alliance
cluster the essentials are six lines:

```yaml
clusters:
  mycluster:
    profile: alliance
    ssh_host: mycluster.example.ca
    account: ctb-mylab
    group: ctb-mylab
    partition_cpu: mylab
    partition_gpu: mylab
```

The `alliance` profile fills in the rest: the five storage tiers, the quota
command, the login-node rule. Another institution with a different layout
overrides any tier's path or facts in the same file; a cluster that is not the
Alliance's still uses the profile and changes what differs.

**Each member**, once:

```bash
murmurent cluster add mycluster --ssh-host <login>@mycluster.example.ca
murmurent cluster test
```

A lab's own page for its members (which cluster, which login, who to ask) sits
outside these docs, with the lab's other local material.

`test` logs in and checks that the member may charge the lab's account. If the
cluster takes passwords, put your SSH key on it first with `ssh-copy-id`.

## Submitting a job

From inside the experiment folder:

```bash
cd ~/repos/my_project/exp/3_fit
murmurent cluster submit --name fit --cores 16 --gpus 1 --memory 64G --time 6h \
    -- python run_all.py
```

What happens:

1. The folder is copied to `<scratch>/murmurent/<project>/fit-<id>/stage` on
   the cluster (`.git`, caches and virtual environments are left out).
2. A job script is written beside it with the lab's account and partition,
   the resources asked for, and the thread settings that stop numerical
   libraries from taking every core. The command runs inside `stage` with
   `$MURMURENT_OUT` pointing at `../out`. **Write results to `$MURMURENT_OUT`**;
   that is the folder that comes back.
3. `sbatch` submits it. A job card is written under `~/.murmurent/runs/`, the
   same store `murmurent jobs` reads, so cluster jobs appear beside local ones.
4. A watcher starts in tmux and polls the scheduler every few minutes.

`--time` is the one setting to think about: a job that runs out of time is
lost work, so take the longest earlier run and add a margin. The cluster's
default applies when you say nothing. Memory and cores default to the
scheduler's modest defaults. A job script of your own goes in with
`--script job.sh`, used as it is.

## Following it

| Command | What it does |
|---|---|
| `murmurent cluster status` | Every cluster job of the last fortnight. |
| `murmurent cluster status <id>` | Asks the scheduler where that job stands and prints its notes. |
| `murmurent cluster watch <id>` | Polls until the end (the watcher runs this in tmux). |
| `murmurent cluster cancel <id>` | Stops it. |
| `murmurent cluster fetch <id>` | Copies the results and log back again, on request. |

When the job ends the watcher copies `out` into the experiment's output folder
(or `--out`). That is its `append_only` folder, where **nothing already there
is overwritten**, unless the experiment chose the `modifiable` tier
(`output_tier: modifiable` in its `notebook.md`, or in the repository's
`.murmurent.yaml` for all of its experiments; `--output-tier` on `submit`
overrides either), where a re-run replaces files of the same name. The lab
folder protocol page explains the choice. The watcher then pulls the
scheduler's log beside the card, writes why the job ended in plain words (out
of time, out of memory, an error in the program, a node failure), and posts one
line to the project's channel through the same route `murmurent run` uses. The
Slack line carries the name, state and duration, never a path.

The watcher never asks the scheduler more often than once a minute, however
the policy is set, because the Alliance asks that `squeue` not be run at high
frequency.

## Files

```bash
murmurent cluster push data/cohort.csv '{scratch}/cohort/'
murmurent cluster pull '{project}/results/run7' ~/results/run7
```

`{home}`, `{scratch}`, `{project}` and `{nearline}` expand to your own paths
on the cluster. `pull` leaves existing local files alone; `--overwrite` is
refused under the governed data folders. `push` refuses the nearline tier,
which is the tape archive: a person writes there, with the PI's agreement.
Large data should move between the lab server and the cluster directly, not
through a laptop.

## Storage tiers

`murmurent cluster usage` reports each tier for you, with its purpose and the
facts that matter. On an Alliance cluster:

| Tier | What it is for | Backed up | Purged | Quota |
|---|---|---|---|---|
| home | code, scripts, small files | yes | no | about 50 GB, 500 thousand files |
| scratch | working data for running jobs | no | yes, by age | large, shared |
| project | the group's shared large-scale storage | yes | no | the group's allocation |
| nearline | long-term archive on tape | yes | no | the group's allocation |
| local | the compute node's own disk, for one job | no | at the job's end | the node's |

The file-count quota matters as much as the byte quota: a folder of a million
small files is refused on home long before 50 GB. Scratch is where jobs run
and where murmurent stages them; results that matter come back to the lab's
`append_only` (or `modifiable`) folder, so the purge is harmless.

## For the PI: the partition as a whole

```bash
murmurent cluster scan --days 30
```

Reports the lab's partition: each node's cores and GPUs in use, the queue by
person, core-hours and GPU-hours per member in the period, the members of the
lab's account and those who ran nothing, the fair-share standing, and the
group's project and nearline storage. It is a report; it changes nothing. The
Alliance's usage website shows only the national clusters, so a contributed
system's use is visible here and nowhere else.

## The millwright

The [millwright](https://github.com/hallettmiket/murmurent/blob/main/agents/millwright.md) runs these commands for a member:
it submits, watches, reacts to a failure in the way the reason calls for (a
longer time, more memory, or the log for the person to read), brings results
back, explains the tiers, and gives the PI the scan. It never deletes on a
cluster, never writes to nearline, and never reads a data file itself.

## Where things are

| What | Where |
|---|---|
| The lab's cluster descriptions | `<lab records>/policy/clusters.yaml` |
| A member's logins | `~/.murmurent/hosts.yaml` |
| Job cards and pulled logs | `~/.murmurent/runs/` |
| Every SSH and rsync call | `~/.murmurent/remote_audit.log` |
| Staged jobs on the cluster | `<scratch>/murmurent/<project>/<name>-<id>/` |
| The code | `core/cluster_policy.py`, `core/slurm.py`, `core/cluster.py`, `commands/cluster_cmd.py` |
