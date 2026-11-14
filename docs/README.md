# Kasparro AI Visibility Technical Documentation

Welcome to the comprehensive technical documentation for the **Kasparro AI Visibility Analysis & Human Review** platform.

This documentation suite is organized into focused, single-responsibility guides:

| Document | Topic & Focus |
| :--- | :--- |
| **[1. System Architecture](ARCHITECTURE.md)** | High-level system design, relational database schema (8 SQLite tables with ER diagrams), module responsibilities, and key engineering trade-offs. |
| **[2. Scoring & Methodology](SCORING_AND_METHODOLOGY.md)** | Deep dive into Visibility Formula v1, component weights (30/40/20/10), prominence decay math, `null` uncertainty normalization, and statistical denominator integrity. |
| **[3. REST API Reference](API_REFERENCE.md)** | Complete HTTP contract, endpoints (`/datasets`, `/analyses`, `/reports`, `/decision`, `/export`), Bearer token RBAC authentication, and cURL workflow examples. |
| **[4. Human Review & Immutability](HUMAN_REVIEW_LIFECYCLE.md)** | Analyst vs Reviewer workflow, state machine (`DRAFT → SUBMITTED → APPROVED/REJECTED`), cryptographic SHA-256 content hashing, version immutability, and export gate enforcement. |
| **[5. Evaluation & Benchmarks](EVALUATION_AND_BENCHMARKS.md)** | Separate regression and provisional held-out evaluation sets, multi-label metrics, annotation limitations, and reproducible report generation. |
| **[6. P4 Final Analysis Audit](P4_FINAL_ANALYSIS_AUDIT.md)** | End-to-end audit reconciling 150 archived responses, independent aggregate recalculations, verified diagnostics, 7-part remedies, and tier separation. |
| **[7. Engineering Walkthrough](ENGINEERING_WALKTHROUGH.md)** | Reviewer walkthrough mapping the assignment modules and role expectations to implementation, tests, real-model results, limitations and demo commands. |

---

## ⚡ Quick Navigation

* To run the one-click demonstration script:
  ```powershell
  python demo.py
  ```
* To run the complete automated pytest suite (pytest reports the actual test count):
  ```powershell
  pytest -v
  ```
* To run the independent classifier evaluation:
  ```powershell
  python -m evaluation.run_eval
  ```
* To regenerate the JSON and HTML report artifacts from current source data:
  `python tools/regenerate_artifacts.py`
* To explore the generated dashboard:
  Open `evaluation/results/report.html` in any web browser.

