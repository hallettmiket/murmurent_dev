"""Rank docked poses and emit the synthesis shortlist."""
import pandas as pd

W_DOCK, W_LE = 0.6, 0.4

def rescore(df):
    """Consensus of docking score and ligand efficiency, both pre-standardized."""
    return df.assign(consensus=(W_DOCK * df.dock_z + W_LE * df.le_z).round(3))

def main():
    poses = pd.read_csv("poses.csv")
    meta = pd.read_csv("compounds.csv")
    ranked = (
        rescore(poses)
        .merge(meta, on="compound_id", how="left")
        .sort_values("consensus", ascending=False)
        .head(12)
        .reset_index(drop=True)
    )
    ranked.insert(0, "rank", ranked.index + 1)
    ranked.to_csv("shortlist_1.csv", index=False)
    print(ranked[["rank", "compound_id", "common_name", "consensus"]].to_string(index=False))

if __name__ == "__main__":
    main()
