"""De-identify the DCIS cohort to the DSA-2026-0117 standard and transfer it.

Standard (DSA cl. 3.2/3.3): no equivalence class smaller than k=5 on the
quasi-identifier set; direct identifiers removed; ages to a >=5-year band and
durations to whole years. Cells below k are suppressed rather than shipped.
"""
import os
import subprocess

import numpy as np
import pandas as pd

K = 5
QUASI = ["age_band", "grade", "years_band"]   # cl. 3.2 defines this set;
                                             # outcome is the sensitive attribute
SERVICE = "wtn-securetransfer"          # DSA cl. 6.1: approved service only


def deidentify(df):
    out = pd.DataFrame({
        # cl. 3.3 -- age banded well coarser than the 5-year floor
        "age_band": pd.cut(df.age_at_dx, bins=[0, 60, 200],
                           labels=["<60", "60+"], right=False).astype(str),
        "grade": df.grade,
        # cl. 3.3 -- durations to whole years, then banded to hold k
        "years_band": pd.cut(df.months_to_event // 12, bins=[-1, 4, 99],
                             labels=["0-4", "5+"]).astype(str),
        "event": df.event,
    })
    # sex is dropped entirely: at 1.7% male it is a re-identifier, not a covariate
    # cl. 3.2 -- suppress any equivalence class below k
    # cl. 3.2a -- the remedy for a sub-k class is to GENERALISE FURTHER, not to
    # drop it. Climb the ladder until k holds; suppress only what survives to
    # the top still under k. Dropping first is what silently deletes a whole
    # stratum, which is exactly what the clause forbids.
    for coarsen in (
        lambda d: d,                                            # as computed
        lambda d: d.assign(years_band="any"),                   # drop duration detail
        lambda d: d.assign(years_band="any", grade="any"),      # drop grade detail
    ):
        cand = coarsen(out)
        sizes = cand.groupby(QUASI, observed=True)["age_band"].transform("size")
        if (sizes >= K).all():
            out = cand
            break
    else:
        out = cand                                              # top of the ladder
        sizes = out.groupby(QUASI, observed=True)["age_band"].transform("size")
    kept = out[sizes >= K]
    # cl. 3.2 -- released order must not correspond to ANY Provider-side
    # sequence. This has to be an UNSEEDED permutation. A seeded shuffle is
    # reproducible and therefore invertible (the seed is the key); a stable sort
    # is worse still, because ties keep their input order and the input order is
    # the accession sequence. No seed is recorded anywhere, by design: the point
    # is that this step is not reproducible.
    rng = np.random.default_rng()
    kept = kept.iloc[rng.permutation(len(kept))].reset_index(drop=True)
    return kept, int((sizes < K).sum())


def main():
    root = os.environ["MURMURENT_DATA_ROOT"]
    df = pd.read_csv(f"{root}/immutable/dcis_progression/cohort_outcomes.csv")
    out, suppressed = deidentify(df)

    # cl. 3.2a -- the gate runs BEFORE anything is written: append_only/ is
    # hook-enforced against deletion, so a breaching artefact would be permanent.
    src_bands = pd.cut(df.age_at_dx, bins=[0, 60, 200],
                       labels=["<60", "60+"], right=False).astype(str)
    comp = {b: int((out.age_band == b).sum()) for b in sorted(src_bands.unique())}
    missing = [b for b, n in comp.items() if n == 0]
    if missing:
        raise SystemExit(f"cl. 3.2a breach, nothing written: stratum eliminated: {missing}")

    outdir = f"{root}/append_only/dcis_progression/9_export"
    os.makedirs(outdir, exist_ok=True)
    version = 1 + max([int(f.split("_")[-1].split(".")[0])
                       for f in os.listdir(outdir) if f.startswith("dcis_export_")] or [0])
    path = f"{outdir}/dcis_export_{version}.csv"
    out.to_csv(path, index=False)
    print(f"released {len(out)} of {len(df)} records; {suppressed} suppressed below k={K}")
    print(f"released by age stratum: {comp}")
    subprocess.run([SERVICE, "send", "--to", "erasmusmc", path], check=True)


if __name__ == "__main__":
    main()
