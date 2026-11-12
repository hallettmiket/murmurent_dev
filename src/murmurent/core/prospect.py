"""
Purpose: The deterministic half of the prospector (#313): the funder
         registry, a person's funding profile, the institution's internal
         deadline, a check that every registry page still loads, a poller
         over the funders' feeds, and the report files.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-12
Input: ``docs/funders.md`` (the registry, bookworm-kept), the institution
       pack's ``funding.yaml``, profiles under ``~/.murmurent/prospect/``,
       and rows the prospector agent wrote.
Output: Profiles, check and feed reports, an HTML report and a calendar file.

What this module does NOT do is judge: reading a funder's page and deciding
whether a person may apply is the agent's. Everything here is a lookup, a
fetch, a date computation or a rendering, so a timer can run the feed poll
with no model, and the agent's report is rendered the same way every time.

Fetching is public and honest: one GET with a client name that says what it
is, the ``certifi`` bundle (some funders' servers send an incomplete
certificate chain), no retry with credentials, and a sign-in page is a
refusal. A site that answers 401 or 403 is reported as refusing automated
reading; nothing here pretends to be a browser.
"""

from __future__ import annotations

import html as _html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import yaml

from . import institution as _inst

USER_AGENT = "murmurent-prospect/1 (+research funding registry check)"
FETCH_TIMEOUT = 30
WHO = ("student", "postdoc", "early_pi", "pi")
FUNDING_FILE = "funding.yaml"
FUNDERS_ENV = "MURMURENT_FUNDERS_FILE"
CA_BUNDLE_ENV = "MURMURENT_CA_BUNDLE"   # a PEM file of extra CA certificates, for servers that omit an intermediate

Fetcher = Callable[[str], "FetchResult"]


# --------------------------------------------------------------------------- #
# Where things live
# --------------------------------------------------------------------------- #


def prospect_dir(env: dict[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    home = Path(env.get("MURMURENT_HOME") or (Path.home() / ".murmurent")).expanduser()
    return home / "prospect"


def registry_path(env: dict[str, str] | None = None) -> Path:
    """``docs/funders.md``: ``$MURMURENT_FUNDERS_FILE``, else the repository
    this package is installed from."""
    env = os.environ if env is None else env
    if env.get(FUNDERS_ENV):
        return Path(env[FUNDERS_ENV]).expanduser()
    return Path(__file__).resolve().parents[3] / "docs" / "funders.md"


# --------------------------------------------------------------------------- #
# The profile: who is asking
# --------------------------------------------------------------------------- #


@dataclass
class Profile:
    name: str
    who: str                      # student | postdoc | early_pi | pi
    field: str                    # "cystic fibrosis genomics"
    terms: list[str] = field(default_factory=list)   # the public words a search may carry
    citizenship: str = ""         # "Canadian citizen", "permanent resident", "international"
    horizon_months: int = 12
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "who": self.who, "field": self.field, "terms": list(self.terms),
                "citizenship": self.citizenship, "horizon_months": self.horizon_months, "notes": self.notes}

    def problems(self) -> list[str]:
        out = []
        if not re.fullmatch(r"[a-z0-9_-]{1,40}", self.name or ""):
            out.append("name: letters, digits, _ and - only")
        if self.who not in WHO:
            out.append(f"who: one of {', '.join(WHO)}")
        if not self.field.strip():
            out.append("field: say what the research is about, in public words")
        if not (1 <= int(self.horizon_months) <= 36):
            out.append("horizon_months: between 1 and 36")
        return out


def profiles_dir(env: dict[str, str] | None = None) -> Path:
    return prospect_dir(env) / "profiles"


def save_profile(profile: Profile, env: dict[str, str] | None = None) -> Path:
    problems = profile.problems()
    if problems:
        raise ValueError("; ".join(problems))
    folder = profiles_dir(env)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{profile.name}.yaml"
    path.write_text(yaml.safe_dump(profile.to_dict(), sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def load_profile(name: str, env: dict[str, str] | None = None) -> Profile:
    path = profiles_dir(env) / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"no profile named {name!r} ({path})")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Profile(name=str(data.get("name") or name), who=str(data.get("who") or ""),
                   field=str(data.get("field") or ""), terms=[str(t) for t in (data.get("terms") or [])],
                   citizenship=str(data.get("citizenship") or ""),
                   horizon_months=int(data.get("horizon_months") or 12), notes=str(data.get("notes") or ""))


def list_profiles(env: dict[str, str] | None = None) -> list[str]:
    folder = profiles_dir(env)
    return sorted(p.stem for p in folder.glob("*.yaml")) if folder.is_dir() else []


# --------------------------------------------------------------------------- #
# The registry: docs/funders.md, read as data
# --------------------------------------------------------------------------- #


@dataclass
class RegistryEntry:
    agency: str
    tier: str            # the section heading: Canada, Ontario, Disease and field charities, ...
    listing: str         # the page that lists competitions
    gave: str
    loads: str           # plain | script | refused | mixed text
    feeds: list[str]
    funds: str
    checked: str         # YYYY-MM-DD

    @property
    def loads_plain(self) -> bool:
        return self.loads.strip().lower().startswith("plain")


_URL = re.compile(r"https?://[^\s<>()|]+")
_ROW_HEADER = "| Agency |"


def _cells(line: str) -> list[str]:
    inner = line.strip().strip("|")
    return [c.strip() for c in re.split(r"(?<!\\)\|", inner)]


def load_registry(path: Path | None = None) -> list[RegistryEntry]:
    """Every agency row of the registry's tier tables, in file order. Only
    tables whose header starts with ``| Agency |`` count, so the explanatory
    tables and the closed-or-renamed table are skipped."""
    path = path or registry_path()
    text = path.read_text(encoding="utf-8")
    entries: list[RegistryEntry] = []
    tier = ""
    in_table = False
    for line in text.splitlines():
        if line.startswith("## "):
            tier = line[3:].strip()
            in_table = False
            continue
        if line.startswith(_ROW_HEADER):
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table and line.startswith("|"):
            cells = _cells(line)
            if len(cells) < 7:
                continue
            agency, listing, gave, loads, feed, funds, checked = cells[:7]
            urls = _URL.findall(listing)
            entries.append(RegistryEntry(
                agency=re.sub(r"\s+", " ", agency), tier=tier,
                listing=urls[0].rstrip(">") if urls else "",
                gave=gave, loads=loads, feeds=[u.rstrip(">") for u in _URL.findall(feed)],
                funds=funds, checked=checked))
        elif in_table and not line.strip():
            in_table = False
    return entries


# --------------------------------------------------------------------------- #
# The institution's tier and its internal deadline rule
# --------------------------------------------------------------------------- #


def institution_funding(pack: _inst.Pack | None) -> dict[str, Any]:
    """The pack's ``funding.yaml`` as a dict, or ``{}``."""
    if pack is None:
        return {}
    path = pack.root / FUNDING_FILE
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


@dataclass
class InternalDeadline:
    sponsor: date
    internal: date | None
    days: int | None
    kind: str
    rule: str
    source: str
    date_read: str
    explanation: str

    @property
    def known(self) -> bool:
        return self.internal is not None


def internal_deadline(pack: _inst.Pack | None, sponsor: date, kind: str = "") -> InternalDeadline:
    """The institution's internal deadline for a sponsor deadline, from the
    rule in the pack's ``funding.yaml``, counted in working days over the
    pack's holidays. ``kind`` picks a variant from the rule's ``by:`` map
    (``tri_agency``, say); the plain rule otherwise. Unknown when the pack
    has no rule, with the reason."""
    funding = institution_funding(pack)
    rule = funding.get("internal_deadline") if isinstance(funding.get("internal_deadline"), dict) else {}
    if not rule:
        why = ("no institution pack on this machine" if pack is None
               else f"the pack {pack.unique_name} has no {FUNDING_FILE} with an internal_deadline rule")
        return InternalDeadline(sponsor, None, None, kind, "", "", "", f"Unknown: {why}.")
    days = rule.get("working_days")
    by = rule.get("by") if isinstance(rule.get("by"), dict) else {}
    if kind and kind in by:
        days = by[kind]
    try:
        n = int(days)
    except (TypeError, ValueError):
        return InternalDeadline(sponsor, None, None, kind, str(rule.get("rule") or ""),
                                str(rule.get("source") or ""), str(rule.get("date_read") or ""),
                                "Unknown: the rule states no number of working days; read it on its page.")
    internal = _inst.working_days_from(pack, sponsor, n)
    skipped = _inst.holidays_between(pack, sponsor, internal)
    text = (f"{abs(n)} working days {'before' if n < 0 else 'after'} the sponsor's {sponsor.isoformat()} "
            f"is {internal.isoformat()} ({internal.strftime('%A')}), computed from the rule read on "
            f"{rule.get('date_read') or 'an unknown date'}")
    if skipped:
        text += "; skipped " + ", ".join(f"{d.isoformat()} {name}" for d, name in skipped)
    if kind and kind in by:
        text += f"; the {kind} variant"
    return InternalDeadline(sponsor, internal, n, kind, str(rule.get("rule") or ""),
                            str(rule.get("source") or ""), str(rule.get("date_read") or ""), text + ".")


# --------------------------------------------------------------------------- #
# Fetching: public, honest, once
# --------------------------------------------------------------------------- #


@dataclass
class FetchResult:
    url: str
    status: int = 0
    ok: bool = False
    kind: str = "error"      # ok | refused | login | error
    title: str = ""
    text: str = ""           # the body, for parsers; empty on failure
    note: str = ""


def ssl_context(env: dict[str, str] | None = None):
    """The certifi bundle, plus the PEM file ``$MURMURENT_CA_BUNDLE`` names
    when it is set. Some funders' servers (CIHR's ResearchNet on
    2026-11-12) omit an intermediate certificate that browsers fetch for
    themselves and a plain client cannot; the person downloads that
    intermediate from its issuer once and points the variable at it."""
    env = os.environ if env is None else env
    ctx = _inst._ssl_context()
    extra = env.get(CA_BUNDLE_ENV)
    if extra and Path(extra).expanduser().is_file():
        try:
            ctx.load_verify_locations(cafile=str(Path(extra).expanduser()))
        except Exception:  # noqa: BLE001 - a bad file is the same as none
            pass
    return ctx


def fetch(url: str, timeout: int = FETCH_TIMEOUT, _retry: bool = True) -> FetchResult:
    """One GET of a public page. A 401 or 403 is ``refused`` (the site does
    not admit automated readers); a sign-in page is ``login``; anything else
    that fails is ``error``. Never retried with other headers or credentials.
    The one retry is for a certificate failure: some funders run several
    servers and only some send the full chain, so a second try often lands
    on one that does."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            status = resp.status
            final = resp.geturl()
    except urllib.error.HTTPError as exc:
        kind = "refused" if exc.code in (401, 403) else "error"
        return FetchResult(url, exc.code, False, kind, note=f"answered {exc.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = str(getattr(exc, "reason", exc))
        if "CERTIFICATE_VERIFY_FAILED" in reason:
            if _retry:
                return fetch(url, timeout, _retry=False)
            return FetchResult(url, 0, False, "error",
                               note=f"certificate chain incomplete (twice); a PEM of the missing intermediate in ${CA_BUNDLE_ENV} fixes it")
        return FetchResult(url, 0, False, "error", note=reason[:120])
    text = raw.decode(charset, errors="replace")
    if _inst._LOGIN_PAGE.search(text[:20000]) or _inst._LOGIN_PATH.search(urllib.parse.urlsplit(final).path or ""):
        return FetchResult(url, status, False, "login", note="a sign-in page")
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    title = re.sub(r"\s+", " ", _html.unescape(m.group(1))).strip() if m else ""
    return FetchResult(url, status, True, "ok", title=title, text=text)


@dataclass
class CheckResult:
    entry: RegistryEntry
    result: FetchResult

    def line(self) -> str:
        r = self.result
        what = {"ok": f"loads ({r.title[:60]})" if r.title else "loads",
                "refused": f"refuses automated reading ({r.note})",
                "login": "behind a login", "error": f"could not be read ({r.note})"}[r.kind]
        flag = ""
        if r.kind == "ok" and self.entry.loads.lower().startswith("refused"):
            flag = "  <- the registry says refused; update it"
        if r.kind != "ok" and self.entry.loads_plain:
            flag = "  <- the registry says plain; update it"
        return f"{self.entry.agency}: {what}{flag}"


def check_registry(entries: list[RegistryEntry], fetcher: Fetcher | None = None) -> list[CheckResult]:
    """Fetch each entry's listing page once and say whether it still loads
    the way the registry claims."""
    fetcher = fetcher or fetch
    out = []
    for e in entries:
        if not e.listing:
            out.append(CheckResult(e, FetchResult("", 0, False, "error", note="no listing page in the registry")))
            continue
        out.append(CheckResult(e, fetcher(e.listing)))
    return out


# --------------------------------------------------------------------------- #
# Feeds: RSS, Atom, and the one listing table worth parsing
# --------------------------------------------------------------------------- #


@dataclass
class FeedItem:
    feed: str
    title: str
    link: str
    published: str = ""
    deadline: str = ""     # when the feed says one (ResearchNet does)
    loi: str = ""

    @property
    def key(self) -> str:
        return self.link or self.title


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def parse_feed(text: str, feed_url: str) -> list[FeedItem]:
    """Items of an RSS 2.0 or Atom feed. A feed that does not parse gives
    no items rather than an exception; the caller reports the feed."""
    try:
        root = ET.fromstring(text.encode("utf-8", errors="replace"))
    except ET.ParseError:
        return []
    items: list[FeedItem] = []
    for node in root.iter():
        tag = _strip_ns(node.tag)
        if tag not in ("item", "entry"):
            continue
        title = link = published = ""
        for child in node:
            ctag = _strip_ns(child.tag)
            if ctag == "title":
                title = (child.text or "").strip()
            elif ctag == "link":
                link = (child.text or "").strip() or (child.attrib.get("href") or "").strip()
            elif ctag in ("pubDate", "published", "updated", "date"):
                published = published or (child.text or "").strip()
        if title or link:
            items.append(FeedItem(feed_url, re.sub(r"\s+", " ", title), link, published))
    return items


_RN_ROW = re.compile(
    r"<a[^>]+href=\"(?P<href>vwOpprtntyDtls\.do[^\"]*)\"[^>]*>(?P<name>.*?)</a>.*?"
    r"<td[^>]*>(?P<loi>[^<]*)</td>\s*<td[^>]*>(?P<deadline>[^<]*)</td>", re.S)


def parse_researchnet(text: str, base: str) -> list[FeedItem]:
    """The rows of CIHR's ResearchNet listing of current opportunities: name,
    registration or letter-of-intent deadline, application deadline. The
    page is a plain table; this reads it as one so the poller needs no
    model and no feed."""
    items = []
    for m in _RN_ROW.finditer(text):
        name = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", m.group("name")))).strip()
        link = urllib.parse.urljoin(base, _html.unescape(m.group("href")))
        items.append(FeedItem(base, name, link, loi=m.group("loi").strip(), deadline=m.group("deadline").strip()))
    return items


def is_feed_url(url: str) -> bool:
    """A feed, not a page about feeds: ends in .xml, .rss or .atom, or its
    path ends in /feed, or it is ResearchNet's fodRss."""
    path = urllib.parse.urlsplit(url).path.lower().rstrip("/")
    return path.endswith((".xml", ".rss", ".atom")) or path.endswith("/feed") or "fodrss" in path


def is_researchnet(url: str) -> bool:
    return "researchnet-recherchenet.ca" in url and "search.do" in url


def feed_sources(entries: list[RegistryEntry]) -> list[tuple[RegistryEntry, str]]:
    """Every feed the registry names, plus the ResearchNet listing where a
    registry entry's listing page is one, each with its entry."""
    out = []
    for e in entries:
        if e.listing and is_researchnet(e.listing):
            out.append((e, e.listing))
        for f in e.feeds:
            if is_feed_url(f):
                out.append((e, f))
    return out


@dataclass
class PollReport:
    new: list[FeedItem] = field(default_factory=list)
    seen_total: int = 0
    polled: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    first_run: bool = False


def state_path(env: dict[str, str] | None = None) -> Path:
    return prospect_dir(env) / "feeds_seen.json"


def poll_feeds(entries: list[RegistryEntry], *, fetcher: Fetcher | None = None,
               state: Path | None = None, remember: bool = True) -> PollReport:
    """Read every feed source once, report the items not seen before, and
    remember what was seen. The first run on a machine reports nothing new
    (there is no "before") and only records; say so."""
    fetcher = fetcher or fetch
    state = state or state_path()
    seen: dict[str, list[str]] = {}
    if state.is_file():
        try:
            seen = json.loads(state.read_text(encoding="utf-8")) or {}
        except (OSError, json.JSONDecodeError):
            seen = {}
    report = PollReport(first_run=not seen)
    for entry, url in feed_sources(entries):
        result = fetcher(url)
        if not result.ok:
            report.failed.append((f"{entry.agency}: {url}", f"{result.kind}: {result.note}"))
            continue
        items = parse_researchnet(result.text, url) if is_researchnet(url) else parse_feed(result.text, url)
        if not items:
            report.failed.append((f"{entry.agency}: {url}", "no items could be read from it"))
            continue
        report.polled.append(f"{entry.agency}: {url} ({len(items)} items)")
        known = set(seen.get(url, []))
        if url in seen:
            report.new += [i for i in items if i.key not in known]
        seen[url] = sorted(known | {i.key for i in items})
    report.seen_total = sum(len(v) for v in seen.values())
    if remember:
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps(seen, indent=0, sort_keys=True), encoding="utf-8")
    return report


def format_poll_note(report: PollReport, entries: list[RegistryEntry], limit: int = 12) -> str:
    """One Slack-sized note on what is new: agency, title, deadline when the
    feed gave one, link. No paths."""
    by_feed = {url: e.agency for e, url in feed_sources(entries)}
    if report.first_run:
        return ("Funding feeds: first poll on this machine, so nothing counts as new yet; "
                f"{report.seen_total} items recorded across {len(report.polled)} feeds.")
    if not report.new:
        return f"Funding feeds: nothing new across {len(report.polled)} feeds."
    lines = [f"Funding feeds: {len(report.new)} new item{'s' if len(report.new) != 1 else ''}."]
    for item in report.new[:limit]:
        when = f" (deadline {item.deadline})" if item.deadline else ""
        lines.append(f"- {by_feed.get(item.feed, '')}: {item.title}{when} {item.link}".rstrip())
    if len(report.new) > limit:
        lines.append(f"- and {len(report.new) - limit} more")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# The report: rows the agent wrote, rendered the same way every time
# --------------------------------------------------------------------------- #

ROW_FIELDS = ("opportunity", "funder", "tier", "who_may_apply", "pays", "registration",
              "full_deadline", "internal_deadline", "link", "read", "status")
STATUSES = ("READ", "SECONDARY", "UNRESOLVED")


def load_rows(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """``rows.yaml``: a ``profile:`` block (free) and ``rows:``, each with the
    fields in ROW_FIELDS. Missing fields are empty, never invented."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    head = dict(data.get("profile")) if isinstance(data.get("profile"), dict) else {}
    rows = []
    for raw in data.get("rows") or []:
        if not isinstance(raw, dict):
            continue
        row = {k: str(raw.get(k) or "") for k in ROW_FIELDS}
        if row["status"] not in STATUSES:
            row["status"] = "UNRESOLVED"
        rows.append(row)
    head["searched"] = [str(s) for s in (data.get("searched") or [])]
    head["for_the_bookworm"] = [str(s) for s in (data.get("for_the_bookworm") or [])]
    return head, rows


def _esc(s: str) -> str:
    return _html.escape(s, quote=True)


def _date_only(text: str) -> date | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def render_html(head: dict[str, Any], rows: list[dict[str, Any]], today: date | None = None) -> str:
    today = today or date.today()
    title = f"Funding opportunities for {head.get('name') or head.get('who') or 'a researcher'}"
    cols = [("opportunity", "Opportunity"), ("funder", "Funder"), ("tier", "Tier"),
            ("who_may_apply", "Who may apply"), ("pays", "Pays"), ("registration", "Registration or LOI"),
            ("full_deadline", "Full deadline"), ("internal_deadline", "Internal deadline"),
            ("read", "Read"), ("status", "Status")]
    parts = [
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        f"<title>{_esc(title)}</title>",
        "<style>body{font:15px/1.45 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin:2rem;max-width:72rem;color:#222}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:.4rem .5rem;vertical-align:top;text-align:left}"
        "th{background:#f3f0ea}tr.UNRESOLVED td{color:#777}tr.SECONDARY td{background:#fffbe6}"
        ".small{color:#555;font-size:.9em}h1{font-size:1.5rem}h2{font-size:1.15rem;margin-top:2rem}</style></head><body>",
        f"<h1>{_esc(title)}</h1>",
        f"<p class=\"small\">Read on {today.isoformat()}. Every row was read on the funder's own page on the date in its Read column; "
        "a row marked UNRESOLVED could not be read today and says why. The institution's internal deadline comes from the "
        "research office's rule in the institution pack, or is Unknown.</p>",
    ]
    if head.get("field") or head.get("who"):
        parts.append("<p><b>Profile.</b> " + _esc(", ".join(
            s for s in [str(head.get("who") or ""), str(head.get("field") or ""),
                        str(head.get("citizenship") or ""),
                        f"horizon {head['horizon_months']} months" if head.get("horizon_months") else ""] if s)) + "</p>")
    parts.append("<table><thead><tr>" + "".join(f"<th>{_esc(h)}</th>" for _, h in cols) + "</tr></thead><tbody>")
    for r in rows:
        cells = []
        for key, _ in cols:
            val = _esc(r.get(key, ""))
            if key == "opportunity" and r.get("link"):
                val = f"<a href=\"{_esc(r['link'])}\">{val or _esc(r['link'])}</a>"
            cells.append(f"<td>{val}</td>")
        parts.append(f"<tr class=\"{_esc(r.get('status', ''))}\">" + "".join(cells) + "</tr>")
    parts.append("</tbody></table>")
    if head.get("searched"):
        parts.append("<h2>What was searched and did not find</h2><ul>" +
                     "".join(f"<li>{_esc(s)}</li>" for s in head["searched"]) + "</ul>")
    if head.get("for_the_bookworm"):
        parts.append("<h2>For the bookworm</h2><ul>" +
                     "".join(f"<li>{_esc(s)}</li>" for s in head["for_the_bookworm"]) + "</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)


def render_ics(rows: list[dict[str, Any]], today: date | None = None) -> str:
    """One all-day event per dated deadline (registration, full, internal),
    titled with the opportunity and the funder, the link in the description."""
    today = today or date.today()
    stamp = datetime(today.year, today.month, today.day).strftime("%Y%m%dT000000Z")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//murmurent//prospect//EN", "CALSCALE:GREGORIAN"]
    n = 0
    for r in rows:
        for key, label in (("registration", "registration or LOI"), ("full_deadline", "full deadline"),
                           ("internal_deadline", "internal deadline")):
            d = _date_only(r.get(key, ""))
            if d is None:
                continue
            n += 1
            summary = f"{r.get('opportunity') or 'Funding deadline'} ({r.get('funder') or ''}): {label}".replace(",", "\\,")
            desc = (f"{r.get(key)}. {r.get('link') or ''}").replace(",", "\\,")
            lines += ["BEGIN:VEVENT", f"UID:murmurent-prospect-{stamp}-{n}@local", f"DTSTAMP:{stamp}",
                      f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                      f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
                      f"SUMMARY:{summary}", f"DESCRIPTION:{desc}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def write_report(head: dict[str, Any], rows: list[dict[str, Any]], out_dir: Path, slug: str,
                 today: date | None = None) -> tuple[Path, Path]:
    today = today or date.today()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9_-]+", "_", slug.lower()).strip("_") or "funding"
    html_path = out_dir / f"{today.isoformat()}_{slug}.html"
    ics_path = out_dir / f"{today.isoformat()}_{slug}.ics"
    html_path.write_text(render_html(head, rows, today), encoding="utf-8")
    ics_path.write_text(render_ics(rows, today), encoding="utf-8")
    return html_path, ics_path
