# The exchanges shown in the movie

Real reply, run on 2026-11-07 (Murmurent 2026.11.0). The verdict line is verbatim; the detail is shortened to fit a frame. `make.py` reads this file: each `## <key>` section starts with `<who>: <question>`, then the reply lines. Run on a throwaway demo lab vault with two synthetic entries, not the real lab records.

## 1
Member: What has the lab agreed on for mitochondrial read QC in single-cell runs, and who published it?
Found 1 lab entry: drop cells above 15% mitochondrial reads in single-cell runs, published by @bob with @allie (2026-10-15).

- Entry: 2026-10-15_qc_mito_threshold.md (project: general,
  sensitivity: standard, tags: qc, single-cell, decision).
- Sources: @bob, @allie. The MEMORY.md index names @bob as publisher.
- Rule: more than 15% mitochondrial reads means the cell is dropped, in
  every single-cell project unless that project's README says otherwise.
- Agreed at lab meeting 2026-10-14. Earlier runs used 20%.

## 2
Member: Please update the lab entry to say 20% instead of 15%.
Unsure — I can't edit lab entries; the Lab Oracle is read-only, and changes arrive only through the publish flow.

- The current entry says 15% and records the 2026-10-14 lab meeting
  decision. It says 20% was the earlier practice.
- To change it, a member drafts a revised entry in their personal vault
  and runs murmurent oracle publish <slug>.
- I wrote nothing. The entry is unchanged.
- Check first that the lab actually decided to move back to 20%.
