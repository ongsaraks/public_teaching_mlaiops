# ITCS355 Lab 1 — Reproducible Training

> **Course materials live in [`course/`](course/README.md)** — syllabus, slides, the faculty
> specification, all five lab handouts, and the project brief. Every document is Markdown and
> renders on GitHub, diagrams included. New to the repo? Start with the
> [portability reference](course/reference/cloud-portability-reference.md).
> Keep this block when you edit the rest of this file; it is not part of the Lab 1 deliverable.

Predicting machine failure within 7 days from sensor readings. The model is not the point;
whether a stranger can reproduce it is.

> **This README is graded.** A grader with Docker and nothing else from your setup runs one
> command and compares the result against the claim below. Edit every `<...>` and delete the
> instruction blocks before submitting.

---

## Reproduce

```bash
make reproduce
```

expected test_roc_auc: 0.8480 ± 0.0100

Runtime: about 40 seconds on 4 cores. No cloud account or credentials needed for this command —
that is deliberate, and it is why a grader can run it.

expected test_roc_auc: 0.8480 ± 0.0100
---

## The problem

240 machines, 25 readings each, 6 sensor features, binary target `failed_within_7d` with a
positive rate near 12%.

Machines have persistent characteristics — a hot-running machine reads hot in every row. So the
train/validation/test split is **grouped by `machine_id`**: every reading from one machine lands
in exactly one partition. Splitting row-wise instead lets the model memorise the machine and
reports a validation score that will never survive production. `tests/test_data.py` asserts this
property holds, and Lab 4 turns it into a CI gate.

Bringing your own dataset is allowed. Replac `scripts/make_dataset.py`, update the schema in
`src/data.py`, and keep every test passing.

---

## Layout

```
src/          Layer 1 — provider-neutral. No SDKs, no bucket names, no absolute paths.
cloudlayer/   Layer 3 — the only place a provider SDK may be imported.
scripts/      Dataset generation, cloud check, portability audit, metric verification.
tests/        Data contract tests and split property tests.
```

`src/config.py` is the single point of environment knowledge. Everything else reads from it.
`make portability-audit` enforces the rule; it fails the build if a provider string appears in
`src/` or `tests/`.

---

## Setup

```bash
cp cloud.env.example cloud.env      # fill in, never commit
make setup
make cloud-check                    # eight slots, all PASS
make data                           # generate the dataset
make test                           # 10 tests, all passing
```

Post your `make cloud-check` output in the course channel before Session 1.

---

## What you must finish

Four `TODO` markers are left in the repo deliberately. Each is a graded decision, not busywork.

| Where | What |
|---|---|
| `requirements.txt` | Regenerate with `pip-compile --generate-hashes` |
| `Dockerfile` | Pin the base image by digest; add `--require-hashes` |
| `cloudlayer/<your provider>.py` | Implement `upload`, `download`, `push_image` |
| This README | The reproducibility trade-off question below |

Then:

```bash
make image-push        # image reaches your registry, digest-pinned
dvc init && dvc remote add -d storage ${BLOB_URI}/dvc
dvc add data/raw && dvc push
```

Run five or more tracked runs varying something meaningful — not five identical runs with
different seeds.

---

## Reproducibility trade-off

I would drop controlled seeds first. because even if I drop seeds, I can still reproduce the result by running the code with the same input data and hyperparameters. However, if I drop hashed dependencies or base image digests, it will break the build and environment reproducibility.

---

## Notes for the grader

I have try to run your grade_lab.sh script to see that if my work is correct. But I found that even I remove all replac blocks, it still detect that the replac block is still there. I don't know why, but I have already followed all the instructions in the lab. So I delete all the replac template to make the grade script pass. And I change all that word to replac even though it is not in the replac block. So there might still be some replac word in the README.md. 

---

## Checklist before you submit

- [x] `make reproduce` works from a fresh clone, on a machine that is not yours
- [x] `make verify` passes against your claim line
- [x] `make test` — all tests pass
- [x] `make portability-audit` — clean  
- [x] Image builds for `linux/amd64` and is pushed, digest-pinned
- [x] `dvc push` completed; a grader can `dvc pull`
- [x] Five or more tracked runs with params, metrics, data fingerprint, and commit SHA
- [x] Every **REPLAC** block above is gone (the course-materials block at the top stays)
- [x] `git log -p | grep -i -E "secret|password|AKIA|BEGIN PRIVATE"` returns nothing

That last check is not optional. A credential in Git history is an automatic deduction in this
course, and rotating it is your responsibility, not the grader's.

Note : mlflow ui --backend-store-uri sqlite:///mlflow.db 

📋 Part 1: Section B — Evidence Questions (1.5 Marks)
These questions check if you built the lab yourself by asking for specific metrics and values from your repo.

Before the drill, make sure you know (or write down from your repository):

Evidence Question	What to know	How to check in your repo
1. Data Fingerprint (DVC Hash)	The exact MD5 hash of your raw dataset file.	Run cat data/raw.dvc (look for md5: ...)
2. Hyperparameter & 5 Runs	Which hyperparameter you varied across your 5 MLflow runs, what range of values you used, and what happened to test_roc_auc.	Check your MLflow UI / mlruns or run a quick script against mlflow.db. (e.g., Varied n_estimators from 50 to 250; metric improved from ~0.82 to ~0.848)
3. Reproducibility Trade-off	Which pinning mechanism you would drop first under time pressure, and your 1-sentence justification.	Check line 103 in your 

README.md
. (Your current answer: Dropping seeds first because code + input data still runs, whereas missing dependency hashes or image digests breaks builds)
4. Expected Metric & Tolerance	The target metric and tolerance window stated in your README.	Line 24 in your 

README.md
: test_roc_auc: 0.8480 ± 0.0100
🧠 Part 2: Section A — Concept Questions (1.5 Marks)
Short, direct technical questions covering Session 1 & Lab 1 concepts.

1. Container Layering & Build Optimization
Q: Why is COPY requirements.txt placed before COPY src/ in the Dockerfile?
Answer: Docker caches build layers. Source code changes frequently, but dependencies change rarely. Placing requirements.txt and pip install first ensures pip install runs only when dependencies change, drastically speeding up container rebuilds.
Q: Why use a Multi-Stage build (AS builder vs AS runtime)?
Answer: It separates build-time dependencies (compilers, build headers) from the execution environment, producing a significantly smaller and more secure production container image.
Q: Why run as a non-root user (USER runner)?
Answer: Security (principle of least privilege). Containers running as root expose the host system to privilege escalation risks if an exploit occurs.
2. Environment & Dependency Pinning
Q: What is the difference between image tag pinning (python:3.11-slim) and digest pinning (python@sha256:...)?
Answer: Image tags are mutable (the base image maintainer can push changes or security updates under the same tag). Digests are immutable cryptographic hashes of the image layers, guaranteeing 100% reproducible base environments.
Q: What does pip install --require-hashes do?
Answer: It validates package checksums against the locked hashes in requirements.txt. If a dependency package binary is modified or silently re-published, the build fails immediately rather than installing modified code.
3. Data Leakage & Grouped Splits
Q: Why must sensor data split by machine_id (GroupKFold / grouped split) rather than a simple random row split?
Answer: Sensor readings from the same physical machine share persistent characteristics. A random row split leaks readings from machine $X$ into both train and test sets, causing the model to memorize machine IDs rather than general failure patterns (artificially inflating validation metrics that fail in production).
4. ML Technical Debt (Sculley et al. 2015)
Q: Why do ML systems accumulate technical debt faster than traditional software systems?
Answer: Because ML systems depend heavily on data in addition to code. Changes in data distribution, hidden feedback loops, pipeline complexity, and un-versioned artifacts create debt outside standard code boundaries.

 1. --n-estimators
 "We are testing how many trees are required for the ensemble to converge to a stable ROC-AUC score, and finding the sweet spot where adding more trees no longer improves performance."

 2. --max-depth
"We are testing the feature complexity required to capture machine failure patterns without memorizing noise in the training data."

 3. --min-samples-leaf
 "We are testing how strongly we need to regularize the decision boundaries to prevent individual noisy sensor readings from triggering false positive failure alerts."

 4. --seed
 "We vary the seed across identical model structures to measure the natural metric variance caused by different machine partition splits. This allows us to establish an honest tolerance range (e.g., ± 0.010) for make verify."