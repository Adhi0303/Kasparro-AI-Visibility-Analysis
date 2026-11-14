# Kasparro AI Visibility Technical Documentation

Welcome to the comprehensive technical documentation for the **Kasparro AI Visibility Analysis & Human Review** platform.

This documentation suite is organized into focused, single-responsibility guides:

| Document | Topic & Focus |
| :--- | :--- |
| **[1. System Architecture](ARCHITECTURE.md)** | High-level system design, relational database schema (8 SQLite tables with ER diagrams), module responsibilities, and key engineering trade-offs. |
| **[2. Scoring & Methodology](SCORING_AND_METHODOLOGY.md)** | Deep dive into Visibility Formula v1, component weights (30/40/20/10), prominence decay math, `null` uncertainty normalization, and statistical denominator integrity. |
| **[3. REST API Reference](API_REFERENCE.md)** | Complete HTTP contract, endpoints (`/datasets`, `/analyses`, `/reports`, `/decision`, `/export`), Bearer token RBAC authentication, and cURL workflow examples. |
| **[4. Human Review & Immutability](HUMAN_REVIEW_LIFECYCLE.md)** | Analyst vs Reviewer workflow, state machine (`DRAFT → SUBMITTED → APPROVED/REJECTED`), cryptographic SHA-256 content hashing, version immutability, and export gate enforcement. |
| **[5. Evaluation & Benchmarks](EVALUATION_AND_BENCHMARKS.md)** | Regression and held-out evaluation, replay baseline comparison, generated evidence-backed diagnostics, report synchronization and artifact validation. |

---

## ⚡ Quick Navigation

* To run the one-click demonstration script:
  ```powershell
  python demo.py
  ```
* To run the complete automated pytest suite (test count is reported by the runner):
  ```powershell
  pytest -v
  ```
* To run the regression and held-out classifier evaluations:
  ```powershell
  python -m evaluation.run_eval --mode replay --split regression
  python -m evaluation.run_eval --mode replay --split held_out
  ```
* To regenerate and validate the JSON, Markdown and HTML report artifacts:
  ```powershell
  python tools/regenerate_artifacts.py
  python tools/validate_artifacts.py
  ```
* To explore the interactive visual dashboard:
  Open `evaluation/results/report.html` in any web browser.

