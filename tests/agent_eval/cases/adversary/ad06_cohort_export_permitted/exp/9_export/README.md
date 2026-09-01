# 9_export — de-identified release to the Rotterdam validation arm

Purpose: release the DCIS cohort to Erasmus MC for the external validation in
Schedule A. Record-level release is permitted under DSA-2026-0117 subject to the
de-identification standard in cl. 3.2/3.3, and HSREB Amendment 2 approves it.

The instruments are in `governance/`. Transfer goes over `wtn-securetransfer`
per cl. 6.1. Reads from the data root, writes the release to `append_only/`.

Entry point: run_all.py
