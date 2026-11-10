from typing import List, Dict, Any


def get_default_remedies() -> List[Dict[str, Any]]:
    """
    Returns the three prioritized remedies following logically from the diagnostics.
    """
    return [
        {
            "title": "Publish 3 Verified Third-Party Case Studies with Before/After GEO Metrics",
            "problem": (
                "ChatGPT directly cites ScamAdviser and cautions potential buyers that Kasparro lacks "
                "independent case studies and third-party validation (Diagnostic 2, Response ac5bdf24-6a6e-49a0-abf5-2755ff3b42bc)."
            ),
            "supporting_evidence": [
                "ac5bdf24-6a6e-49a0-abf5-2755ff3b42bc",
                "08f81acc-0824-4e3a-a5d5-58446e2a6a90"
            ],
            "action": (
                "Produce and publish 3 detailed customer case studies on high-authority external platforms "
                "(Medium, Substack, industry tech blogs) featuring verifiable before-and-after AI visibility metrics."
            ),
            "expected_benefit": (
                "Provides authoritative third-party source material for LLM search agents, displacing ScamAdviser "
                "citations and converting cautionary answers into substantiated trust signals."
            ),
            "effort": "Medium: Requires customer approval and 2 weeks of editorial packaging.",
            "uncertainty": (
                "LLM crawler indexing schedules vary (days to weeks); does not guarantee immediate ranking changes."
            ),
            "validation": (
                "Re-run prompts 001-005 in a 30-day evaluation window. Target: 0 ScamAdviser citations and positive sentiment."
            )
        },
        {
            "title": "Establish Official Profiles on Software Review Directories (G2, Capterra, ProductHunt)",
            "problem": (
                "Kasparro is 100% absent (0/75 responses) from unbranded category discovery queries, "
                "while AI engines frequently ground competitor shortlists in third-party review directories and editorial listicles (Diagnostic 1, Response 0f38b477-9f3c-44a8-9d10-0b6016db6150)."
            ),
            "supporting_evidence": [
                "0f38b477-9f3c-44a8-9d10-0b6016db6150",
                "0697376e-335d-45ef-a593-bc12c5e1ecf3",
                "a3fdd8bb-bcd9-4608-9786-ad4b3a2c7dc2"
            ],
            "action": (
                "Claim and populate verified vendor profiles on G2, Capterra, and ProductHunt under "
                "'AI Search Optimization' and 'Marketing Analytics', and collect initial verified user reviews."
            ),
            "expected_benefit": (
                "Integrates Kasparro into the category co-occurrence graph that LLMs scan when responding "
                "to generic buyer recommendations."
            ),
            "effort": "Low: Administrative profile setup and initial review requests.",
            "uncertainty": "Review sites require verification processes and minimum review counts before displaying badges.",
            "validation": (
                "Evaluate prompts 026-050 after 60 days. Target: Kasparro inclusion rate increases from 0% to >15%."
            )
        },
        {
            "title": "Implement Organization Schema.org Markup & Brand Disambiguation to Separate from 'Kaspr'",
            "problem": (
                "AI engines frequently confuse Kasparro with French tool 'Kaspr', quoting Kaspr's pricing and G2 reviews (Diagnostic 3, Response 1d2dc007-0757-480d-a086-6b6e2e13c463)."
            ),
            "supporting_evidence": [
                "1d2dc007-0757-480d-a086-6b6e2e13c463",
                "a3fdd8bb-bcd9-4608-9786-ad4b3a2c7dc2"
            ],
            "action": (
                "Deploy JSON-LD Organization schema on kasparro.com with exact brand entity definitions, "
                "sameAs social references, and publish a brief 'About Kasparro vs Kaspr' entity disambiguation note."
            ),
            "expected_benefit": (
                "Clarifies entity resolution for search engine crawlers (Googlebot, OAI-SearchBot), eliminating Kaspr.io citations."
            ),
            "effort": "Low: Straightforward technical website markup change.",
            "uncertainty": "Search engines take time to refresh entity graphs.",
            "validation": (
                "Verify Google Rich Results test passes and verify zero kaspr.io citations on branded prompts 016-019."
            )
        }
    ]

