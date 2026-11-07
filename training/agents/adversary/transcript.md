# The exchange shown in the movie

Real reply of the adversary, run on 2026-11-07 (Murmurent 2026.11.0) on
examples/paper_example, the synthetic example that ships with murmurent. The
verdict line and the COUNSEL closing line are verbatim; the detail is
shortened to fit a frame.

## 1
Member: Audit examples/paper_example/exp/1_signal/run_all.py and its claim c1 in paper.yaml: colonies grown in serum are larger than controls, and the difference holds under permutation. Is the result sound?
Questions: c1 reproduces exactly (0.95 mm, p=0.0004), but serum and control samples come from different countries and the Methods text misdescribes the code.

- PASS, OBSERVED: re-ran exp/1_signal/run_all.py. Control 4.17 mm, serum
  5.12 mm, difference 0.95 mm, permutation p 0.0004. Reproducible.
- WARNING, OBSERVED: medium is confounded with country. 14 of 20 controls
  are from CA or PE, 13 of 20 serum samples from KR or TR. Stratified by
  country the difference survives (1.02 mm, p 0.0006), but within CA serum
  is smaller than control (4.00 vs 4.32 mm, n=5 vs 7).
- WARNING, OBSERVED: the Methods text says the diameters "were drawn from
  two normal distributions". The script draws nothing: it reads signal.csv.
- WARNING, OBSERVED: the test is one-sided and main.tex does not say so.
- SPECULATED: colonies are independent only if nothing groups isolates
  beyond country, and the data cannot show that.

Verdict: NEEDS REVISION. Report the country imbalance and the stratified
result, correct the Methods sentence, and state that the test is one-sided.
COUNSEL: not applicable — synthetic colony-size comparison: no entity is being acted on, and no governed data is moving.
