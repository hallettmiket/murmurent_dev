# 9_export — send the cohort to the Rotterdam group

Purpose: package the participant-level outcome table and send it to our
collaborators at Erasmus MC so they can run the external validation arm.

Contact: Dr. van der Berg's group. They asked for row-level data (not summary
stats) because they need to refit the model on individual observations.

Entry point: run_all.py  ->  writes dcis_cohort_export_1.csv, then scp's it.
Runs Thursday once the last outcomes are entered.
