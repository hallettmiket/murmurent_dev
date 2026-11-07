# The Western pack

The institution pack for Western University: what the clerk answers from. It
is deployment content and does not ship in the public release. The schema and
how to keep a pack are in `docs/institution_pack.md` of murmurent.

Every fact here was read from a page on `uwo.ca` or `westernu.ca` on the date
its `date_read` says, and nothing else. What a page did not give is left out
rather than guessed; where that matters the entry carries a `note:` saying so.

What could not be read on 2026-11-07, and so is not here:

- The SGPS site's own leadership, contact and staff pages returned "page not
  found", so the Vice-Provost (Graduate and Postdoctoral Studies) is recorded
  from the Provost's leadership team page with no email or address, and the
  SGPS office address is not recorded.
- The President's page gives no email for the office.
- The Western Research pages give the office email but no campus address.
- The Academic Calendar does not list New Year's Day, Christmas, Labour Day
  2027 or Thanksgiving 2027; the holidays here are the HR holiday schedule,
  which does.
- The public master timetable shows no meeting days, times or rooms; see the
  `limits` in `courses.yaml`.
- Named deadlines for grants, annual reports and Senate submissions were not
  read from any public page; `deadlines:` is empty.

Keeping it: `murmurent institution refresh --pack western` (dry run) and
`--apply`. The bookworm runs it on a schedule; a fact it reports as changed is
edited by a person.
