# The exchanges shown in the movie

Real replies of the docent, run on 2026-11-07 (Murmurent 2026.11.0) on a copy of
examples/thesis_example; the same exchanges as training/thesis_package/docent_transcript.md,
which the long movie uses. The verdict lines are verbatim; the detail is shortened to fit a frame.

## 1
External examiner: Where does the thesis show that serum enlarges colonies, and does that result hold? Re-run it.
Located — Chapter 2, Results, first paragraph (claim c1, fig:signal). Re-run: serum 5.12 mm
vs control 4.17 mm, difference 0.95 mm, permutation p = 0.0004. The result holds.

Where: build/claim_map.md, chapter 2, row c1; thesis of record build/main.pdf, chapter 2,
Results, Figure 2.1: "Colonies grown in serum were larger than controls ... the difference
held under permutation." The PDF and the package agree.
Re-run: cd paper_example && python3 exp/1_signal/run_all.py   (data/signal.csv, 40 isolates)
  mean_control_mm 4.17   mean_serum_mm 5.12   difference_mm 0.95   permutation_p 0.0004
  5000 permutations, seed 0. Identical to the results.tsv already in the package.
Not said in the text: no significance threshold; main.tex line 13 says the data are made up.
Onward: whether a permutation test on 40 simulated values is the right evidence is for
the adversary, citing claim c1. Logged in queries/examiner/2026-11-07.md.

## 2
External examiner: Does the thesis address incubation temperature?
Absent — no chapter, claim, script or data column mentions incubation temperature; the only
growth condition the thesis varies is the medium (serum versus control).

Searched, no match for "temperature", "incubat" or a degree value: thesis.yaml (c3.1),
paper_example/paper.yaml (c1), build/claim_map.md; every chapter and front-matter file;
paper_example/main.tex; the text of build/main.pdf. data/signal.csv has columns isolate,
medium, colony_mm, country: no temperature. Neither run_all.py reads or sets one.
Nearest thing the thesis does address: growth medium (main.tex, Methods and Results,
claim c1) and country of origin (chapters/03_metadata.tex, claim c3.1). Methods say the
diameters were drawn from two normal distributions, so no incubation took place.
Logged in queries/examiner/2026-11-07.md, append-only.
