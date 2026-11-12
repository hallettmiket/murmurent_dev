# The prospect command: the Prospector's deterministic half

The [prospector](https://github.com/hallettmiket/murmurent/blob/main/agents/prospector.md)
reads funders' pages and judges who may apply; that needs a model. Around
it sits `murmurent prospect`, which needs none: it keeps the profile a
search starts from, reads the [funder registry](funders.md) as data,
computes the institution's internal deadline from the research office's
rule, checks that every registry page still loads, polls the funders' feeds
for what is new, and renders the agent's rows as a report. A timer can run
the poll; the agent runs the rest.

## The profile

A search without a profile returns a list of funders the person could have
found themselves. Record who is asking once:

```bash
murmurent prospect profile new cf_phd --who student --field "cystic fibrosis genomics" \
    --terms "cystic fibrosis, genomics, CFTR" --citizenship "Canadian citizen" --horizon-months 12
murmurent prospect profile show cf_phd
murmurent prospect profile list
```

`--who` is `student`, `postdoc`, `early_pi` or `pi`. `--terms` are the
public words a web search may carry; nothing else about the person leaves
the machine. Profiles live under `~/.murmurent/prospect/profiles/`.

## The registry and the institution's tier

```bash
murmurent prospect registry                 # every entry, by tier, with how its page loads
murmurent prospect registry --tier canada   # one tier
murmurent prospect registry --feeds         # only entries the poller can read
```

The first line says whether the institution pack on this machine has a
`funding.yaml` (the institution's own competitions, the research office's
screened lists, and its internal deadline rule). Without one, that tier is
`Unknown`. The schema is in [the institution pack](institution_pack.md).

## The internal deadline

```bash
murmurent prospect internal-deadline 2027-03-03
murmurent prospect internal-deadline 2027-03-03 --kind tri_agency
```

Counts the rule's working days back from the sponsor's deadline over the
pack's holidays, and says which part is read (the rule, with its page and
date) and which is computed. `--kind` picks a variant the rule carries
(`tri_agency`, `us_federal`, `partner_contributions` in Western's). Without a
rule in the pack it answers `Unknown` and says so; it never guesses a
number.

## Checking the registry

```bash
murmurent prospect check
murmurent prospect check --tier ontario
```

One honest GET per listing page (a client name that says what it is, the
certifi certificate bundle, no retry, no credentials; a sign-in page is a
refusal). It reports each page as loads, refuses automated reading, behind a
login, or could not be read, and flags every entry whose Loads column in the
registry no longer matches. Exit status 1 when any needs updating, so the
bookworm can run it and act on the flags.

## The feed poll, by hand or on a timer

```bash
murmurent prospect feeds             # what is new since the last run; remembers what it saw
murmurent prospect feeds --dry-run   # the same, without remembering
murmurent prospect feeds --post      # and post what is new to this repository's channel
```

It reads every feed the registry's Feed column names (RSS or Atom) and
CIHR's ResearchNet listing, which is a plain table of opportunity name,
registration deadline and application deadline, and reports the items it has
not seen before. The first run on a machine records everything and reports
nothing new, and says so. `--post` sends the note where `murmurent project
note` would send it, so a session never picks a channel; run it from the
repository whose channel should hear it.

**A server that omits a certificate.** CIHR's ResearchNet sends its own
certificate without the Entrust intermediate that signs it. A browser fetches
the missing link itself; a plain client cannot, so the poll reports
"certificate chain incomplete" for it. The fix is one file: download that
intermediate certificate from its issuer (the browser's certificate viewer
names it; on 2026-11-12 it was Entrust OV TLS Issuing RSA CA 2), save it as
PEM, and set `MURMURENT_CA_BUNDLE=/path/to/it.pem` for the poll. The file
is loaded on top of the standard bundle, never instead of it.

On the lab server, under the service account that runs the other timers
([`service_account.md`](service_account.md)), a weekly user timer:

```ini
# ~/.config/systemd/user/murmurent-prospect-feeds.service
[Unit]
Description=murmurent: poll the funders' feeds for new opportunities
[Service]
Type=oneshot
WorkingDirectory=%h/repos/<the repository whose channel hears it>
ExecStart=/bin/sh -lc 'murmurent prospect feeds --post > %h/.murmurent/prospect_feeds.log 2>&1'

# ~/.config/systemd/user/murmurent-prospect-feeds.timer
[Unit]
Description=murmurent: weekly funding feed poll
[Timer]
OnCalendar=Mon 07:00
Persistent=true
[Install]
WantedBy=timers.target
```

`systemctl --user enable --now murmurent-prospect-feeds.timer`. What the
poll cannot read (the NIH Guide refuses automated clients even for its feed)
is listed under the note each time, not silently dropped.

## The report

The agent writes its rows to a YAML file and the command renders them, so
every report looks the same and nothing is retyped:

```bash
murmurent prospect report rows.yaml --slug cf_phd
```

`rows.yaml` holds a `profile:` block, `rows:` (one per opportunity, with the
fields `opportunity`, `funder`, `tier`, `who_may_apply`, `pays`,
`registration`, `full_deadline`, `internal_deadline`, `link`, `read`,
`status` of `READ`, `SECONDARY` or `UNRESOLVED`), `searched:` (what gave
nothing) and `for_the_bookworm:` (funders the registry should hold). Out
come `./outputs/prospector/<date>_<slug>.html`, a self-contained page with
every link live and no scripts, and `<date>_<slug>.ics`, one all-day event
per dated deadline for the person's calendar. A row with a status the
command does not know is rendered as `UNRESOLVED`, never upgraded.
