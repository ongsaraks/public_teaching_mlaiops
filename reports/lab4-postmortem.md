# Lab 4 — Injected Drift Incident Post-Mortem

**What fired:**
Drift alert on metric 'drift.psi.temp_c' exceeding threshold (PSI = 0.38333 >= 0.25, KS = 0.24567) on 2026-10-05T07:39:56Z.

**True cause:**
Upstream sensor calibration error causing a systematic +6.0°C positive offset across machine fleet thermocouple readings; underlying mechanical failure dynamics did not change.

**Retrain, roll back, or no action — and why:**
No action on model; fix upstream sensor calibration and invalidate corrupted telemetry. Retraining on corrupted temperature data would bake corrupted sensor offsets into model weights, permanently ruining the champion model.

**What this would have cost if unnoticed for a week:**
Estimated $42,000 USD across 240 machines due to ~35 false-positive premature maintenance shutdowns and unnecessary replacement of healthy pump bearings.

**How to prevent or detect it faster:**
Add an upstream data contract check asserting hourly mean thermocouple drift relative to ambient factory temperature before data lands in the feature store.
