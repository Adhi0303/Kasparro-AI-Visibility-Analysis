# Supplied-response annotation record

## Purpose and scope

This document records the eight supplied archived responses used as the labelled **development/tuning** sample for the provider-classification evaluation. It is not a final unseen benchmark. The labels are manually authored by one project annotator and should be treated as reference labels with known single-annotator limitations.

## Selection

The sample is fixed in `evaluation/cases.jsonl` as `case-001` through `case-008`. It includes:
- All three archived answer engines: ChatGPT, Google AI Mode (`aimode`) and Gemini.
- Vendor shortlisting, unbranded tool discovery, growth-marketing tools, AI visibility measurement, pricing/value and product-capability/limitations contexts.
- Positive Kasparro mention, recommendation, negative characterization, neutral mention and absence.
- Cases with verbatim affirmative evidence excerpts and absence cases with no Kasparro evidence excerpt.

The cases retain their original `response_id` and `prompt_id`. The evaluation runner resolves the answer from `data/responses.jsonl` and the originating prompt from `data/prompts.jsonl`; it must not replace archived content with paraphrases.

## Label semantics

| Label | Positive when | Not sufficient by itself |
|---|---|---|
| `kasparro_mentioned` | The answer body substantively discusses or identifies Kasparro. | The brand appearing only in a prompt echo/recap or source metadata. |
| `kasparro_recommended` | The answer presents Kasparro as a suitable option or endorses it for the stated need. | Mere mention, comparison, or a recommendation directed at a competitor. |
| `kasparro_negative` | The answer makes a negative claim or cautionary characterization about Kasparro. | Neutral uncertainty, missing information, or criticism aimed only at a competitor. |

Recommendation and negative characterization may both be true where the answer endorses Kasparro but includes a meaningful caveat. Recommendation and negative labels imply a substantive mention.

## Case-level annotation rationale

| Case | Engine | Context | Expected mention / recommendation / negative | Rationale |
|---|---|---|---|---|
| case-001 | ChatGPT | Vendor shortlisting | 1 / 0 / 1 | Discusses Kasparro but withholds endorsement because independently verifiable outcome evidence is lacking. |
| case-002 | Google AI Mode | Vendor shortlisting | 1 / 0 / 1 | Explicitly characterizes Kasparro as not widely recognized/top-tier; not an endorsement. |
| case-003 | Gemini | Vendor shortlisting | 1 / 1 / 0 | Presents Kasparro as a viable agency/platform for AI-answer optimization. |
| case-004 | Gemini | Unbranded tool discovery | 0 / 0 / 0 | Recommends other vendors; Kasparro is absent from the answer. |
| case-005 | Google AI Mode | Growth-marketing tools | 0 / 0 / 0 | Names alternatives without discussing Kasparro. |
| case-006 | ChatGPT | AI visibility measurement | 0 / 0 / 0 | General monitoring guidance; no Kasparro discussion. |
| case-007 | ChatGPT | Pricing and value | 1 / 0 / 0 | Disambiguates Kasparro from Kaspr but says evidence is insufficient to judge value; neutral mention. |
| case-008 | Gemini | Product capability and limitations | 1 / 0 / 0 | Uses Kasparro in a balanced discussion of capability versus model non-determinism; neither recommendation nor negative claim. |

The machine-readable annotation object in each supplied case is the source of truth for method, annotator role, label-set version, category and rationale. `expected_evidence` is an exact excerpt from the archived answer for positive discussion/characterization where available; empty evidence arrays are intentional for absence cases.

## Required synthetic edge cases

- `synthetic-001`: prompt-echo-only occurrence must not count as a substantive mention.
- `synthetic-002`: explicit negative characterization and cautionary language must be recognized without incorrectly recommending Kasparro.

These are controlled development regression cases, not supplied observations and not part of the manually labelled supplied-response count.

## Split discipline and limitations

- Tune prompts/rules on the 20-case development set only.
- Keep the 30-case held-out candidate file frozen. Its prompt-family IDs are disjoint from the development set.
- The held-out candidate cases are synthetic and provisionally single-annotated. Use the blinded workflow in `evaluation/annotation_workflow.py`; require a third reviewer for disagreements before calling labels independently adjudicated.
- The current held-out candidate set is not a supplied-response holdout. For a stronger final claim, select a new set of archived supplied responses, manually annotate them without seeing classifier predictions, and freeze that dataset before the final model run.
- The current eight supplied labels are single-annotator development references. Do not overstate inter-annotator reliability or generalization from them.
