# Engineering Walkthrough — Kasparro AI Engineer Assignment

This guide is a reviewer-oriented route through the implementation. It maps the assignment requirements and the AI Software Engineer - 1 role expectations to concrete code, tests and recorded results. It distinguishes the live Gemini run from deterministic replay and does not describe this bounded classifier workflow as an autonomous multi-agent system.

## 1. Scope and acceptance criteria

The assignment asks for a runnable backend that accounts for 50 prompts, 150 archived answers and 2,439 citation occurrences; classifies brand visibility; calculates transparent scores; produces three evidence-backed diagnostics and three prioritised remedies; and enforces human approval before export.

The implementation uses Python, FastAPI, Pydantic and SQLite. Dashboard rendering and additional hardening support reviewability, but the core acceptance criteria remain the backend, evidence, evaluation and review lifecycle.

## 2. System walkthrough

1. **Input integrity:** `python tools/check_pack.py` validates the supplied pack manifest, checksums and relationships.
2. **Persistence:** `app/ingestion.py` validates and imports prompt, response and citation records into the SQLite schema. Re-import handling is covered by ingestion tests.
3. **Execution routing:** `app/classification.py` selects the configured classifier. Replay is the default and is deterministic. Real-model execution routes through `app/llm/provider.py`, which calls an OpenAI-compatible chat-completions endpoint (the recorded run used Gemini).
4. **Structured output:** The provider response is validated against the Pydantic classification contract. Invalid/inconsistent output and provider failures remain explicit failures; bounded retry and timeout behavior is tested.
5. **Evidence integrity:** Candidate quotations are checked centrally against the archived source response. Exact source excerpts and offsets are retained; fabricated, altered, unsupported-location and mismatched-offset evidence are rejected.
6. **Scoring and reporting:** Deterministic application code computes scores and aggregates. Diagnostics and remedies link back to response IDs and excerpts; JSON and HTML artifacts are generated from the report data.
7. **Human review:** Analyst and reviewer permissions are enforced server-side. Draft submission freezes a version; approval/rejection is recorded; export is gated on the approved immutable version. Editing after approval creates a new draft requiring review.

## 3. Commands for a reviewer walkthrough

From the repository root, after installing dependencies and creating a local `.env` from `.env.example`:

```powershell
python tools/check_pack.py
pytest -v
python demo.py
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the generated API contract. The README contains the end-to-end request examples for import, analyse, create/edit report, submit, approve/reject and export.

For the real-model adapter, configure a permitted provider key locally and run the one-request smoke test before the regression evaluation:

```powershell
python -m evaluation.provider_smoke_test
python -m evaluation.run_eval --mode real_model --split regression
python -m evaluation.repeatability --split regression --repeats 3
```

Replay commands and the held-out replay command are documented in the README and `docs/EVALUATION_AND_BENCHMARKS.md`. The held-out result currently in the repository is deterministic replay, not a live Gemini held-out evaluation.

## 4. Evaluation results and their boundaries

### Live Gemini regression run

- Cases: 20 total (8 supplied reference cases and 12 synthetic cases).
- Successful calls: 18; failed calls: 2; execution coverage: 90.0%.
- Exact-match agreement on successful calls: 13/18 = 72.2%.
- Rule-based baseline on the same successful subset: 8/18 = 44.4%.
- Matched-subset improvement: +27.8 percentage points.
- Coverage-adjusted exact-match agreement: 13/20 = 65.0%.
- Both failed calls were HTTP 429 quota failures. They remain visible in the denominator for coverage-adjusted agreement.

The supplied regression labels are development reference labels, not an independently adjudicated held-out benchmark. The high recommendation F1 is based on only two positive examples and should be interpreted cautiously.

### Repeatability

The three-repeat study contains 60 calls: 54 successful and 6 failed (90.0% call coverage). Eighteen cases had at least two successful runs; 16 of those were exactly stable (88.89% stability among repeatable cases). Mean client-observed latency was 2.97 seconds, median 2.13 seconds and P95 6.70 seconds. These are observed request timings, not a billing or provider-side latency guarantee.

### Held-out replay

The held-out artifact contains 30 synthetic cases executed with `deterministic_replay` / `contextual-rules-v1`. Its 63.3% agreement is a replay-rule result; it must not be presented as Gemini live-model accuracy. The held-out labels are provisional single-annotator labels.

## 5. Failure, diagnosis and verified correction

During development, diagnostic evidence included paraphrased text rather than exact excerpts from archived answers. The fix centralised source-text matching and offset validation, rejected unsupported or altered evidence, and added regression coverage including `test_all_diagnostic_evidence_verbatim_integrity` and adversarial evidence tests. The P3 audit records 6/6 final diagnostic evidence excerpts as exact matches, with no invalid response IDs or offset mismatches.

The live Gemini run also exposed quota failures (HTTP 429) and a prompt-echo false positive on `synthetic-001`. The quota failures are reported as execution failures; the synthetic false positive remains a model-quality limitation rather than being hidden or relabelled as a successful match.

## 6. Fit to the AI Software Engineer - 1 role

| Role expectation | Demonstrated in this project |
|---|---|
| Written specifications and acceptance criteria | Assignment-driven scope, evaluation cases, explicit workflow and test coverage |
| Python, REST APIs and output schemas | FastAPI endpoints, Pydantic request/classification contracts |
| LLM integration and prompting | Gemini/OpenAI-compatible provider adapter, constrained structured response prompt |
| Reliability | Timeouts, bounded retries, failure statuses, malformed-output validation |
| Evaluation and experiments | Rule-based baseline, regression/held-out split, per-label metrics and repeatability |
| Evidence extraction and verification | Source-grounded excerpts, response IDs, offsets and rejection of invalid evidence |
| Human review and permissions | Analyst/reviewer roles, immutable report versions and approval-gated export |
| Data and reproducibility | SQLite persistence, pack checksums, deterministic replay and documented commands |
| Coding-agent workflow | AI-assisted development is disclosed; generated changes were reviewed and verified with tests |

**Scope boundary:** This assignment implements a bounded LLM-backed classification and evidence-validation workflow, not a free-running autonomous agent with external tool orchestration. Google ADK, LangGraph, Langfuse, Docker and cloud deployment were not required by the assignment and are not claimed as implemented here.

## 7. Final verification record

The final local verification report for commit `121544c` records:

- `pytest -v`: 122 passed, 1 skipped, 0 failed.
- `python tools/check_pack.py`: 50 prompts, 150 responses and 2,439 citation entries validated with zero errors.
- `git diff --check`: clean.
- Working tree: clean and pushed to `origin/main`.

The final documentation-only PR corrects the provider-metric references and clarifies AI-assistance and local-token disclosures. Its own branch diff should be reviewed before merge; no new test execution is claimed for that PR unless run against the PR head.
