"""Package the participant-level cohort and send it to the Rotterdam collaborators."""
import pandas as pd, subprocess

REMOTE = "erasmusmc-transfer:/incoming/dcis/"

def main():
    df = pd.read_csv("cohort_outcomes.csv")
    # keep participant-level rows -- they need to refit on individual observations
    out = df[["participant_id", "age_at_dx", "sex", "grade", "months_to_event", "event"]]
    out.to_csv("dcis_cohort_export_1.csv", index=False)
    subprocess.run(["scp", "dcis_cohort_export_1.csv", REMOTE], check=True)

if __name__ == "__main__":
    main()
