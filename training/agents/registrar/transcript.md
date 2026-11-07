# The exchange shown in the movie

Real reply, run on 2026-11-07 (Murmurent 2026.11.0). The verdict line is verbatim; the detail is shortened to fit a frame. `make.py` reads this file: each `## <key>` section starts with `<who>: <question>`, then the reply lines. A read-only view of the registry on this machine.

## 1
Administrative head: Give me the institution-level view: which labs and cores are registered in this centre, who leads each, and whether any registry entry is incomplete.
Clear — 1 lab registered (mh, led by @mhallet, active), 0 cores, 0 collaborations; the entry resolves, but the registrar list is empty and no registrar file is set.

- Registry: ~/.murmurent/lab_info/_registry.yaml (version 1)
- Lab "mh": PI @mhallet, status active, records at
  ~/repos/murmurent_lab_mgmt_mh
- Pointer check: that folder exists and holds lab.md, members, policy
  and cert_projects, so it resolves
- Cores: none. Collaborations: none
- Incomplete: the registrars list is empty, and ~/.murmurent/registrar
  does not exist
- Nothing was recorded or changed (read-only run)
