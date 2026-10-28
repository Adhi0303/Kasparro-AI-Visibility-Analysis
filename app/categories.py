import re
from typing import Dict, Any

CATEGORY_VERSION = "v1"

CATEGORIES = [
    "brand_discovery",
    "vendor_comparison",
    "capability_evaluation",
    "trust_and_legitimacy",
    "pricing_and_implementation",
]


def categorize_prompt(prompt_text: str) -> str:
    """
    Categorizes a prompt into one of five documented categories (taxonomy v1):
    1. vendor_comparison
    2. trust_and_legitimacy
    3. pricing_and_implementation
    4. capability_evaluation
    5. brand_discovery
    """
    text = prompt_text.lower()

    # Vendor comparison: mentions competitor names or comparison words
    comparison_patterns = [
        r"\bbetter\s+than\b", r"\bcompare(d)?\s+to\b", r"\bvs\b", r"\bversus\b",
        r"\bprofound\b", r"\botterly\b", r"\bpeec\b", r"\bathenahq\b", r"\bdageno\b",
        r"\balternatives?\b", r"\bprefer\s+between\b"
    ]
    for pat in comparison_patterns:
        if re.search(pat, text):
            return "vendor_comparison"

    # Trust & Legitimacy: skepticism, scam, reviews, proof, hype
    trust_patterns = [
        r"\blegit\b", r"\bhype\b", r"\btrustworthy\b", r"\breal\s+(enterprise\s+)?users\s+say\b",
        r"\bviolat(e|ing)\b", r"\bterms\s+of\s+service\b", r"\bskeptical\b", r"\bempty\s+promises\b",
        r"\bgimmick\b", r"\bprompt\s+hacks?\b"
    ]
    for pat in trust_patterns:
        if re.search(pat, text):
            return "trust_and_legitimacy"

    # Pricing & Implementation: costs, retainers, onboarding, setup, self-serve, cancellation
    pricing_patterns = [
        r"\bcost\b", r"\bprice\b", r"\boverpriced\b", r"\bworth\s+(the\s+)?money\b",
        r"\bretainer\b", r"\bsetup\b", r"\bonboarding\b", r"\bcancel\b",
        r"\bself\s+serve\b", r"\bsign\s+up\b", r"\bhow\s+fast\b", r"\bfees\b"
    ]
    for pat in pricing_patterns:
        if re.search(pat, text):
            return "pricing_and_implementation"

    # Capability Evaluation: specific features, audit modules, technical mechanisms
    capability_patterns = [
        r"\bmodule\s+audit\b", r"\btrack\s+brand\b", r"\bmissing\s+any\s+major\b",
        r"\bfeatures?\b", r"\bseo\s+or\b", r"\binfluence\s+ai\b", r"\bwhy\s+isn't\s+my\b",
        r"\baudit\s+reports?\b", r"\bapi\s+integrations?\b", r"\bshow\s+up\s+more\b"
    ]
    for pat in capability_patterns:
        if re.search(pat, text):
            return "capability_evaluation"

    # Default fallback: brand / category discovery
    return "brand_discovery"

