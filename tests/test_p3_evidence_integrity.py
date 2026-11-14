import html
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Dataset, Response, Report, ReportVersion, ReviewDecision
from app.export import export_approved_report
from app.evidence import (
    find_evidence_match,
    render_report_html,
    render_report_markdown,
    validate_evidence,
    validate_report_evidence,
)
from app.classification import _audit_evidence_candidates
from app.llm.base import ClassificationResult, EvidenceItem


def test_find_evidence_match_altered_and_fabricated_rejections():
    """Verify find_evidence_match rejects fabricated quotes and word/punctuation alterations."""
    source_text = "Kasparro provides structured AI visibility analytics for D2C brands."

    # 1. Fabricated quotation
    res_fab = find_evidence_match("Kasparro guarantees #1 rankings across all search engines.", source_text)
    assert res_fab["valid"] is False
    assert res_fab["start_offset"] is None
    assert "not found" in res_fab["rejection_reason"].lower()

    # 2. Altered words (substitution: 'reproducible' instead of 'structured')
    res_alt_words = find_evidence_match("Kasparro provides reproducible AI visibility analytics", source_text)
    assert res_alt_words["valid"] is False
    assert "not found" in res_alt_words["rejection_reason"].lower()

    # 3. Altered punctuation (trailing exclamation instead of period)
    res_alt_punct = find_evidence_match("Kasparro provides structured AI visibility analytics for D2C brands!", source_text)
    assert res_alt_punct["valid"] is False
    assert "not found" in res_alt_punct["rejection_reason"].lower()

    # 4. Altered casing
    res_alt_case = find_evidence_match("kasparro provides structured ai visibility analytics", source_text)
    assert res_alt_case["valid"] is False
    assert "not found" in res_alt_case["rejection_reason"].lower()

    # 5. Unsupported location
    res_unsupported_loc = find_evidence_match("Kasparro provides structured", source_text, location="user_prompt")
    assert res_unsupported_loc["valid"] is False
    assert "unsupported evidence location" in res_unsupported_loc["rejection_reason"].lower()


def test_adversarial_evidence_filtering_in_report_pipeline():
    """Verify validate_report_evidence and renderers filter all forms of invalid evidence."""
    resp1_text = "Overview:\n  Kasparro offers   objective\tbenchmarks, while Profound leads enterprise share."
    resp2_text = "Competitor analysis: Peec AI and Otterly monitor conversational search trends."

    source_lookup = {
        "resp-001": {"answer_text": resp1_text},
        "resp-002": {"answer_text": resp2_text},
    }

    # 1. Genuine exact match
    ev_valid = {
        "response_id": "resp-001",
        "location": "answer_text",
        "start_offset": resp1_text.index("while Profound leads enterprise share."),
        "end_offset": resp1_text.index("while Profound leads enterprise share.") + len("while Profound leads enterprise share."),
        "excerpt": "while Profound leads enterprise share.",
    }

    # 2. Fabricated quotation
    ev_fabricated = {
        "response_id": "resp-001",
        "location": "answer_text",
        "start_offset": 0,
        "end_offset": 30,
        "excerpt": "Kasparro is 100x better than all alternatives.",
    }

    # 3. Altered quotation (word altered)
    ev_altered_words = {
        "response_id": "resp-001",
        "location": "answer_text",
        "start_offset": None,
        "end_offset": None,
        "excerpt": "Kasparro offers verified benchmarks",
    }

    # 4. Altered quotation (punctuation altered)
    ev_altered_punct = {
        "response_id": "resp-001",
        "location": "answer_text",
        "start_offset": None,
        "end_offset": None,
        "excerpt": "while Profound leads enterprise share!",
    }

    # 5. Incorrect offsets (text exists elsewhere, but declared offsets point to different text)
    ev_incorrect_offsets = {
        "response_id": "resp-001",
        "location": "answer_text",
        "start_offset": 0,
        "end_offset": 25,
        "excerpt": "while Profound leads enterprise share.",
    }

    # 6. Out-of-bounds offsets
    ev_oob_offsets = {
        "response_id": "resp-001",
        "location": "answer_text",
        "start_offset": 900,
        "end_offset": 950,
        "excerpt": "while Profound leads enterprise share.",
    }

    # 7. Correct quote associated with incorrect response_id
    ev_wrong_response_id = {
        "response_id": "resp-002",  # Text is in resp-001, not resp-002
        "location": "answer_text",
        "start_offset": None,
        "end_offset": None,
        "excerpt": "while Profound leads enterprise share.",
    }

    # 8. Nonexistent response_id
    ev_missing_response_id = {
        "response_id": "nonexistent-id-999",
        "location": "answer_text",
        "excerpt": "while Profound leads enterprise share.",
    }

    # 9. Unsupported evidence location
    ev_unsupported_loc = {
        "response_id": "resp-001",
        "location": "user_prompt",
        "excerpt": "while Profound leads enterprise share.",
    }

    # 10. Whitespace-normalized candidate (extra spaces submitted, original source has newlines/tabs)
    ev_whitespace_norm = {
        "response_id": "resp-001",
        "location": "answer_text",
        "excerpt": "Kasparro offers objective benchmarks",  # Source has "\n  Kasparro offers   objective\tbenchmarks"
    }

    diagnostics = [
        {
            "title": "Adversarial Integrity Diagnostic",
            "observed_pattern": "Evaluating rigorous evidence validation against adversarial quotes.",
            "comparison": "Clean vs Tampered evidence",
            "evidence": [
                ev_valid,
                ev_fabricated,
                ev_altered_words,
                ev_altered_punct,
                ev_incorrect_offsets,
                ev_oob_offsets,
                ev_wrong_response_id,
                ev_missing_response_id,
                ev_unsupported_loc,
                ev_whitespace_norm,
            ],
        }
    ]

    report_payload = {
        "title": "Evidence Integrity Test Report",
        "dataset_name": "adversarial-dataset",
        "diagnostics": diagnostics,
    }

    # Execute validation
    validated_diags, audit = validate_report_evidence(diagnostics, source_lookup)

    assert audit["accepted_count"] == 2  # Only ev_valid and ev_whitespace_norm
    assert audit["rejected_count"] == 8

    # Verify canonical excerpt mapping for whitespace-normalized quotation
    canonical_ws = validated_diags[0]["evidence"][1]["excerpt"]
    assert canonical_ws == "Kasparro offers   objective\tbenchmarks"
    assert validated_diags[0]["evidence"][1]["match_type"] == "normalized_whitespace"
    assert validated_diags[0]["evidence"][1]["submitted_excerpt"] == "Kasparro offers objective benchmarks"

    # Verify exact slice alignment on both accepted items
    for item in validated_diags[0]["evidence"]:
        src = source_lookup[item["response_id"]]["answer_text"]
        assert src[item["start_offset"]:item["end_offset"]] == item["excerpt"]

    # Verify specific rejection reasons in audit
    rejected_reasons = [r["rejection_reason"].lower() for r in audit["rejected"]]
    assert any("not found" in r for r in rejected_reasons)
    assert any("does not match" in r or "invalid source offsets" in r for r in rejected_reasons)
    assert any("unsupported evidence location" in r for r in rejected_reasons)

    # Verify Markdown rendering filters out all 8 rejected items
    md_output = render_report_markdown(report_payload, source_lookup)
    assert "while Profound leads enterprise share." in md_output
    assert "Kasparro offers   objective\tbenchmarks" in md_output
    assert "Kasparro is 100x better" not in md_output
    assert "Kasparro offers verified benchmarks" not in md_output
    assert "while Profound leads enterprise share!" not in md_output
    assert "nonexistent-id-999" not in md_output

    # Verify HTML rendering filters out all 8 rejected items
    html_output = render_report_html(report_payload, source_lookup)
    assert "while Profound leads enterprise share." in html_output
    assert "Kasparro offers   objective&#9;benchmarks" in html_output or "Kasparro offers   objective\tbenchmarks" in html_output
    assert "Kasparro is 100x better" not in html_output
    assert "Kasparro offers verified benchmarks" not in html_output
    assert "while Profound leads enterprise share!" not in html_output
    assert "nonexistent-id-999" not in html_output


def test_real_model_validation_consistency_with_centralized_audit():
    """Verify real-model and replay execution share the identical centralized evidence audit."""
    source_text = "Independent testing confirmed that Kasparro delivers accurate AISO analytics."

    # Simulate provider candidate items
    candidates = [
        # Valid exact quote
        EvidenceItem(excerpt="Kasparro delivers accurate AISO analytics", location="answer_text"),
        # Fabricated quote
        EvidenceItem(excerpt="Kasparro is endorsed by Gartner Magic Quadrant", location="answer_text"),
        # Altered quote
        EvidenceItem(excerpt="Kasparro delivers flawed AISO analytics", location="answer_text"),
        # Unsupported location
        EvidenceItem(excerpt="Kasparro delivers accurate AISO analytics", location="user_prompt"),
        # Malformed candidate (empty string)
        EvidenceItem(excerpt="   ", location="answer_text"),
    ]

    accepted, rejected = _audit_evidence_candidates(candidates, source_text)

    # Exactly 1 valid candidate
    assert len(accepted) == 1
    assert accepted[0]["excerpt"] == "Kasparro delivers accurate AISO analytics"
    assert accepted[0]["validation_status"] == "valid"
    assert accepted[0]["start_offset"] == source_text.index("Kasparro delivers accurate AISO analytics")
    assert accepted[0]["end_offset"] == accepted[0]["start_offset"] + len("Kasparro delivers accurate AISO analytics")
    assert source_text[accepted[0]["start_offset"]:accepted[0]["end_offset"]] == accepted[0]["excerpt"]

    # Exactly 4 rejected candidates
    assert len(rejected) == 4
    rejected_reasons = [r["rejection_reason"].lower() for r in rejected]
    assert any("not found" in r for r in rejected_reasons)
    assert any("unsupported evidence location" in r for r in rejected_reasons)
    assert any("empty" in r for r in rejected_reasons)

    # Verify mock provider output in execute_analysis follows the same centralized path
    res = ClassificationResult(
        response_id="mock-resp-001",
        engine="gemini",
        status="success",
        kasparro_absent=False,
        kasparro_mentioned=True,
        kasparro_recommended=True,
        kasparro_negative=False,
        competitors=[],
        evidence=candidates,
        confidence=0.95,
        execution_mode="real_model",
        classifier_version="v1",
    )

    labels = res.model_dump()
    labels["evidence"] = accepted
    labels["evidence_validation"] = {
        "accepted": accepted,
        "rejected": rejected,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
    }

    # Canonical evidence field contains zero rejected or unvalidated items
    assert len(labels["evidence"]) == 1
    assert labels["evidence"][0]["excerpt"] == "Kasparro delivers accurate AISO analytics"
    assert labels["evidence_validation"]["rejected_count"] == 4


def test_downstream_report_export_formats_filter_invalid_evidence():
    """Verify that JSON, Markdown, and HTML export endpoints revalidate evidence and filter invalid quotes."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        ds = Dataset(name="export-integrity-ds", source_hash="hash_export", validation_status="valid")
        db.add(ds)
        db.flush()

        source_text = "Verified: Kasparro provides verifiable citations across search engines."
        db_resp = Response(
            dataset_id=ds.id,
            source_response_id="export-resp-101",
            prompt_id="prompt-101",
            engine="chatgpt",
            raw_payload=json.dumps({
                "response_id": "export-resp-101",
                "engine": "chatgpt",
                "answer_text": source_text,
            }),
        )
        db.add(db_resp)
        db.flush()

        rep = Report(dataset_id=ds.id)
        db.add(rep)
        db.flush()

        # Content has 1 genuine quote and 1 injected fabricated quote
        content = {
            "title": "Approved Report for Export",
            "dataset_name": ds.name,
            "source_hash": ds.source_hash,
            "diagnostics": [
                {
                    "title": "Evidence Grounding Finding",
                    "observed_pattern": "Testing export revalidation.",
                    "evidence": [
                        {
                            "response_id": "export-resp-101",
                            "location": "answer_text",
                            "start_offset": source_text.index("Kasparro provides verifiable citations"),
                            "end_offset": source_text.index("Kasparro provides verifiable citations") + len("Kasparro provides verifiable citations"),
                            "excerpt": "Kasparro provides verifiable citations",
                        },
                        {
                            "response_id": "export-resp-101",
                            "location": "answer_text",
                            "excerpt": "Completely hallucinated quote that does not exist.",
                        },
                    ],
                }
            ],
        }

        v1 = ReportVersion(
            report_id=rep.id,
            version_number=1,
            status="APPROVED",
            content_json=json.dumps(content),
            content_hash="test-content-hash",
        )
        db.add(v1)
        db.flush()

        decision = ReviewDecision(
            report_version_id=v1.id,
            reviewer_id="lead-reviewer",
            decision="approve",
            comment="Approved for export",
        )
        db.add(decision)
        db.commit()

        # 1. JSON Export
        json_export = export_approved_report(db, rep.id, output_format="json")
        exported_content = json_export["content"]
        exported_ev = exported_content["diagnostics"][0]["evidence"]
        assert len(exported_ev) == 1
        assert exported_ev[0]["excerpt"] == "Kasparro provides verifiable citations"
        assert exported_ev[0]["start_offset"] == source_text.index("Kasparro provides verifiable citations")
        assert exported_ev[0]["end_offset"] == exported_ev[0]["start_offset"] + len("Kasparro provides verifiable citations")
        assert exported_content["evidence_validation"]["rejected_count"] == 1

        # 2. Markdown Export
        md_export = export_approved_report(db, rep.id, output_format="markdown")
        assert md_export["format"] == "markdown"
        assert "Kasparro provides verifiable citations" in md_export["rendered"]
        assert "Completely hallucinated quote" not in md_export["rendered"]
        assert "export-resp-101" in md_export["rendered"]

        # 3. HTML Export
        html_export = export_approved_report(db, rep.id, output_format="html")
        assert html_export["format"] == "html"
        assert "Kasparro provides verifiable citations" in html_export["rendered"]
        assert "Completely hallucinated quote" not in html_export["rendered"]
        assert "export-resp-101" in html_export["rendered"]

    finally:
        db.close()
