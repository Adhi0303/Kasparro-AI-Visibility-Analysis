# P2 Local Validation Audit — 2026-11-14

## Scope

This note records an audit of the local evaluation artifacts generated on 2026-11-14. It is an observation snapshot, not a claim that the model is production-ready or that the labels are independently validated.

Artifacts reviewed:
- `evaluation/results/eval_provider_results.json`
- `evaluation/results/eval_provider_report.md`
- `evaluation/results/eval_held_out_results.json`
- `evaluation/results/repeatability_regression.json`

Provider: Gemini OpenAI-compatible endpoint  
Model: `gemini-3.5-flash-lite`  
Classifier version: `v1`

## 1. Live provider regression run

The provider result and Markdown report agree on the same run:

| Measure | Observed result |
|---|---:|
| Regression cases | 20 |
| Successful calls | 18 |
| Failed calls | 2 |
| Execution coverage | 90.0% |
| Exact matches on successful calls | 13 / 18 (72.22%) |
| Coverage-adjusted exact-match agreement | 13 / 20 (65.0%) |

The two failed cases were `synthetic-009` and `synthetic-011`. Both report HTTP 429 quota errors after three attempts. These are execution failures, not classification predictions, and are excluded from matched-subset classification metrics while remaining visible in coverage-adjusted agreement.

Matched-subset per-label results:

| Label | Baseline F1 | Gemini F1 | Positive support |
|---|---:|---:|---:|
| Mention | 0.9286 | 0.9286 | 13 |
| Recommendation | 0.4444 | 1.0000 | 2 |
| Negative | 0.4444 | 0.6667 | 5 |

The recommendation F1 is based on only two positive examples in the successful subset. Treat it as an encouraging but highly preliminary result, not a general performance guarantee.

### Required edge-case observations

- `synthetic-001` (prompt-echo-only brand occurrence): expected mention=false; Gemini predicted mention=true. This is a genuine classification error and shows that this required edge case is not yet solved by the live provider classifier.
- `synthetic-002` (explicit negative characterization): Gemini matched all three expected labels in this run.

## 2. Three-repeat live provider study

| Measure | Observed result |
|---|---:|
| Cases | 20 |
| Repeats per case | 3 |
| Total calls | 60 |
| Successful calls | 54 |
| Failed calls | 6 |
| Call coverage | 90.0% |
| Cases with at least two successful calls | 18 |
| Stable cases among those 18 | 16 |
| Conditional stability | 88.89% |

Latency (client-observed):
- Mean: 2.9654 seconds
- Median: 2.1269 seconds
- P95: 6.6953 seconds

Two cases had fewer than two successful calls and therefore could not be assessed for repeatability. Two cases with enough successful calls showed prediction variation:
- `synthetic-004`: recommendation varied across repeats.
- `synthetic-007`: negative characterization varied across repeats.

The 88.89% figure is stability conditional on having at least two successful calls. It is not the overall success rate; call coverage was 90.0%. The six failed calls were quota-related HTTP 429 errors.

## 3. Held-out candidate replay

The uploaded held-out artifact is a deterministic replay run, not a live Gemini evaluation.

| Metadata | Value |
|---|---|
| Cases | 30 synthetic |
| Execution mode | `replay` |
| Provider | `deterministic_replay` |
| Model | `contextual-rules-v1` |
| Successful evaluations | 30 / 30 |
| Baseline exact-match agreement | 46.67% |
| Replay exact-match agreement | 63.33% |

The held-out file marks its labels as `provisional_single_annotator`. Therefore, this result is a diagnostic replay result on a synthetic candidate set, not independently adjudicated ground truth and not evidence of Gemini's held-out performance.

## 4. Annotation provenance and benchmark limitations

The eight supplied regression reference-label tuples predate the P2 documentation work. The repository does not record the original annotator identity, annotation date, or independent review process. Added rationales and metadata do not retroactively establish provenance. Keep their status as pre-existing development reference labels with unverified provenance until the original process is confirmed or the cases are relabelled through a blinded workflow.

The 30 held-out cases are synthetic and currently provisional single-annotator labels. A stronger external-validity benchmark still requires a separately selected supplied-response holdout, blinded independent annotation, and adjudication of disagreements.

## 5. Audit conclusions and follow-up

P2 evidence demonstrates that:
- The live Gemini adapter executes and returns structured classifications.
- The evaluation reports matched-subset quality metrics separately from execution coverage.
- Provider failures are recorded rather than silently treated as predictions.
- Repeatability, latency, and per-repeat metrics are captured.
- The held-out replay split is kept distinct from live provider evaluation.

Remaining follow-up:
1. Resolve Gemini quota/rate-limit constraints before attempting another full live run; use controlled request pacing rather than rapid retries.
2. Investigate and fix the live false positive on `synthetic-001`, then rerun the regression evaluation.
3. Investigate prediction variation on `synthetic-004` and `synthetic-007`.
4. Verify or redo the provenance of the eight supplied reference labels.
5. Complete blinded double annotation and adjudication for the held-out set; create a new unseen supplied-response holdout for a stronger final claim.
6. When reporting this run, use 18/20 successful calls, 72.22% matched-subset agreement, and 65.0% coverage-adjusted agreement. Do not substitute the different 19/20 result from an earlier run.

## Overall assessment

P2's evaluation instrumentation and reporting are substantially in place. The uploaded run provides useful initial live-provider evidence, but quota-limited coverage, the prompt-echo false positive, observed repeat variation, and unverified annotation provenance mean the benchmark should be described as an initial validation—not a fully closed or independently validated evaluation.
