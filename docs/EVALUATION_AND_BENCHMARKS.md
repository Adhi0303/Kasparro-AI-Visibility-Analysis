# Evaluation Framework, Methodology & Benchmark Results

## 1. Evaluation design

The project keeps a development/regression set separate from a frozen held-out candidate set. Split definitions and limitations are recorded in `evaluation/split_manifest.json`.

- **Regression split:** `evaluation/cases.jsonl` contains the 20 existing supplied and synthetic cases. It may be used during implementation and rule development.
- **Held-out candidate split:** `evaluation/held_out_cases.jsonl` contains 30 additional synthetic scenarios with prompt-family IDs disjoint from the regression set. Do not tune classifier rules against this set.
- **Annotation limitation:** The 30 held-out labels are provisional single-annotator labels. They are not independently double-annotated or adjudicated. They provide a separate leakage-control check, but must not be presented as an independently validated benchmark until a human reviewer independently labels them and disagreements are resolved.

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

Metrics are calculated only for successful classifier responses. Failed provider cases are reported separately and must not silently count as correct predictions.

## 4. Leakage and annotation policy

- Keep the regression and held-out files separate.
- The test suite checks that their prompt-family IDs do not overlap and that held-out case IDs are unique.
- Do not inspect held-out errors and then modify classifier rules before reporting the same held-out score as final. If the held-out set is used for development, retire it and create a new unseen test set.
- Independently annotate the held-out cases (preferably two reviewers), record disagreements and adjudicate labels before describing the set as independent ground truth.
- Preserve the original labels and record any adjudicated correction with a rationale; do not silently overwrite labels based on model output.
- Report each split's sample count and per-label support alongside all metrics.

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
