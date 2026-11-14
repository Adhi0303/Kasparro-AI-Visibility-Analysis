# Evaluation Framework, Methodology & Benchmark Results

## 1. Evaluation design

The project keeps a development/regression set separate from a frozen held-out candidate set. Split definitions and limitations are recorded in `evaluation/split_manifest.json`.

- **Regression split:** `evaluation/cases.jsonl` contains the 20 existing supplied and synthetic cases. It may be used during implementation and rule development.
- **Held-out candidate split:** `evaluation/held_out_cases.jsonl` contains 30 additional synthetic scenarios with prompt-family IDs disjoint from the regression set. Do not tune classifier rules against this set.
- **Annotation limitation:** The 30 held-out labels in the repository are still provisional single-annotator labels. They are not independently double-annotated or adjudicated and must not be presented as independently validated ground truth.
- **Execution reliability:** Classifier quality metrics are reported on successful calls, while execution coverage and coverage-adjusted exact-match agreement use the full cohort so failed calls cannot disappear from the operational result.

### Independent annotation workflow

Create two separately shuffled reviewer packets. The packets include the case context but omit provisional labels, source notes and model predictions:

```bash
python -m evaluation.annotation_workflow export --reviewer-a reviewer_a --reviewer-b reviewer_b
```

Have two distinct reviewers label every case independently by filling the `labels` booleans and, where useful, the rationale in their respective JSONL files under `evaluation/annotations/`. Do not show reviewers classifier output or the provisional `expected` field.

Reconcile the two submissions:

```bash
python -m evaluation.annotation_workflow finalize \
  --reviewer-a evaluation/annotations/reviewer_a.jsonl \
  --reviewer-b evaluation/annotations/reviewer_b.jsonl
```

If any labels disagree, finalization writes `evaluation/annotations/adjudication_required.jsonl` and stops without creating a finalized benchmark file. A third reviewer must fill the adjudicator ID, final booleans and a rationale for every disputed case. Then rerun the command with `--adjudication evaluation/annotations/adjudication_required.jsonl`. The output `evaluation/held_out_adjudicated_cases.jsonl` preserves the original provisional labels, both reviewer decisions and any adjudication record.

Run evaluation with the adjudicated labels only after that process succeeds:

```bash
python -m evaluation.run_eval --mode replay --split held_out \
  --cases-path evaluation/held_out_adjudicated_cases.jsonl
```

Run regression evaluation:

```bash
python -m evaluation.run_eval --mode replay --split regression
```

Run the frozen held-out candidate evaluation:

```bash
python -m evaluation.run_eval --mode replay --split held_out
```

The outputs are written to separate files for each execution mode and split (for example, `eval_results.json` and `eval_held_out_results.json`). Replay and provider runs are not interchangeable. A high score on synthetic cases does not establish real-world generalization.

## 2. Execution modes

1. **Deterministic Replay (`execution_mode="replay"`):** Keyless contextual rules in `app/llm/replay.py`. It verifies deterministic behavior; it is not live LLM reasoning.
2. **Real-Model Provider (`execution_mode="real_model"`):** `app/llm/provider.py` calls an OpenAI-compatible chat-completions endpoint. It validates strict response types and cross-field label consistency, retries selected transient HTTP/transport failures with bounded backoff, and leaves evidence verification to the centralized source-audit pipeline. Compatibility depends on the endpoint supporting `choices[0].message.content` and JSON-object response mode.

Example provider evaluation on the held-out candidate set (requires configured credentials and compatible endpoint):

```bash
python -m evaluation.run_eval --mode real_model --split held_out
```

## 3. Metrics

The grader reports, per label:
- Support, positive support and negative support
- True positives, false positives, true negatives and false negatives
- Precision, recall, specificity, accuracy, balanced accuracy and F1
- Exact-match agreement across mention, recommendation and negative labels

Per-label precision, recall, F1 and matched-subset exact-match agreement are calculated only for successful classifier responses. The report separately shows the all-case baseline, classifier execution coverage, and coverage-adjusted exact-match agreement. The coverage-adjusted rate divides successful exact matches by the full case count, so every failed classifier call remains visible in the operational denominator.

## 4. Leakage and annotation policy

- Keep the regression and held-out files separate.
- The test suite checks that their prompt-family IDs do not overlap and that held-out case IDs are unique.
- Do not inspect held-out errors and then modify classifier rules before reporting the same held-out score as final. If the held-out set is used for development, retire it and create a new unseen test set.
- Independently annotate the held-out cases with two distinct reviewers, record raw agreement and per-label Cohen's kappa, and require a third reviewer to adjudicate every disagreement before describing the set as independent ground truth.
- Use `evaluation.annotation_workflow` to generate blinded packets and validate complete reviewer coverage. The tool refuses duplicate reviewer identities, missing/extra case IDs, invalid label types, and unresolved disagreements.
- Preserve the provisional labels and both independent submissions in the adjudicated output; record every adjudication with a third reviewer ID and rationale. Never alter labels in response to model predictions.
- Report each split's sample count, per-label support, execution coverage and coverage-adjusted exact-match agreement alongside quality metrics.

## 5. Evidence and source traceability

Classifier-proposed evidence is untrusted input. The analysis coordinator verifies candidates against original answer text and records accepted and rejected evidence, including source offsets and rejection reasons. Report creation, editing and export repeat source validation before rendering diagnostics.

## 6. Historical dataset findings

The archived dataset contains 50 prompts, 150 captured responses and 2,439 citation records from the 31 July 2026 snapshot. Findings in historical reports describe that capture only; they are not live model rankings or current brand visibility.

## 7. Limitations

- The held-out candidate set is synthetic and its labels are provisional single-annotator labels; independent human annotation is still required.
- Replay is deterministic rule-based logic and cannot guarantee semantic understanding beyond implemented rules.
- Live provider quality depends on model, endpoint, version, prompt and provider behavior. No live-provider quality claim should be made without a recorded successful run.
- Citation presence does not establish that a cited page supports the associated claim without inspecting the page.
- A single historical capture cannot establish trends or current visibility.
