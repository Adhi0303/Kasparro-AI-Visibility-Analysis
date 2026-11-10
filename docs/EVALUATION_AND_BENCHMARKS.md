# Evaluation Framework, Methodology & Benchmark Results

## 1. Classification & Evaluation Methodology

The project separates deterministic offline replay from configured live provider inference. The checked-in benchmark is intended for **regression testing**, not as a statistically representative or held-out estimate of real-world performance.

### Execution Mode Separation
1. **Deterministic Replay (`execution_mode="replay"`, default):** Keyless contextual rules in `app/llm/replay.py`. This verifies deterministic behavior and known edge cases; it is not live LLM reasoning.
2. **Real-Model Provider (`execution_mode="real_model"`):** `app/llm/provider.py` calls an OpenAI-compatible chat-completions endpoint. The adapter validates strict response types and cross-field label consistency, retries selected transient HTTP/transport failures with bounded backoff, and leaves evidence verification to the centralized source-audit pipeline. Compatibility depends on the endpoint supporting `choices[0].message.content` and JSON-object response mode.

### Checked-in Regression Cases
The current case file contains 20 labeled examples (8 supplied and 12 synthetic). Synthetic examples target known regressions such as prompt echo, competitor attribution, negation and pronoun scope. These examples are useful for repeatable regression checks, but the sample is too small and partly hand-authored; it must not be treated as an independent held-out test set.

### Metrics
The grader reports per-label support, positive/negative support, confusion counts (TP/FP/TN/FN), precision, recall, specificity, accuracy, balanced accuracy and F1, plus exact-match agreement across the three labels. The grader rejects mismatched prediction lengths and non-boolean labels instead of silently truncating or coercing them.

## 2. Interpreting Results Correctly

Run the deterministic regression suite:

```bash
python -m evaluation.run_eval --mode replay
```

Run a separate provider evaluation only when a compatible endpoint and credentials are configured:

```bash
python -m evaluation.run_eval --mode real_model
```

Replay and provider outputs are written to separate files. Provider results are not interchangeable with replay results. A 100% result on the 20 checked-in cases means only that the implementation matched those 20 labels in that run; it does not establish generalization to unseen customer data, other brands, languages, industries or model families.

### Required next step for a statistically meaningful benchmark

Before making broad accuracy claims, build a larger independently annotated corpus and freeze a held-out test set. Split by source response/prompt family (not randomly by near-duplicate rows) to reduce leakage. Have labels reviewed independently, record disagreements and adjudication, and publish per-class support and confusion matrices for each split. Do not tune replay rules against the held-out set.

## 3. Evidence and Source Traceability

Classifier-proposed evidence is treated as untrusted input. The analysis coordinator verifies every candidate against the original answer text and records accepted and rejected evidence, including source offsets and rejection reasons. Report creation, editing and export repeat source validation before rendering diagnostics. A provider response with invalid evidence does not gain credibility merely because its JSON schema passed.

## 4. Historical Dataset Findings

The archived dataset contains 50 prompts, 150 captured responses and 2,439 citation records from the 31 July 2026 snapshot. Findings in the executive report describe that historical capture only. They should not be interpreted as live model rankings or current brand visibility.

## 5. Limitations

- The checked-in labeled set is small and not an independent held-out benchmark.
- Replay is deterministic rule-based logic; it is not an LLM and cannot guarantee semantic understanding beyond implemented rules.
- Live provider quality depends on the selected model, endpoint, model version, prompt, provider behavior and credentials. No live provider quality claim should be made without recording an actual run.
- Citation presence does not establish that the cited page supports the associated model claim without inspecting the page.
- A single historical capture cannot establish trends or current visibility.
