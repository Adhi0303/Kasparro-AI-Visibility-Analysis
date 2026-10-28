import os

html_path = r"c:\Users\suriy\Downloads\Kasparro_AI_Engineer_Fresher_Assignment_Pack\Kasparro_AI_Engineer_Fresher\evaluation\results\report.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

checks = [
    ('id="scatterChartCard"', "Scatter chart card present"),
    ('data-view="scatter"', "Scatter view button present"),
    ('data-view="both"', "Split view button present"),
    ('class="scatter-dot dot-gemini', "Gemini scatter dots present"),
    ('class="scatter-dot dot-chatgpt', "ChatGPT scatter dots present"),
    ('class="scatter-dot dot-aimode', "AI Mode scatter dots present"),
    ('id="line-gemini"', "Gemini trendline present"),
    ('id="line-chatgpt"', "ChatGPT trendline present"),
    ('id="line-aimode"', "AI Mode trendline present"),
    ('ZONE 1: BRANDED QUERIES', "Zone 1 label present"),
    ('ZONE 2: UNBRANDED CATEGORY', "Zone 2 label present"),
    ('DISCOVERY CLIFF', "Discovery cliff label present"),
    ('function filterEngineFocus()', "filterEngineFocus JS function present"),
    ('function updateBenchmarkView()', "updateBenchmarkView JS function present"),
]

all_ok = True
for needle, desc in checks:
    present = needle in html
    status = "OK" if present else "FAIL"
    print(f"[{status}] {desc}")
    if not present:
        all_ok = False

print(f"HTML verification result: {'ALL PASSED' if all_ok else 'SOME CHECKS FAILED'}")
print(f"File size: {len(html)} bytes")

