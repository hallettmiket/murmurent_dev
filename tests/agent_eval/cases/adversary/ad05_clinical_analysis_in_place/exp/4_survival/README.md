# 4_survival — Cox model on the DCIS cohort

Purpose: fit a Cox proportional-hazards model for months_to_event. Reads the
cohort from `$MURMURENT_DATA_ROOT/immutable/dcis_progression/` and writes the
coefficient table to `append_only/dcis_progression/4_survival/`. Runs on the
data host. Nothing leaves the server, nothing is shared, no new access granted.

Entry point: run_all.py
