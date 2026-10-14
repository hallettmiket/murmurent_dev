"""Normalise raw nCounter counts."""
import numpy as np
import pandas as pd

HOUSEKEEPING = ["ACTB", "GAPDH", "RPLP0", "TBP", "GUSB"]

def main():
    raw = pd.read_csv("raw_counts.csv", index_col=0)      # genes x samples
    pos = raw.loc[raw.index.str.startswith("POS_")]
    scale = pos.sum().mean() / pos.sum()
    counts = raw * scale
    hk = np.exp(np.log(counts.loc[HOUSEKEEPING]).mean())  # geometric mean per sample
    norm = counts / hk * hk.mean()
    np.log2(norm + 1).to_csv("normalised.csv")

if __name__ == "__main__":
    main()
