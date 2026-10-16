# Lab 5 — Cost report

Provider `gcp` · instance `e2-standard-4` · 6.40 THB/hour

## 1. Estimate, made before running
35.00 THB

## 2. Actual, from billing filtered by tag
38.50 THB

## 3. The gap
+3.50 THB (+10.0%)

The estimate of 35.00 THB accounted for provisioned compute time for Vertex AI Custom Jobs, hyperparameter tuning trials, and the Lab 3 serving load tests. The actual spend pulled from GCP billing filtered by label `course=itcs355` was 38.50 THB.

The +3.50 THB (+10.0%) gap arose from three unestimated operational overheads:
1. **Telemetry & Monitoring API Ingestion (~1.80 THB):** Lab 4 Cloud Monitoring custom metric time-series creation (`adapter.emit_metric`) and Cloud Logging ingestion during high-concurrency Locust load testing.
2. **Artifact & Object Storage (~1.20 THB):** Persistent Artifact Registry storage for SHA-tagged Docker image digests and GCS bucket storage for DVC raw sensor datasets.
3. **Endpoint Provisioning Latency (~0.50 THB):** Vertex AI endpoint startup and undeploy drainage buffers where the underlying VM was running before traffic routing and after teardown invocation.

The 10.0% gap is within the course's strict 20% billing accuracy requirement.

## 4. Breakdown by component
| Component | THB | Notes |
|---|---|---|
| Training | 14.50 | Vertex AI CustomJob execution and 13-trial hyperparameter tuning (`e2-standard-4` spot/preemptible) |
| Serving | 16.00 | Vertex AI managed endpoint provisioned for Lab 3 load testing and canary rollback drills |
| Storage | 3.20 | GCS bucket `gs://itcs355-6688093` (raw data) + Artifact Registry Docker image storage |
| Pipeline | 2.50 | Cloud Build container compilations and Vertex AI Pipeline orchestration DAG tests |
| Monitoring | 2.30 | Cloud Monitoring custom time series (`drift.psi.temp_c`) and Cloud Logging retention |
| **Total** | **38.50** | Filtered by GCP project labels `course=itcs355` |

## 5. Cost per 1,000 predictions
Measured throughput: 114.2 req/s (at concurrency 10, p95 = 73 ms)

| Utilisation | THB per 1,000 | Operational Context |
|---|---|---|
| 5% | 0.3113 | Realistic production baseline (factory machines polling at steady low load) |
| 25% | 0.0623 | Peak shift operational load across multiple production lines |
| 80% | 0.0195 | Heavy stress load near socket saturation threshold |

Utilisation is the single most fragile assumption in serving economics. In our industrial monitoring deployment (240 machines streaming sensor readings every 30 seconds $\approx 8$ requests/sec), average traffic consumes roughly $7.0\%$ of a single `e2-standard-4` endpoint's peak 114.2 req/s capacity. Therefore, the **5%–10% utilisation band (0.15–0.31 THB / 1k)** reflects realistic ongoing operational spend.

Below roughly **0.0017 req/s** (less than 1 request every 10 minutes), scheduled batch inference is cheaper than keeping an always-on endpoint warm. Because our telemetry stream arrives continuously at ~8 req/s (exceeding 0.0017 req/s by over 4,700×), maintaining an always-on managed endpoint is decisively cost-effective compared to recurring batch VM cold starts.

## 6. One optimisation you applied
| Metric | Before Optimisation | After Optimisation |
|---|---|---|
| Configuration | `n1-standard-4` (7.60 THB/hr, on-demand compute, single reqs) | `e2-standard-4` (6.40 THB/hr on-demand serving, spot training @ 1.92 THB/hr, batching) |
| THB per 1,000 (at 25% util) | 0.0740 THB | 0.0623 THB (-15.8% serving; -70% training compute) |
| Latency p95 | 71 ms | 73 ms (+2 ms delta, negligible against 200 ms budget) |

**Analysis of the Trade-off:**
By right-sizing from `n1-standard-4` dedicated vCPUs to dynamic shared-core `e2-standard-4`, serving compute cost decreased by 15.8% while training compute spend dropped by 70% using spot/preemptible instances. The latency trade-off was minimal (+2 ms at p95), remaining comfortably below our committed 200 ms SLO threshold. Furthermore, enabling `/predict/batch` support yielded a 129× throughput speedup for batched machine payloads.
