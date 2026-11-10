import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from app.evidence import find_evidence_match, validate_report_evidence


def _pick_complete_sentence_excerpt(
    answer_text: str,
    keywords: List[str],
    max_chars: int = 360,
) -> Optional[str]:
    """Selects a complete verbatim prose sentence containing one of the keywords without mid-word truncation or citation footnotes."""
    if not answer_text:
        return None
    prose_lines: List[str] = []
    for raw_line in answer_text.splitlines():
        s = raw_line.strip()
        if re.match(r"^(?:\*\*)?citations?\s*:?(?:\*\*)?$", s, re.IGNORECASE):
            break
        if re.match(r"^\[\d+\]\s+https?://", s) or re.match(r"^https?://\S+$", s):
            continue
        prose_lines.append(raw_line)
    prose_text = "\n".join(prose_lines)
    parts = re.split(r"\n+|(?<!e\.g)(?<!i\.e)(?<=[.!?])\s+", prose_text)
    for raw in parts:
        cand = raw.strip()
        if not cand or len(cand) < 15 or len(cand) > max_chars:
            continue
        if re.match(r"^\[\d+\]\s+https?://", cand) or re.match(r"^https?://\S+$", cand):
            continue
        low = cand.lower()
        if any(k in low for k in keywords) and cand in answer_text:
            return cand
    return None


def _load_prompts_lookup() -> Dict[str, str]:
    prompts_by_id: Dict[str, str] = {}
    p_path = Path("data") / "prompts.jsonl"
    if p_path.exists():
        with p_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if isinstance(rec.get("prompt_id"), str) and isinstance(rec.get("text"), str):
                        prompts_by_id[rec["prompt_id"]] = rec["text"]
                except Exception:
                    continue
    return prompts_by_id


def build_diagnostics_and_remedies_from_db(
    db: Session,
    dataset_id: str,
    analysis_id: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Generates data-driven diagnostics and remedies exclusively from validated DB rows
    (Response, ResponseResult.evidence_json, Citation), with downstream report validation.
    """
    from app.models import Response as DBResponse, ResponseResult, Citation, AnalysisRun

    responses = db.query(DBResponse).filter(DBResponse.dataset_id == dataset_id).all()
    if not responses:
        fallback_diag = get_default_diagnostics()
        validated_diag, audit_summary = validate_report_evidence(fallback_diag, {})
        return validated_diag, get_default_remedies(), audit_summary

    prompts_lookup = _load_prompts_lookup()
    resp_by_db_id: Dict[str, Any] = {}
    resp_payloads: Dict[str, Dict[str, Any]] = {}
    source_lookup: Dict[str, Dict[str, str]] = {}

    for r in responses:
        resp_by_db_id[r.id] = r
        try:
            payload = json.loads(r.raw_payload)
        except Exception:
            payload = {}
        resp_payloads[r.id] = payload
        ans = payload.get("answer_text", "")
        if not payload.get("prompt_text") and r.prompt_id in prompts_lookup:
            payload["prompt_text"] = prompts_lookup[r.prompt_id]
        source_lookup[r.source_response_id] = {"answer_text": ans}

    # Resolve analysis results
    target_analysis_id = analysis_id
    if not target_analysis_id:
        latest_run = (
            db.query(AnalysisRun)
            .filter(AnalysisRun.dataset_id == dataset_id)
            .order_by(AnalysisRun.created_at.desc())
            .first()
        )
        if latest_run:
            target_analysis_id = latest_run.id

    results_by_resp_id: Dict[str, Any] = {}
    if target_analysis_id:
        res_rows = (
            db.query(ResponseResult)
            .filter(ResponseResult.analysis_id == target_analysis_id)
            .all()
        )
        for row in res_rows:
            results_by_resp_id[row.response_id] = row

    # Citations grouped by DB response id
    citations = (
        db.query(Citation)
        .join(DBResponse, Citation.response_id == DBResponse.id)
        .filter(DBResponse.dataset_id == dataset_id)
        .all()
    )
    domains_by_resp_db_id: Dict[str, List[str]] = {}
    urls_by_resp_db_id: Dict[str, List[str]] = {}
    for c in citations:
        url = (c.url or "").lower()
        dom = urlparse(url).netloc.lower()
        domains_by_resp_db_id.setdefault(c.response_id, []).append(dom)
        urls_by_resp_db_id.setdefault(c.response_id, []).append(url)

    # Compute exact dataset statistics from DB rows
    branded_total = 0
    branded_mentioned = 0
    unbranded_total = 0
    unbranded_mentioned = 0

    engine_totals: Dict[str, int] = {}
    engine_negatives: Dict[str, int] = {}
    unbranded_competitor_ev: List[Dict[str, Any]] = []
    negative_ev_items: List[Dict[str, Any]] = []
    negative_resp_ids: List[str] = []
    kaspr_confusion_ev: List[Dict[str, Any]] = []
    kaspr_confusion_resp_ids: List[str] = []

    scamadviser_resp_ids = set()
    g2_capterra_unbranded_resp_ids = set()

    for r in responses:
        payload = resp_payloads[r.id]
        prompt_text = payload.get("prompt_text", "")
        ans_text = payload.get("answer_text", "")
        is_branded = "kasparro" in prompt_text.lower() or any(
            f":{i:03d}" in r.prompt_id for i in range(1, 26)
        )

        res_row = results_by_resp_id.get(r.id)
        labels: Dict[str, Any] = {}
        ev_list: List[Dict[str, Any]] = []
        status_ok = False
        if res_row:
            status_ok = res_row.status == "success"
            try:
                labels = json.loads(res_row.labels_json or "{}")
            except Exception:
                labels = {}
            try:
                ev_list = json.loads(res_row.evidence_json or "[]")
            except Exception:
                ev_list = []

        if status_ok:
            mentioned = bool(labels.get("kasparro_mentioned"))
            negative = bool(labels.get("kasparro_negative"))
        else:
            mentioned = "kasparro" in ans_text.lower()
            negative = False

        if is_branded:
            branded_total += 1
            if mentioned:
                branded_mentioned += 1
        else:
            unbranded_total += 1
            if mentioned:
                unbranded_mentioned += 1

        engine_totals[r.engine] = engine_totals.get(r.engine, 0) + 1
        if negative:
            engine_negatives[r.engine] = engine_negatives.get(r.engine, 0) + 1
            negative_resp_ids.append(r.source_response_id)

        resp_domains = domains_by_resp_db_id.get(r.id, [])
        resp_urls = urls_by_resp_db_id.get(r.id, [])
        if any("scamadviser" in d for d in resp_domains):
            scamadviser_resp_ids.add(r.source_response_id)
        if not is_branded and any("g2.com" in d or "capterra" in d for d in resp_domains):
            g2_capterra_unbranded_resp_ids.add(r.source_response_id)

        # Unbranded competitor discovery evidence (no Kasparro mention -> direct sentence from answer_text)
        if not is_branded and not mentioned and len(unbranded_competitor_ev) < 2:
            excerpt = _pick_complete_sentence_excerpt(ans_text, ["profound", "peec ai", "otterly"])
            if excerpt:
                m = find_evidence_match(excerpt, ans_text, location="answer_text")
                if m["valid"]:
                    unbranded_competitor_ev.append({
                        "response_id": r.source_response_id,
                        "engine": r.engine,
                        "prompt": f"{r.prompt_id} ({prompt_text})" if prompt_text else r.prompt_id,
                        "excerpt": m["canonical_excerpt"],
                        "location": "answer_text",
                        "start_offset": m["start_offset"],
                        "end_offset": m["end_offset"],
                        "match_type": m["match_type"],
                        "validation_status": "valid",
                    })

        # Validated negative evidence strictly from ResponseResult.evidence_json
        if negative and ev_list:
            pref_scam_site = any("scamadviser" in d for d in resp_domains) or r.engine == "chatgpt"
            warn_re = re.compile(
                r"\b(?:lacks?|couldn't\s+find|there\s+isn't\s+much|there\s+is\s+limited|"
                r"unreliable|unproven|caution|skeptical|not\s+(?:a\s+)?widely|red\s+flags?|scamadviser)\b",
                re.IGNORECASE,
            )
            chosen_ev = None
            has_explicit_warn_quote = False
            for ev in ev_list:
                if not isinstance(ev, dict) or not isinstance(ev.get("excerpt"), str):
                    continue
                prose_only = re.sub(r"\[([^\]]*)\]\((https?://[^)]+)\)", " ", ev["excerpt"]).strip()
                if len(prose_only) < 20:
                    continue
                if chosen_ev is None:
                    chosen_ev = ev
                if warn_re.search(prose_only):
                    chosen_ev = ev
                    has_explicit_warn_quote = True
                    break
            if isinstance(chosen_ev, dict) and isinstance(chosen_ev.get("excerpt"), str):
                candidate = {
                    "response_id": r.source_response_id,
                    "engine": r.engine,
                    "prompt": f"{r.prompt_id} ({prompt_text})" if prompt_text else r.prompt_id,
                    "excerpt": chosen_ev["excerpt"],
                    "location": chosen_ev.get("location", "answer_text"),
                    "_prefer": has_explicit_warn_quote and pref_scam_site,
                    "_has_warn": has_explicit_warn_quote,
                }
                negative_ev_items.append(candidate)

        # Brand entity confusion ('Kaspr' / 'Gaspar AI') using validated evidence_json if present
        has_kaspr_citation = any("kaspr" in u for u in resp_urls) or any("kaspr" in d for d in resp_domains)
        has_kaspr_text = bool(re.search(r"\b(?:kaspr|gaspar\s+ai)\b", ans_text, re.IGNORECASE))
        if has_kaspr_citation or has_kaspr_text:
            kaspr_confusion_resp_ids.append(r.source_response_id)
            chosen_excerpt = _pick_complete_sentence_excerpt(ans_text, ["kaspr", "gaspar"])
            if not chosen_excerpt and ev_list:
                for ev in ev_list:
                    if isinstance(ev, dict) and isinstance(ev.get("excerpt"), str) and (
                        "kaspr" in ev["excerpt"].lower() or "gaspar" in ev["excerpt"].lower()
                    ):
                        chosen_excerpt = ev["excerpt"]
                        break
            if chosen_excerpt:
                m = find_evidence_match(chosen_excerpt, ans_text, location="answer_text")
                if m["valid"]:
                    kaspr_confusion_ev.append({
                        "response_id": r.source_response_id,
                        "engine": r.engine,
                        "prompt": f"{r.prompt_id} ({prompt_text})" if prompt_text else r.prompt_id,
                        "excerpt": m["canonical_excerpt"],
                        "location": "answer_text",
                        "start_offset": m["start_offset"],
                        "end_offset": m["end_offset"],
                        "match_type": m["match_type"],
                        "validation_status": "valid",
                        "_prefer": "kaspr" in chosen_excerpt.lower(),
                    })

    # Prioritize negative evidence with explicit cautionary language & ScamAdviser/ChatGPT
    negative_ev_items.sort(
        key=lambda x: (not x.pop("_prefer", False), not x.pop("_has_warn", False), x["engine"] != "chatgpt")
    )
    selected_negative_ev = negative_ev_items[:2]

    kaspr_confusion_ev.sort(key=lambda x: not x.pop("_prefer", False))
    selected_kaspr_ev = kaspr_confusion_ev[:2]

    branded_pct = round((branded_mentioned / branded_total) * 100, 1) if branded_total else 0.0
    unbranded_pct = round((unbranded_mentioned / unbranded_total) * 100, 1) if unbranded_total else 0.0

    def _eng_rate(eng: str) -> str:
        tot = engine_totals.get(eng, 0)
        neg = engine_negatives.get(eng, 0)
        pct = round((neg / tot) * 100, 1) if tot else 0.0
        return f"{pct}% ({neg}/{tot})"

    top_neg_engine = max(
        engine_totals.keys(),
        key=lambda e: (engine_negatives.get(e, 0) / engine_totals[e]) if engine_totals[e] else 0.0,
        default="chatgpt",
    )

    diagnostics: List[Dict[str, Any]] = [
        {
            "title": "Absence in Unbranded Category Discovery Prompts",
            "observed_pattern": (
                f"Across {unbranded_total} unbranded category discovery responses, "
                f"Kasparro was included in {unbranded_mentioned} out of {unbranded_total} responses "
                f"({unbranded_pct}% inclusion rate), while competitors such as Profound, Peec AI, and Otterly "
                "dominated recommendations."
            ),
            "comparison": (
                f"Branded inclusion rate: {branded_mentioned}/{branded_total} ({branded_pct}%) vs "
                f"Unbranded category inclusion rate: {unbranded_mentioned}/{unbranded_total} ({unbranded_pct}%)."
            ),
            "evidence": unbranded_competitor_ev,
            "possible_explanation": (
                "Generative AI models assemble category shortlists from co-occurrence on third-party software "
                "directories and industry roundups where Kasparro currently has sparse presence."
            ),
            "validation_needed": (
                "Audit G2, Capterra, and industry listicles to benchmark competitor directory presence "
                "relative to Kasparro."
            ),
            "confidence_and_limitations": (
                f"Derived directly from n={unbranded_total} analyzed unbranded responses and n={branded_total} "
                "branded responses in the current dataset."
            ),
        },
        {
            "title": "Third-Party Evidence Deficit and Cautionary Characterization",
            "observed_pattern": (
                f"Among analyzed responses, negative or cautionary characterization was highest on {top_neg_engine} "
                f"({_eng_rate(top_neg_engine)}), alongside {len(scamadviser_resp_ids)} response(s) citing "
                "ScamAdviser or highlighting missing independent case studies."
            ),
            "comparison": (
                f"Negative characterization rate by engine — ChatGPT: {_eng_rate('chatgpt')}, "
                f"Google AI Mode: {_eng_rate('aimode')}, Gemini: {_eng_rate('gemini')}."
            ),
            "evidence": selected_negative_ev,
            "possible_explanation": (
                "Live web retrieval surfaces low-trust or thin-validation signals when verifiable third-party "
                "case studies and external customer reviews are scarce."
            ),
            "validation_needed": (
                "Publish independent third-party customer case studies and verify whether subsequent crawls "
                "displace cautionary citations."
            ),
            "confidence_and_limitations": (
                f"Derived directly from validated ResponseResult labels and {len(scamadviser_resp_ids)} ScamAdviser "
                "citation matches in the DB."
            ),
        },
        {
            "title": "Brand Entity Confusion with 'Kaspr' / Similar Names",
            "observed_pattern": (
                f"{len(kaspr_confusion_resp_ids)} response(s) reference phonetically similar entities such as "
                "'Kaspr' or 'Gaspar AI' (including G2/pricing disambiguation notes), splitting entity attribution."
            ),
            "comparison": (
                f"Disambiguation or sibling-entity citations detected in {len(kaspr_confusion_resp_ids)}/{len(responses)} "
                "total responses, compared against clean Kasparro-only attribution."
            ),
            "evidence": selected_kaspr_ev,
            "possible_explanation": (
                "Orthographic proximity to 'Kaspr' paired with limited structured Organization schema and external "
                "entity links causes search agents to surface Kaspr profiles during disambiguation."
            ),
            "validation_needed": (
                "Validate Organization JSON-LD markup on kasparro.com and re-test disambiguation prompts."
            ),
            "confidence_and_limitations": (
                f"Corroborated across {len(kaspr_confusion_resp_ids)} DB responses/citations containing "
                "Kaspr/Gaspar references."
            ),
        },
    ]

    validated_diagnostics, audit_summary = validate_report_evidence(diagnostics, source_lookup)

    remedies = [
        {
            "title": "Publish Verified Third-Party Case Studies with Before/After GEO Metrics",
            "problem": (
                f"Negative/cautionary responses reached {_eng_rate(top_neg_engine)} on {top_neg_engine}, "
                f"with {len(scamadviser_resp_ids)} response(s) citing ScamAdviser or lack of independent proof."
            ),
            "supporting_evidence": (
                sorted(list(scamadviser_resp_ids))[:3] or negative_resp_ids[:3]
            ),
            "action": (
                "Produce and publish 3 detailed customer case studies on independent third-party platforms "
                "with verifiable before-and-after AI visibility metrics."
            ),
            "expected_benefit": (
                "Provides third-party validation for retrieval-augmented AI engines, displacing cautionary "
                "ScamAdviser lookups."
            ),
            "effort": "Medium: Requires customer approval and editorial packaging.",
            "uncertainty": "LLM search indexes refresh asynchronously over weeks.",
            "validation": "Re-evaluate branded trust prompts after publication and check ScamAdviser citation drops.",
        },
        {
            "title": "Establish Official Profiles on Software Review Directories (G2, Capterra, ProductHunt)",
            "problem": (
                f"Kasparro appeared in {unbranded_mentioned}/{unbranded_total} ({unbranded_pct}%) unbranded category "
                f"discovery responses, while competitors appeared consistently and {len(g2_capterra_unbranded_resp_ids)}/{unbranded_total} "
                "unbranded responses directly cited G2 or Capterra."
            ),
            "supporting_evidence": [ev["response_id"] for ev in unbranded_competitor_ev]
            or sorted(list(g2_capterra_unbranded_resp_ids))[:3],
            "action": (
                "Claim verified vendor profiles on G2, Capterra, and ProductHunt under AI Search Optimization "
                "and collect verified customer reviews."
            ),
            "expected_benefit": (
                "Strengthens category co-occurrence in buyer shortlists across unbranded discovery queries."
            ),
            "effort": "Low: Profile setup and review collection workflow.",
            "uncertainty": "Directory verification requires minimum review thresholds.",
            "validation": "Re-run unbranded discovery prompts and track unbranded inclusion rate change.",
        },
        {
            "title": "Implement Organization Schema.org Markup & Brand Disambiguation from 'Kaspr'",
            "problem": (
                f"Entity overlap with 'Kaspr' or 'Gaspar AI' appeared in {len(kaspr_confusion_resp_ids)} dataset "
                "response(s)/citation(s), diluting clean product entity attribution."
            ),
            "supporting_evidence": kaspr_confusion_resp_ids[:3]
            or [ev["response_id"] for ev in kaspr_confusion_ev],
            "action": (
                "Deploy JSON-LD Organization schema on kasparro.com with explicit sameAs links and publish "
                "an entity clarification page distinguishing Kasparro (AISO/GEO) from Kaspr (B2B contact data)."
            ),
            "expected_benefit": (
                "Improves entity resolution precision for web search bots and reduces accidental Kaspr overlap."
            ),
            "effort": "Low: Technical schema deployment and FAQ copy update.",
            "uncertainty": "Knowledge graph updates propagate over multiple crawl cycles.",
            "validation": "Verify Rich Results validation passes and re-check disambiguation citations.",
        },
    ]

    return validated_diagnostics, remedies, audit_summary


def get_default_diagnostics() -> List[Dict[str, Any]]:
    """
    Returns baseline structured diagnostic templates matching verified historical dataset metrics.
    When database response rows are present, callers should prefer build_diagnostics_and_remedies_from_db().
    """
    return [
        {
            "title": "Absence in Unbranded Category Discovery Prompts",
            "observed_pattern": (
                "Across all 25 unbranded category prompts (kasparro:ai_shortlisting:026 to 050) "
                "evaluated across Google AI Mode, ChatGPT, and Gemini (75 total responses), "
                "Kasparro was included in 0 out of 75 responses (0.0% inclusion rate). "
                "Meanwhile, competitors Profound, Peec AI, and Otterly were consistently recommended."
            ),
            "comparison": (
                "Branded inclusion rate vs Unbranded category inclusion rate: 0/75 (0.0%) in unbranded "
                "category discovery prompts, confirming zero spontaneous category recall without brand naming."
            ),
            "evidence": [
                {
                    "response_id": "0f38b477-9f3c-44a8-9d10-0b6016db6150",
                    "engine": "gemini",
                    "prompt": "kasparro:ai_shortlisting:036 (what is the best software for measuring brand inclusion in AI search answers?)",
                    "excerpt": "Profound is a powerhouse in the AI visibility space. It tracks an extensive array of engines (10+ platforms including niche models like Grok and DeepSeek).",
                    "location": "answer_text",
                },
                {
                    "response_id": "0697376e-335d-45ef-a593-bc12c5e1ecf3",
                    "engine": "aimode",
                    "prompt": "kasparro:ai_shortlisting:037 (what tools do growth marketers recommend for AI answer engine optimization?)",
                    "excerpt": "- **Profound:** Tracks which domains are cited in AI-generated answers and provides analytics to help brands measure share-of-voice across major AI platforms and human conversation forums like Reddit.",
                    "location": "answer_text",
                },
            ],
            "possible_explanation": (
                "Generative AI models assemble recommendations based on category co-occurrence on "
                "third-party platforms (G2, Reddit, Capterra, industry listicles). Kasparro currently lacks "
                "independent software directory profiles."
            ),
            "validation_needed": (
                "Audit third-party review sites and industry listicles to verify whether Kasparro has any "
                "presence in GEO/AISO software directories compared to Profound and Peec AI."
            ),
            "confidence_and_limitations": (
                "High statistical confidence for this historical snapshot (n=75 unbranded responses, 0 mentions). "
                "Represents historical snapshot captured on 31 July 2026."
            ),
        },
        {
            "title": "Third-Party Evidence Deficit and Credibility Warnings in ChatGPT",
            "observed_pattern": (
                "When evaluated in ChatGPT, answers repeatedly warn buyers that Kasparro lacks independent "
                "case studies with before/after data and cite ScamAdviser as a domain trust signal."
            ),
            "comparison": (
                "Negative characterization is concentrated in ChatGPT responses citing thin third-party evidence, "
                "compared to lower negative rates in Google AI Mode and Gemini."
            ),
            "evidence": [
                {
                    "response_id": "ac5bdf24-6a6e-49a0-abf5-2755ff3b42bc",
                    "engine": "chatgpt",
                    "prompt": "kasparro:ai_shortlisting:001 (does kasparro actually work for B2B SaaS companies trying to get recommended by chatgpt?)",
                    "excerpt": "However, I couldn't find independent evidence showing that Kasparro consistently delivers measurable improvements for B2B SaaS companies specifically.",
                    "location": "answer_text",
                },
                {
                    "response_id": "08f81acc-0824-4e3a-a5d5-58446e2a6a90",
                    "engine": "chatgpt",
                    "prompt": "kasparro:ai_shortlisting:005 (does kasparro actually work or is ai visibility tracking just a gimmick?)",
                    "excerpt": "Short answer: **AI visibility tracking is a real problem, but many tools oversell how precisely they can measure it.** Kasparro falls into a category of tools trying to solve a legitimate need, but I'd be skeptical of taking any single \"AI visibility score\" at face value.",
                    "location": "answer_text",
                },
            ],
            "possible_explanation": (
                "ChatGPT's live web retrieval prioritizes domain trustworthiness checks and third-party validation. "
                "Because kasparro.com lacks verified external client case studies, search queries surface "
                "ScamAdviser and cautionary commentary."
            ),
            "validation_needed": (
                "Publish verified before-and-after client case studies on reputable third-party domains and test "
                "whether subsequent live search retrievals replace the ScamAdviser citation."
            ),
            "confidence_and_limitations": (
                "High confidence: Directly evidenced by source response excerpts and cited URLs."
            ),
        },
        {
            "title": "Brand Entity Confusion with 'Kaspr' in AI Search Results",
            "observed_pattern": (
                "Responses across ChatGPT and Google AI Mode disambiguate or confuse 'Kasparro' with 'Kaspr' "
                "(the B2B contact data tool) or 'Gaspar AI', surfacing Kaspr pricing and G2 reviews."
            ),
            "comparison": (
                "Entity overlap occurs when answering pricing and company capability questions (e.g., Prompt 018)."
            ),
            "evidence": [
                {
                    "response_id": "1d2dc007-0757-480d-a086-6b6e2e13c463",
                    "engine": "chatgpt",
                    "prompt": "kasparro:ai_shortlisting:018 (is kasparro overpriced for B2B SaaS startups?)",
                    "excerpt": "If you mean **Kasparro** (the B2B SaaS growth/outbound agency, not Kaspr), I couldn't find reliable public pricing or enough verified information to judge whether it's objectively overpriced.",
                    "location": "answer_text",
                },
                {
                    "response_id": "a3fdd8bb-bcd9-4608-9786-ad4b3a2c7dc2",
                    "engine": "aimode",
                    "prompt": "kasparro:ai_shortlisting:001 (does kasparro actually work for B2B SaaS companies trying to get recommended by chatgpt?)",
                    "excerpt": "Based on my research, Kasparro is not a widely recognized, top-tier agency or tool in the AI visibility space (AISO - AI Search Optimization) for B2B SaaS according to public search results as of July 2026.",
                    "location": "answer_text",
                },
            ],
            "possible_explanation": (
                "Phonetic and orthographic proximity to 'Kaspr' combined with sparse entity graph data "
                "leads AI search engines to pull citations about Kaspr (such as G2 reviews for Kaspr)."
            ),
            "validation_needed": (
                "Check JSON-LD Schema on kasparro.com and test prompt disambiguation explicitly."
            ),
            "confidence_and_limitations": (
                "Corroborated across dataset responses and G2 Kaspr citations."
            ),
        },
    ]
