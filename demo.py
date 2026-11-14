"""
Kasparro AI Visibility Analysis — One-Click Demonstration Script.

The demo fails closed when pack validation, analysis metrics, or report lifecycle
checks are incomplete. It does not substitute fabricated metric defaults.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import Base
import app.models  # noqa: F401
from app.export import export_approved_report
from app.ingestion import import_dataset
from app.classification import execute_analysis
from app.reports import create_initial_report, submit_report_for_review
from app.review import process_review_decision
from app.schemas import ReviewDecisionRequest


def print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(f" {title}")
    print("=" * 72)


def require_mapping(value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Required analysis field '{path}' is missing or invalid")
    return value


def require_number(value: Any, path: str, *, minimum: float = 0.0,
                   maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"Required analysis metric '{path}' is missing or non-numeric")
    result = float(value)
    if not math.isfinite(result):
        raise RuntimeError(f"Required analysis metric '{path}' is not finite")
    if result < minimum or (maximum is not None and result > maximum):
        raise RuntimeError(f"Required analysis metric '{path}' is outside its valid range")
    return result


def require_rate(distribution: Dict[str, Any], key: str, context: str) -> float:
    return require_number(distribution.get(key), f"{context}.{key}", minimum=0.0, maximum=1.0)


def run_pack_integrity_check() -> str:
    """Run the real pack checker; never print a success claim without executing it."""
    checker = ROOT / "tools" / "check_pack.py"
    if not checker.is_file():
        raise RuntimeError(f"Pack checker is missing: {checker}")
    completed = subprocess.run(
        [sys.executable, str(checker)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def expect_export_blocked(db: Any, report_id: str, expected_state: str) -> None:
    try:
        export_approved_report(db, report_id=report_id)
    except HTTPException as exc:
        if exc.status_code != 400:
            raise RuntimeError(
                f"Expected HTTP 400 when exporting {expected_state}, got HTTP {exc.status_code}"
            ) from exc
        print(f" [PASS] Export correctly blocked for {expected_state} (HTTP 400).")
        return
    raise RuntimeError(f"Export unexpectedly succeeded for {expected_state}")


def main() -> None:
    start_time = time.time()
    print_header("KASPARRO AI VISIBILITY ANALYSIS — END-TO-END DEMO")
    print(" Execution Mode : Keyless Replay (Deterministic, No API Keys Required)")

    # 1. Execute the actual pack integrity checker.
    print_header("STEP 1: Verifying Pack Integrity")
    pack_output = run_pack_integrity_check()
    print(pack_output)

    run_metadata_path = ROOT / "data" / "run.json"
    run_metadata = json.loads(run_metadata_path.read_text(encoding="utf-8"))
    print(f" Snapshot Date  : {run_metadata.get('historical_capture_date', 'Not recorded')}")
    print(f" Engines Tested : {', '.join(run_metadata.get('engines', {}).values())}")

    # 2. Use an isolated in-memory database; no demo_run.db is left behind.
    print_header("STEP 2: Initializing Isolated SQLite Database")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    try:
        print(f" [PASS] Created isolated database with {len(Base.metadata.tables)} registered tables.")

        # 3. Import only after the pack has passed its checksum and relationship checks.
        print_header("STEP 3: Ingesting Historical Dataset Snapshot")
        import_result = import_dataset(
            db,
            dataset_name="kasparro-historical-snapshot",
            source_directory=str(ROOT / "data"),
        )
        if import_result.validation_status != "valid":
            raise RuntimeError(f"Dataset import was not valid: {import_result.validation_status}")
        print(" [PASS] Ingestion completed:")
        print(f"        • Dataset ID       : {import_result.dataset_id}")
        print(f"        • Prompts          : {import_result.imported_prompts}")
        print(f"        • Responses        : {import_result.imported_responses}")
        print(f"        • Citations        : {import_result.imported_citations}")

        # 4. Execute replay analysis and require the metrics that the demo displays.
        print_header("STEP 4: Executing Deterministic AI Visibility Analysis")
        print(f" [*] Running replay classifier across {import_result.imported_responses} imported responses...")
        analysis = execute_analysis(
            db,
            dataset_id=import_result.dataset_id,
            execution_mode="replay",
        )
        if analysis.status != "completed":
            raise RuntimeError(f"Analysis did not complete: status={analysis.status}")

        config_summary = json.loads(analysis.configuration_json or "{}")
        overall = require_mapping(config_summary.get("overall"), "overall")
        engine_aggregates = require_mapping(
            config_summary.get("engine_aggregates"),
            "engine_aggregates",
        )
        overall_score = require_number(
            overall.get("mean_score"),
            "overall.mean_score",
            minimum=0,
            maximum=100,
        )
        overall_distribution = require_mapping(overall.get("distribution"), "overall.distribution")
        overall_inclusion = require_rate(overall_distribution, "inclusion_rate", "overall.distribution")
        overall_recommendation = require_rate(overall_distribution, "recommendation_rate", "overall.distribution")
        overall_negative = require_rate(overall_distribution, "negative_rate", "overall.distribution")

        total_eligible = int(require_number(overall.get("total_eligible"), "overall.total_eligible"))
        total_successful = int(require_number(overall.get("total_successful"), "overall.total_successful"))
        total_failed = int(require_number(overall.get("total_failed"), "overall.total_failed"))
        total_skipped = int(require_number(overall.get("total_skipped"), "overall.total_skipped"))
        if total_successful + total_failed + total_skipped != total_eligible:
            raise RuntimeError("Analysis response counts are inconsistent")

        print(f" [PASS] Analysis Run ID: {analysis.id}")
        print(f"        • Status                  : {analysis.status.upper()}")
        print(f"        • Overall Visibility Score: {overall_score:.2f} / 100")
        print(f"        • Eligible Responses      : {total_eligible}")
        print(f"        • Successful              : {total_successful}")
        print(f"        • Failed                  : {total_failed}")
        print(f"        • Skipped                 : {total_skipped}")

        print("\n" + "─" * 72)
        print("  ENGINE VISIBILITY BENCHMARK TABLE")
        print("─" * 72)
        print(f"  {'Engine':<18} | {'Score':<8} | {'Inclusion':<11} | {'Recommend':<11} | {'Negative':<10}")
        print("─" * 72)

        for engine_code, engine_name in (
            ("gemini", "Google Gemini"),
            ("chatgpt", "OpenAI ChatGPT"),
            ("aimode", "Google AI Mode"),
        ):
            metrics = require_mapping(engine_aggregates.get(engine_code), f"engine_aggregates.{engine_code}")
            distribution = require_mapping(
                metrics.get("distribution"),
                f"engine_aggregates.{engine_code}.distribution",
            )
            score = require_number(
                metrics.get("mean_score"),
                f"engine_aggregates.{engine_code}.mean_score",
                minimum=0,
                maximum=100,
            )
            inc = require_rate(distribution, "inclusion_rate", f"{engine_code}.distribution")
            rec = require_rate(distribution, "recommendation_rate", f"{engine_code}.distribution")
            neg = require_rate(distribution, "negative_rate", f"{engine_code}.distribution")
            print(
                f"  {engine_name:<18} | {score:<8.1f} | {inc * 100:<10.1f}% | "
                f"{rec * 100:<10.1f}% | {neg * 100:<9.1f}%"
            )

        print("─" * 72)
        print(
            f"  {'Combined':<18} | {overall_score:<8.1f} | {overall_inclusion * 100:<10.1f}% | "
            f"{overall_recommendation * 100:<10.1f}% | {overall_negative * 100:<9.1f}%"
        )
        print("─" * 72)

        # 5. Verify the report lifecycle with exact expected error semantics.
        print_header("STEP 5: Demonstrating Report Lifecycle & Export Gate")
        report = create_initial_report(db, dataset_id=import_result.dataset_id, analysis_id=analysis.id)
        expect_export_blocked(db, report.id, "DRAFT")

        submitted_version = submit_report_for_review(db, report_id=report.id)
        expect_export_blocked(db, report.id, "SUBMITTED")

        decision_request = ReviewDecisionRequest(
            version_id=submitted_version.id,
            decision="approve",
            comment="Verified against the current analysis and validated source evidence.",
        )
        approved_version = process_review_decision(
            db,
            report_id=report.id,
            decision_req=decision_request,
            reviewer_id="demo-reviewer",
        )
        if approved_version.status != "APPROVED":
            raise RuntimeError(f"Report approval did not complete: {approved_version.status}")

        export_payload = export_approved_report(db, report_id=report.id)
        exported_content = require_mapping(export_payload.get("content"), "export.content")
        content_hash = export_payload.get("content_hash")
        if not isinstance(content_hash, str) or len(content_hash) != 64:
            raise RuntimeError("Approved export did not contain a valid SHA-256 content hash")
        print(" [PASS] Approved report exported successfully.")
        print(f"        • Export Version : {export_payload.get('version_id')}")
        print(f"        • Content Hash   : {content_hash}")
        print(f"        • Diagnostics    : {len(exported_content.get('diagnostics', []))}")
        print(f"        • Remedies       : {len(exported_content.get('remedies', []))}")

    finally:
        db.close()
        engine.dispose()

    elapsed = time.time() - start_time
    print_header(f"DEMO COMPLETED IN {elapsed:.2f} SECONDS")
    print("""
Next verification commands:
  1. Automated tests          : pytest -v
  2. Regression evaluation    : python -m evaluation.run_eval --mode replay --split regression
  3. Held-out candidate check : python -m evaluation.run_eval --mode replay --split held_out
  4. Regenerate report assets : python tools/regenerate_artifacts.py

Test counts and CI status are intentionally not hardcoded in this demo.
""")


if __name__ == "__main__":
    main()
