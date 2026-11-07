# The exchange shown in the movie

Real reply of the teacher in EXPLAIN mode, run on 2026-11-07 (Murmurent
2026.11.0) about examples/paper_example. The verdict line is verbatim; the
detail is shortened to fit a frame.

## 1
Member: teacher explain: what a permutation test is and why examples/paper_example uses one with 5000 permutations to compare colony sizes in serum and control. In chat, for a wet-lab biologist.
Explained: the test shuffles the serum and control labels 5000 times to see how often chance alone gives a gap as big as the real one. Here it happened once.

- The question. Serum colonies average 5.12 mm and controls 4.17 mm
  (20 isolates each, simulated), a gap of 0.95 mm. Could that be luck?
- The trick. If serum does nothing, the labels are arbitrary. So the script
  pools all 40 sizes, deals them at random into two piles of 20, and records
  the gap. That is one permutation (a random reshuffling of the labels).
- The count. Of 5000 shuffles, exactly 1 gave a gap of 0.95 mm or more
  (I re-ran it to check). The p-value is (1 + 1) / (5000 + 1) = 0.0004.
- Why 5000. There are about 138 billion ways to split 40 numbers into two
  piles of 20. A sample of 5000 gives a p-value precise to about one
  shuffle in a few thousand, plenty for a decision at the 0.05 level.
- Why not a t-test. A t-test assumes roughly bell-shaped data. Shuffling
  assumes only that the labels could be swapped if serum had no effect.

Takeaway: when you ask "could this be chance?", build the chance version
yourself by scrambling what the claim depends on, and count.
