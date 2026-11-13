# The machines you can reach

`murmurent machines` lists every machine a person can reach and, on request,
how busy each one is and how full its storage is, in one table. A lab
declares its machines once; each member records their own login once; after
that one command answers for all of them, and the millwright runs the same
command when it is asked about load or space.

## What a machine is

A **machine** is anything a person can log in to and run work on: this
computer, the lab's own server, a cluster. Each is one of three kinds, called
**profiles**, and every profile answers the same three read-only questions:

| Question | Command | What it reports |
|---|---|---|
| Is it up? | `murmurent machines` | reachable or not, and when that was last checked |
| How busy is it? | `murmurent machines load` | cores busy of total, GPUs busy of total, jobs or sessions, who |
| How full is it? | `murmurent machines usage` | each storage tier: space and files used of quota, and which tier is nearest its limit |

The three profiles:

- **laptop**: this computer. It needs no login and is always in your set. Load
  comes from the operating system; storage is your home folder and, when it is
  set, the data root.
- **ssh_server**: a Linux server reached by plain ssh, with no scheduler. Load
  comes from `uptime` and `nproc`, GPUs from `nvidia-smi` when it is installed,
  people from `who` and `ps`, and storage from `df` over the machine's tiers,
  which default to the eight folders of the lab folder protocol under its data
  root (immutable, append_only, modifiable, mothballed, release, cottage,
  tools, db).
- **alliance**: a cluster of the Digital Research Alliance of Canada. Its
  facts stay in `policy/clusters.yaml`, and the cluster code answers:
  `murmurent machines load` is `murmurent cluster scan` reduced to one row,
  and `murmurent machines usage` is `murmurent cluster usage`.

Every probe is read-only. It goes through `ssh -o BatchMode=yes` with a
timeout, so a machine that does not answer never asks for a password and never
hangs the table: its row says `unreachable: <why>` and the command still exits
with 0.

## The two layers

A machine is described in two layers, the same way a cluster is.

**The lab's declaration** is `policy/machines.yaml` in the lab records
repository (`murmurent_lab_mgmt_<lab>`). It is shared by the whole lab and
written by the PI. Each entry picks a profile and says what differs from it:

```yaml
machines:
  biodatsci:
    profile: ssh_server
    description: the lab's own server, holding the data root /data/lab_vm
    ssh_host: biodatsci.schulich.uwo.ca     # the default address, for the setup hint
    data_root: /data/lab_vm                 # the eight lab folders become the tiers
    tiers:                                  # add a tier, or move one
      home:
        path: /home
        purpose: home folders; small
  dusky:
    profile: alliance
    cluster: dusky                          # the entry in policy/clusters.yaml
```

`templates/machines.yaml` is this example in full, with every line explained.
A value the lab leaves out comes from the profile; a value it gets wrong is
reported as a problem and the profile's value is kept, so a typo never empties
the table.

**The person's login** is one row per machine in their own
`~/.murmurent/hosts.yaml`, written by:

```bash
murmurent machine add biodatsci --ssh-host mhallet@biodatsci.schulich.uwo.ca
```

The login is personal, so it never goes in the shared file. `murmurent cluster
add` writes the same row for a cluster; the two commands are one.

Your **set** is this computer plus every declared machine for which you have
recorded a login. A declared machine with no login is listed as
`not set up: run murmurent machine add ...` and is never probed.

## The three commands

```bash
murmurent machines
```

One row per declared machine: its kind, your login or the setup hint, whether
it answered just now, and the time. `--no-check` shows what the last check
found without reaching out.

```bash
murmurent machines load
```

Every set-up machine is asked at the same time. For a server: cores busy
(the one-minute load against the core count), GPUs busy (a card with work on
it or memory taken), how many people are logged in, and who is using how many
cores. For a cluster: the lab's partition as a whole, cores and GPUs allocated,
jobs running and waiting, and who holds what. A server counts people, not terminals: one person with a dozen tmux windows is one person.

```bash
murmurent machines usage
```

Every storage tier on every set-up machine, with space used of its total, the
number of files where the machine reports one (a cluster does; a plain server
does not), and `nearest its limit` on the tier closest to full. Tiers that
share one filesystem say so, since `df` reports the filesystem, not the folder.

In a Claude Code session, `/murmurent-machines` (or `/murmurent-machines
usage`) runs the command and shows the table as it is, without interpretation;
ask the millwright when you want it read for you.

All three take `--json`, which prints the same rows as JSON for the millwright
and the dashboard. The exit code is 0 even when a machine is unreachable; the
row says so.

## How a new institution adds its own

1. Copy `templates/machines.yaml` to `policy/machines.yaml` in the lab records
   repository and replace the Western example with your own machines. A Linux
   server is `ssh_server` with its data root; a cluster is `alliance` with the
   name of its entry in `policy/clusters.yaml` (see
   [`cluster.md`](cluster.md)). Nothing in murmurent names a machine; the
   example is the only place biodatsci and dusky appear.
2. Each member runs `murmurent machine add <name> --ssh-host <login>@<address>`
   once per machine, and `murmurent machines` to see that it answers.
3. A machine of another family (a cloud account, a cluster with another
   scheduler) needs a new profile in `src/murmurent/core/machine_policy.py`:
   one class with `status()`, `load()` and `usage()`. The commands, the JSON
   and the millwright need no change.

For trying a file before the PI adopts it, `$MURMURENT_MACHINES_FILE` names a
file read after the lab's.
