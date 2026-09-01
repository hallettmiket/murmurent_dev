"""Cox PH on the DCIS cohort. Runs in place on the data host; no data leaves."""
import os
import pandas as pd
from lifelines import CoxPHFitter

def main():
    root = os.environ["MURMURENT_DATA_ROOT"]
    df = pd.read_csv(f"{root}/immutable/dcis_progression/cohort_outcomes.csv")
    # sex is 1.7% male here (3/180) -- too rare to model, left out deliberately
    d = df[["age_at_dx", "grade", "months_to_event", "event"]]
    cph = CoxPHFitter().fit(d, duration_col="months_to_event", event_col="event")
    outdir = f"{root}/append_only/dcis_progression/4_survival"
    os.makedirs(outdir, exist_ok=True)
    cph.summary.to_csv(f"{outdir}/cox_summary_1.csv")
    print(cph.summary[["coef", "p"]])

if __name__ == "__main__":
    main()
