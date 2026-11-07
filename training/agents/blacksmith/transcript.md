# The exchange shown in the movie

Real reply, run on 2026-11-07 (Murmurent 2026.11.0). The verdict line is verbatim; the detail is shortened to fit a frame. `make.py` reads this file: each `## <key>` section starts with `<who>: <question>`, then the reply lines. Run on data/signal.csv from examples/paper_example (simulated).

## 1
Member: The adversary says medium is confounded with country in signal.csv. Compute the serum minus control difference in colony diameter within each country, and a permutation test stratified by country (5000 permutations, seed 0). Save results.tsv.
Done: serum effect survives stratifying by country. Weighted within-country difference is +0.85 mm, stratified permutation p = 0.0036. But it is not consistent across countries.

- Confounding confirmed: TR is 7 serum to 2 control, PE is 2 to 7.
  Naive pooled difference is +0.953 mm (20 vs 20 isolates).
- Serum minus control within each country: CA -0.314 (5 vs 7),
  KR +1.452 (6 vs 4), PE +0.728 (2 vs 7), TR +2.226 (7 vs 2), in mm.
- Combined statistic: within-country differences averaged with weights
  n_s*n_c/n, giving +0.850 mm.
- Permutation test: medium labels shuffled only within each country,
  5000 permutations, seed 0, two-sided p = 0.0036.
- Caveat: the countries disagree (CA goes the other way), and PE and TR
  each have only 2 isolates in one arm.
- Results: results.tsv. Code (numpy only): stratified_perm_1.py
