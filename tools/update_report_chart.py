import json
import os

base_dir = r"c:\Users\suriy\Downloads\Kasparro_AI_Engineer_Fresher_Assignment_Pack\Kasparro_AI_Engineer_Fresher"
html_path = os.path.join(base_dir, "evaluation", "results", "report.html")
scores_path = os.path.join(base_dir, "evaluation", "results", "prompt_scores.json")

with open(scores_path, "r", encoding="utf-8") as f:
    scores_data = json.load(f)

# Coordinates calculation
# SVG viewBox="0 0 1000 360"
# X: 50 to 970 (width 920, 50 points -> dx = 920/49 = 18.7755)
# Y: 40 to 310 (height 270, 0 to 100 -> y = 310 - (score / 100) * 270)
dx = 920.0 / 49.0

def get_coords(score_list):
    pts = []
    circles = []
    for i, item in enumerate(score_list):
        x = round(50.0 + i * dx, 1)
        y = round(310.0 - (item["score"] / 100.0) * 270.0, 1)
        pts.append(f"{x},{y}")
        circles.append((x, y, item))
    return " ".join(pts), circles

gem_pts, gem_circles = get_coords(scores_data["gemini"])
gpt_pts, gpt_circles = get_coords(scores_data["chatgpt"])
aim_pts, aim_circles = get_coords(scores_data["aimode"])

# Build circles SVG elements
def build_circles(circles, engine_name, color, engine_class):
    svg_circles = []
    for x, y, item in circles:
        p_idx = item["prompt_index"]
        score = item["score"]
        p_text = item["prompt_text"].replace('"', '&quot;').replace("'", "&#39;")
        m_txt = "Yes" if item["mentioned"] else "No"
        r_txt = "Yes" if item["recommended"] else "No"
        n_txt = "Yes (Caution)" if item["negative"] else "No"
        
        # Tooltip text
        title = f"{engine_name} · Prompt {p_idx:02d} · Score: {score}/100"
        body = (
            f"&quot;{p_text}&quot;<br><br>"
            f"• <strong>Mentioned:</strong> {m_txt}<br>"
            f"• <strong>Recommended:</strong> {r_txt}<br>"
            f"• <strong>Negative/Caution:</strong> {n_txt}"
        )
        meta_left = "Category: Branded" if p_idx <= 25 else "Category: Unbranded GEO"
        meta_right = f"Formula: {score} pts"
        
        c_tag = (
            f'<circle cx="{x}" cy="{y}" r="4.5" fill="{color}" stroke="#ffffff" stroke-width="1.5" '
            f'class="scatter-dot dot-{engine_class} dot-p{p_idx}" '
            f'data-prompt="{p_idx}" data-engine="{engine_class}" '
            f'data-hover-title="{title}" data-hover-body="{body}" '
            f'data-hover-meta-left="{meta_left}" data-hover-meta-right="{meta_right}">'
            f'</circle>'
        )
        svg_circles.append(c_tag)
    return "\n          ".join(svg_circles)

gem_svg_circles = build_circles(gem_circles, "🔮 Gemini", "#7c5cdb", "gemini")
gpt_svg_circles = build_circles(gpt_circles, "🤖 ChatGPT", "#0ea472", "chatgpt")
aim_svg_circles = build_circles(aim_circles, "🔍 AI Mode", "#3b82f6", "aimode")

scatter_svg = f"""
      <!-- SCATTER / LINE CHART CARD (Full-Width Benchmark View) -->
      <div class="chart-card reveal" id="scatterChartCard" style="display:none;margin-bottom:24px">
        <div class="chart-header">
          <div>
            <h3 id="scatterTitle">Prompt-by-Prompt Score Trajectory (50 Prompts)</h3>
            <div style="font-size:.76rem;color:var(--text-m)" id="scatterSubtitle">Comparing visibility score variance across prompts 01 to 50</div>
          </div>
          <div class="chart-legend">
            <div class="legend-item" style="cursor:pointer" onclick="filterByEngineCard('gemini')">
              <div class="legend-dot" style="background:var(--gem)"></div><span>🔮 Gemini</span>
            </div>
            <div class="legend-item" style="cursor:pointer" onclick="filterByEngineCard('chatgpt')">
              <div class="legend-dot" style="background:var(--gpt)"></div><span>🤖 ChatGPT</span>
            </div>
            <div class="legend-item" style="cursor:pointer" onclick="filterByEngineCard('aimode')">
              <div class="legend-dot" style="background:var(--aim)"></div><span>🔍 AI Mode</span>
            </div>
          </div>
        </div>

        <div style="width:100%;overflow-x:auto">
          <svg viewBox="0 0 1000 360" width="100%" height="360" style="overflow:visible;font-family:inherit" id="scatterSvg">
            <defs>
              <linearGradient id="brandedZoneGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stop-color="#4f6ef7" stop-opacity="0.08"/>
                <stop offset="100%" stop-color="#4f6ef7" stop-opacity="0.02"/>
              </linearGradient>
              <linearGradient id="unbrandedZoneGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stop-color="#e05c6b" stop-opacity="0.08"/>
                <stop offset="100%" stop-color="#e05c6b" stop-opacity="0.02"/>
              </linearGradient>
              <filter id="dotGlow" x="-50%" y="-50%" width="200%" height="200%">
                <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#111827" flood-opacity="0.18"/>
              </filter>
            </defs>

            <!-- Background Zone 1: Branded (P01-P25) -->
            <rect x="50" y="40" width="460" height="270" fill="url(#brandedZoneGrad)" rx="8" id="zoneBranded"/>
            <text x="60" y="58" fill="#4f6ef7" font-size="11" font-weight="700" letter-spacing="0.06em">ZONE 1: BRANDED QUERIES (P01–P25) · EXPLICIT INTENT</text>

            <!-- Background Zone 2: Unbranded Category (P26-P50) -->
            <rect x="510" y="40" width="460" height="270" fill="url(#unbrandedZoneGrad)" rx="8" id="zoneUnbranded"/>
            <text x="520" y="58" fill="#e05c6b" font-size="11" font-weight="700" letter-spacing="0.06em">ZONE 2: UNBRANDED CATEGORY (P26–P50) · 0% RECALL CLIFF</text>

            <!-- Dividing Cliff Line at P25.5 -->
            <line x1="510" y1="40" x2="510" y2="310" stroke="#e05c6b" stroke-width="1.8" stroke-dasharray="4,4" opacity="0.8"/>
            <text x="510" y="32" text-anchor="middle" fill="#e05c6b" font-size="10" font-weight="800">▼ DISCOVERY CLIFF</text>

            <!-- Y-Axis Gridlines & Labels -->
            <!-- 100 -->
            <line x1="50" y1="40" x2="970" y2="40" stroke="#e2e6f0" stroke-width="1"/>
            <text x="42" y="44" text-anchor="end" fill="#8891ab" font-size="11" font-weight="600">100</text>
            <!-- 75 -->
            <line x1="50" y1="107.5" x2="970" y2="107.5" stroke="#e2e6f0" stroke-width="1" stroke-dasharray="2,2"/>
            <text x="42" y="111.5" text-anchor="end" fill="#8891ab" font-size="11" font-weight="600">75</text>
            <!-- 50 -->
            <line x1="50" y1="175" x2="970" y2="175" stroke="#e2e6f0" stroke-width="1" stroke-dasharray="2,2"/>
            <text x="42" y="179" text-anchor="end" fill="#8891ab" font-size="11" font-weight="600">50</text>
            <!-- 25 -->
            <line x1="50" y1="242.5" x2="970" y2="242.5" stroke="#e2e6f0" stroke-width="1" stroke-dasharray="2,2"/>
            <text x="42" y="246.5" text-anchor="end" fill="#8891ab" font-size="11" font-weight="600">25</text>
            <!-- 12.5 Baseline Callout -->
            <line x1="50" y1="276.25" x2="970" y2="276.25" stroke="#e05c6b" stroke-width="1" stroke-dasharray="3,3" opacity="0.35"/>
            <text x="42" y="279" text-anchor="end" fill="#e05c6b" font-size="10" font-weight="700">12.5</text>
            <!-- 0 Axis -->
            <line x1="50" y1="310" x2="970" y2="310" stroke="#c8cedf" stroke-width="1.5"/>
            <text x="42" y="314" text-anchor="end" fill="#8891ab" font-size="11" font-weight="600">0</text>

            <!-- X-Axis Labels (Sample key prompts) -->
            <text x="50" y="332" text-anchor="middle" fill="#8891ab" font-size="10" font-weight="600">P01</text>
            <text x="143.9" y="332" text-anchor="middle" fill="#8891ab" font-size="10" font-weight="600">P06</text>
            <text x="237.8" y="332" text-anchor="middle" fill="#8891ab" font-size="10" font-weight="600">P11</text>
            <text x="331.6" y="332" text-anchor="middle" fill="#8891ab" font-size="10" font-weight="600">P16</text>
            <text x="425.5" y="332" text-anchor="middle" fill="#8891ab" font-size="10" font-weight="600">P21</text>
            <text x="500.6" y="332" text-anchor="middle" fill="#e05c6b" font-size="10" font-weight="800">P25</text>
            <text x="519.4" y="332" text-anchor="middle" fill="#e05c6b" font-size="10" font-weight="800">P26</text>
            <text x="613.3" y="332" text-anchor="middle" fill="#8891ab" font-size="10" font-weight="600">P31</text>
            <text x="707.1" y="332" text-anchor="middle" fill="#8891ab" font-size="10" font-weight="600">P36</text>
            <text x="801.0" y="332" text-anchor="middle" fill="#8891ab" font-size="10" font-weight="600">P41</text>
            <text x="894.9" y="332" text-anchor="middle" fill="#8891ab" font-size="10" font-weight="600">P46</text>
            <text x="970" y="332" text-anchor="middle" fill="#8891ab" font-size="10" font-weight="600">P50</text>

            <!-- Polylines (Trendlines) -->
            <polyline id="line-gemini" points="{gem_pts}" fill="none" stroke="#7c5cdb" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="scatter-line line-gemini"/>
            <polyline id="line-chatgpt" points="{gpt_pts}" fill="none" stroke="#0ea472" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="scatter-line line-chatgpt"/>
            <polyline id="line-aimode" points="{aim_pts}" fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="scatter-line line-aimode"/>

            <!-- Scatter Dots -->
            <!-- Gemini Dots -->
            <g id="dots-gemini" class="dot-group dot-group-gemini">
              {gem_svg_circles}
            </g>

            <!-- ChatGPT Dots -->
            <g id="dots-chatgpt" class="dot-group dot-group-chatgpt">
              {gpt_svg_circles}
            </g>

            <!-- AI Mode Dots -->
            <g id="dots-aimode" class="dot-group dot-group-aimode">
              {aim_svg_circles}
            </g>
          </svg>
        </div>

        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:14px;padding-top:12px;border-top:1px solid var(--border);font-size:.76rem;color:var(--text-p)">
          <div>💡 <strong>Interactive Hint:</strong> Hover over any dot to inspect the prompt query text, model verdict, and ScamAdviser warning flags.</div>
          <div><span style="color:#e05c6b;font-weight:700">Notice:</span> Flat 12.5 floor across P26–P50 represents the zero-mention unbranded cliff.</div>
        </div>
      </div>
"""

# Now let's inject this into report.html
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update View switcher buttons to make them clear
old_view_buttons = """      <div class="view-switcher">
        <button class="view-btn active" data-view="both">⚡ Split</button>
        <button class="view-btn" data-view="chart">📊 Chart</button>
        <button class="view-btn" data-view="table">📋 Table</button>
      </div>"""

new_view_buttons = """      <div class="view-switcher">
        <button class="view-btn active" data-view="both">⚡ Split View</button>
        <button class="view-btn" data-view="scatter">📈 Scatter Chart</button>
        <button class="view-btn" data-view="table">📋 Table</button>
      </div>"""

if old_view_buttons in html:
    html = html.replace(old_view_buttons, new_view_buttons)

# 2. Add scatter CSS
scatter_css = """
    /* ════════════════════════════════════════════════
       SCATTER / LINE CHART STYLING
    ════════════════════════════════════════════════ */
    .scatter-line{
      transition:opacity .35s ease, stroke-width .35s ease;
      cursor:pointer;
    }
    .scatter-dot{
      cursor:pointer;
      transition:r .2s cubic-bezier(.22,1,.36,1), fill .2s ease;
    }
    .scatter-dot:hover{
      r:8px !important;
      filter:url(#dotGlow);
    }
    .dot-group{
      transition:opacity .35s ease;
    }
    .dimmed-series{
      opacity:0.10 !important;
    }
    .highlight-series{
      opacity:1 !important;
      stroke-width:3.5px !important;
    }
"""

if "SCATTER / LINE CHART STYLING" not in html:
    html = html.replace("/* ════════════════════════════════════════════════\n       BENCHMARK CHARTS (ARENA STYLE)", scatter_css + "\n    /* ════════════════════════════════════════════════\n       BENCHMARK CHARTS (ARENA STYLE)")

# 3. Insert scatter_svg right before `<div class="benchmark-grid" id="benchmarkContainer">`
if 'id="scatterChartCard"' not in html:
    target_str = '<div class="benchmark-grid" id="benchmarkContainer">'
    html = html.replace(target_str, scatter_svg + "\n    " + target_str)

# 4. Update the JavaScript for View Switcher and Engine Filtering
new_js_logic = """
  /* ══════════════════════════════════════════
     ENGINE FOCUS & FILTERING (Chart + Table)
  ══════════════════════════════════════════ */
  function filterEngineFocus() {
    // 1. Table rows
    document.querySelectorAll('.interactive-row').forEach(row => {
      const eng = row.dataset.engine;
      if (currentEngine === 'all' || eng === currentEngine) {
        row.style.opacity = '1';
        row.classList.toggle('active', currentEngine !== 'all' && eng === currentEngine);
      } else {
        row.style.opacity = '0.35';
        row.classList.remove('active');
      }
    });

    // 2. Engine Cards
    document.querySelectorAll('.engine-card').forEach(card => {
      const isMatch = currentEngine === 'all' || card.classList.contains(currentEngine + '-card');
      card.classList.toggle('highlight', currentEngine !== 'all' && isMatch);
      card.style.opacity = isMatch ? '1' : '0.45';
    });

    // 3. Bar Chart Rows (Split View)
    ['gemini', 'chatgpt', 'aimode'].forEach(eng => {
      const shortCode = eng === 'gemini' ? 'gem' : (eng === 'chatgpt' ? 'gpt' : 'aim');
      const isMatch = currentEngine === 'all' || currentEngine === eng;
      ['score', 'inc', 'rec', 'neg'].forEach(metric => {
        const barRow = document.getElementById('bar-' + shortCode + '-' + metric)?.closest('.single-bar-row');
        if (barRow) {
          barRow.style.opacity = isMatch ? '1' : '0.22';
          barRow.style.transition = 'opacity 0.3s ease';
        }
      });
    });

    // 4. Scatter / Line Chart Polylines and Dot Groups
    ['gemini', 'chatgpt', 'aimode'].forEach(eng => {
      const line = document.getElementById('line-' + eng);
      const dotGroup = document.getElementById('dots-' + eng);
      const isMatch = currentEngine === 'all' || currentEngine === eng;

      if (line) {
        if (isMatch) {
          line.classList.remove('dimmed-series');
          if (currentEngine !== 'all') line.classList.add('highlight-series');
          else line.classList.remove('highlight-series');
        } else {
          line.classList.add('dimmed-series');
          line.classList.remove('highlight-series');
        }
      }

      if (dotGroup) {
        if (isMatch) {
          dotGroup.classList.remove('dimmed-series');
        } else {
          dotGroup.classList.add('dimmed-series');
        }
      }
    });
  }

  /* ══════════════════════════════════════════
     VIEW SWITCHER (Split / Scatter / Table)
  ══════════════════════════════════════════ */
  document.querySelectorAll('.view-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const view = btn.dataset.view;
      const chartCard = document.getElementById('chartCard');
      const gapCard = document.getElementById('gapCard');
      const tableCard = document.getElementById('tableCard');
      const benchGrid = document.getElementById('benchmarkContainer');
      const scatterCard = document.getElementById('scatterChartCard');

      if (view === 'scatter') {
        scatterCard.style.display = 'block';
        benchGrid.style.display = 'none';
        tableCard.style.display = 'none';
      } else if (view === 'table') {
        scatterCard.style.display = 'none';
        benchGrid.style.display = 'none';
        tableCard.style.display = 'block';
      } else { // both / split
        scatterCard.style.display = 'none';
        benchGrid.style.display = 'grid';
        chartCard.style.display = 'block';
        gapCard.style.display = 'block';
        tableCard.style.display = 'block';
      }
    });
  });

  /* ══════════════════════════════════════════
     UPDATE BENCHMARK VIEW ON SCOPE CHANGE
  ══════════════════════════════════════════ */
  function updateBenchmarkView() {
    const data = datasetMatrix[currentScope];

    // Update Subtitles & Labels
    const scopeNames = { all: 'All Prompts (50)', branded: 'Branded Queries (25)', unbranded: 'Unbranded Category (25)' };
    document.getElementById('chartSubtitle').textContent = `Showing ${scopeNames[currentScope]} across 3 engines`;
    document.getElementById('tableScopeIndicator').textContent = `SCOPE: ${scopeNames[currentScope].toUpperCase()}`;
    const scatterSub = document.getElementById('scatterSubtitle');
    if (scatterSub) scatterSub.textContent = `Showing ${scopeNames[currentScope]} prompt trajectory`;

    // Highlight zones in Scatter Chart
    const zoneB = document.getElementById('zoneBranded');
    const zoneU = document.getElementById('zoneUnbranded');
    if (zoneB && zoneU) {
      if (currentScope === 'branded') {
        zoneB.style.opacity = '1';
        zoneU.style.opacity = '0.15';
        document.querySelectorAll('.scatter-dot').forEach(d => {
          const p = parseInt(d.dataset.prompt);
          d.style.opacity = p <= 25 ? '1' : '0.15';
        });
      } else if (currentScope === 'unbranded') {
        zoneB.style.opacity = '0.15';
        zoneU.style.opacity = '1';
        document.querySelectorAll('.scatter-dot').forEach(d => {
          const p = parseInt(d.dataset.prompt);
          d.style.opacity = p > 25 ? '1' : '0.15';
        });
      } else {
        zoneB.style.opacity = '1';
        zoneU.style.opacity = '1';
        document.querySelectorAll('.scatter-dot').forEach(d => {
          d.style.opacity = '1';
        });
      }
    }

    // Update Chart Bar Widths & Values
    ['gem', 'gpt', 'aim'].forEach(eng => {
      const key = eng === 'gem' ? 'gemini' : (eng === 'gpt' ? 'chatgpt' : 'aimode');
      const d = data[key];

      setBar('bar-' + eng + '-score', d.score, d.score);
      setBar('bar-' + eng + '-inc', d.inc, d.inc + '%');
      setBar('bar-' + eng + '-rec', d.rec, d.rec + '%');
      setBar('bar-' + eng + '-neg', d.neg, d.neg + '%');

      document.getElementById('t-' + eng + '-score').textContent = d.score;
      document.getElementById('t-' + eng + '-inc').textContent = d.inc + '%';
      document.getElementById('t-' + eng + '-rec').textContent = d.rec + '%';
      document.getElementById('t-' + eng + '-neg').textContent = d.neg + '%';
      document.getElementById('t-' + eng + '-count').textContent = d.count;

      document.getElementById('t-' + eng + '-inc-bar').style.width = d.inc + '%';
      document.getElementById('t-' + eng + '-rec-bar').style.width = d.rec + '%';
      document.getElementById('t-' + eng + '-neg-bar').style.width = d.neg + '%';
    });

    const all = data.all;
    document.getElementById('t-all-score').textContent = all.score;
    document.getElementById('t-all-inc').textContent = all.inc + '%';
    document.getElementById('t-all-rec').textContent = all.rec + '%';
    document.getElementById('t-all-neg').textContent = all.neg + '%';
    document.getElementById('t-all-count').textContent = all.count;
    document.getElementById('t-all-inc-bar').style.width = all.inc + '%';
    document.getElementById('t-all-rec-bar').style.width = all.rec + '%';
    document.getElementById('t-all-neg-bar').style.width = all.neg + '%';

    const alertEl = document.getElementById('dynamicAlert');
    alertEl.className = 'dynamic-alert';
    if (data.alert.type === 'warning') alertEl.classList.add('alert-warning');
    if (data.alert.type === 'danger') alertEl.classList.add('alert-danger');
    document.getElementById('alertIcon').textContent = data.alert.icon;
    document.getElementById('alertTitle').textContent = data.alert.title;
    document.getElementById('alertDesc').innerHTML = data.alert.desc;

    // Re-apply engine focus in case scope changed
    filterEngineFocus();
  }
"""

# Replace the existing filterEngineFocus, view switcher, and updateBenchmarkView
import re
pattern = r"function filterEngineFocus\(\)\s*\{[\s\S]*?filterEngineFocus\(\);\s*\}"
if re.search(pattern, html):
    html = re.sub(pattern, new_js_logic.strip(), html)
else:
    # Fallback replace
    old_block_start = "function filterEngineFocus() {"
    old_block_end = "filterEngineFocus();\n  }"
    if old_block_start in html and old_block_end in html:
        start_idx = html.find(old_block_start)
        end_idx = html.find(old_block_end) + len(old_block_end)
        html = html[:start_idx] + new_js_logic.strip() + html[end_idx:]

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Updated report.html with Scatter Line Chart successfully!")

