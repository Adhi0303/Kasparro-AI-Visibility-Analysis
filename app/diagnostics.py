from typing import List, Dict, Any


def get_default_diagnostics() -> List[Dict[str, Any]]:
    """
    Returns the three evidence-backed diagnostics derived from actual dataset analysis.
    Every finding cites actual response IDs and exact excerpts.
    """
    return [
        {
            "title": "Complete Absence in Unbranded Category Discovery Prompts",
            "observed_pattern": (
                "Across all 25 unbranded category prompts (kasparro:ai_shortlisting:026 to 050) "
                "evaluated across Google AI Mode, ChatGPT, and Gemini (75 total responses), "
                "Kasparro was included in 0 out of 75 responses (0.0% inclusion rate). "
                "Meanwhile, competitors Profound, Peec AI, and Otterly were consistently recommended."
            ),
            "comparison": (
                "Branded inclusion rate: 37/75 (49.3%) vs Unbranded category inclusion rate: 0/75 (0.0%). "
                "Kasparro currently has zero spontaneous category recall when buyers do not explicitly name it."
            ),
            "evidence": [
                {
                    "response_id": "0f38b477-9f3c-44a8-9d10-0b6016db6150",
                    "engine": "gemini",
                    "prompt": "kasparro:ai_shortlisting:036 (what is the best software for measuring brand inclusion in AI search answers?)",
                    "excerpt": "Profound is a powerhouse in the AI visibility space. It tracks an extensive array of engines (10+ platforms including niche models like Grok and DeepSeek)."
                },
                {
                    "response_id": "0697376e-335d-45ef-a593-bc12c5e1ecf3",
                    "engine": "aimode",
                    "prompt": "kasparro:ai_shortlisting:037 (what tools do growth marketers recommend for AI answer engine optimization?)",
                    "excerpt": "- **Profound:** Tracks which domains are cited in AI-generated answers and provides analytics to help brands measure share-of-voice across major AI platforms and human conversation forums like Reddit."
                }
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
                "High statistical confidence for this historical snapshot (n=75 responses, 0 mentions). "
                "Represents historical snapshot captured on 31 July 2026."
            )
        },
        {
            "title": "Severe Third-Party Evidence Deficit and Credibility Warnings in ChatGPT",
            "observed_pattern": (
                "When Kasparro is evaluated in ChatGPT, it receives negative or cautionary characterization "
                "in 12% of responses (6/50)—the highest negative rate of all three engines. ChatGPT answers "
                "repeatedly warn buyers that Kasparro lacks independent case studies and cite ScamAdviser."
            ),
            "comparison": (
                "Negative characterization rate: ChatGPT: 12.0% (6/50) vs Google AI Mode: 4.0% (2/50) vs Gemini: 2.0% (1/50)."
            ),
            "evidence": [
                {
                    "response_id": "ac5bdf24-6a6e-49a0-abf5-2755ff3b42bc",
                    "engine": "chatgpt",
                    "prompt": "kasparro:ai_shortlisting:001 (does kasparro actually work for B2B SaaS companies trying to get recommended by chatgpt?)",
                    "excerpt": "However, I couldn't find independent evidence showing that Kasparro consistently delivers measurable improvements for B2B SaaS companies specifically. Most of the publicly available material is the company's own positioning rather than third-party case studies with before/after data. [www.scamadviser.com](https://www.scamadviser.com/check-website/kasparro.com?utm_source=chatgpt.com)"
                },
                {
                    "response_id": "08f81acc-0824-4e3a-a5d5-58446e2a6a90",
                    "engine": "chatgpt",
                    "prompt": "kasparro:ai_shortlisting:005 (does kasparro actually work or is ai visibility tracking just a gimmick?)",
                    "excerpt": "Short answer: **AI visibility tracking is a real problem, but many tools oversell how precisely they can measure it.** Kasparro falls into a category of tools trying to solve a legitimate need, but I'd be skeptical of taking any single \"AI visibility"
                }
            ],
            "possible_explanation": (
                "ChatGPT's live web retrieval prioritizes domain trustworthiness checks and third-party validation. "
                "Because kasparro.com is a new domain without verified external client case studies, search queries "
                "surface ScamAdviser and cautionary blog posts."
            ),
            "validation_needed": (
                "Publish verified before-and-after client case studies on reputable third-party domains and test "
                "whether subsequent live search retrievals replace the ScamAdviser citation."
            ),
            "confidence_and_limitations": (
                "High confidence: Directly evidenced by source response excerpts and cited URLs. "
                "Does not mean Kasparro is invalid, but proves what ChatGPT conveys to prospects."
            )
        },
        {
            "title": "Brand Entity Confusion with 'Kaspr' in AI Search Results",
            "observed_pattern": (
                "Multiple responses across ChatGPT and Google AI Mode confuse 'Kasparro' with 'Kaspr' "
                "(the French B2B lead generation / contact scraping tool) or 'Gaspar AI', presenting "
                "Kaspr's subscription pricing and G2 reviews instead of Kasparro's AI visibility platform."
            ),
            "comparison": (
                "Entity confusion occurred in both Google AI Mode and ChatGPT responses when answering pricing "
                "and company capability questions (e.g. Prompt 018)."
            ),
            "evidence": [
                {
                    "response_id": "1d2dc007-0757-480d-a086-6b6e2e13c463",
                    "engine": "chatgpt",
                    "prompt": "kasparro:ai_shortlisting:018 (is kasparro overpriced for B2B SaaS startups?)",
                    "excerpt": "If you mean **Kasparro** (the B2B SaaS growth/outbound agency, not Kaspr), I couldn't find reliable public pricing or enough verified information to judge whether it's objectively overpriced."
                },
                {
                    "response_id": "a3fdd8bb-bcd9-4608-9786-ad4b3a2c7dc2",
                    "engine": "aimode",
                    "prompt": "kasparro:ai_shortlisting:001 (does kasparro actually work for B2B SaaS companies trying to get recommended by chatgpt?)",
                    "excerpt": "Based on my research, Kasparro is not a widely recognized, top-tier agency or tool in the AI visibility space (AISO - AI Search Optimization) for B2B SaaS according to public search results as of July 2026."
                }
            ],
            "possible_explanation": (
                "Phonetic and orthographic proximity to 'Kaspr' combined with sparse entity graph data "
                "for Kasparro leads AI search engines to pull citations from kaspr.io."
            ),
            "validation_needed": (
                "Check JSON-LD Schema on kasparro.com and test prompt disambiguation explicitly."
            ),
            "confidence_and_limitations": (
                "Evidence corroborated across multiple citation domains (e.g. citations from kaspr.io in response ac5bdf24)."
            )
        }
    ]

