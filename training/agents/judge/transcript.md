# The exchange shown in the movie

Real reply, run on 2026-11-07 (Murmurent 2026.11.0). The verdict line is verbatim; the detail is shortened to fit a frame. `make.py` reads this file: each `## <key>` section starts with `<who>: <question>`, then the reply lines. Run on a synthetic run package (five invented compounds, two invented labs) made for this movie.

## 1
Poser: Present the run: which compounds should go to the next assay round, and where do the two contributions disagree?
Split: docking and K_D are not on a shared scale, so there is no combined score. The poser's rule favours measured binding, which sends cpd_05 and cpd_01 to the next round. All 5 compounds shown.

  compound  docking kcal/mol  rank   K_D nM (± SE)   rank
  cpd_05    -9.1              3      18 ± 4          1
  cpd_01    -9.8              2      42 ± 6          2
  cpd_02    -8.1              4      310 ± 40        3
  cpd_03    -10.4             1      870 ± 120       4
  cpd_04    -7.2              5      not assayed     n/a
- Criteria: joined on compound_id, ordered by K_D, which the poser ranks
  above docking. The metrics differ, so no weights and no consensus.
- Next round: cpd_05 and cpd_01; their error bars do not overlap.
- Disagreement flagged: cpd_03 ranks 1st in docking but last in the assay.
- Coverage gap: the assay has no result for cpd_04. It stays in the table.
- Handoff to the artist: the two rankings with lines joining each
  compound's ranks, cpd_03 highlighted and cpd_04 marked as untested.
