#!/usr/bin/env python3
from __future__ import annotations

"""
Render the knowledge graph as interactive HTML. Visualization only — no analysis.

Contract:
  (no flags)  → reads graph/graph.json, writes graph/graph.html
  --open      → also opens graph.html in the default browser

Inputs:  graph/graph.json (produced by build_graph.py)
Outputs: graph/graph.html (self-contained vis.js page, no server needed)

No wiki file scanning, no NetworkX.

If this script fails:
  - FileNotFoundError on graph/graph.json → run build_graph.py first
  - Empty or malformed graph.json → re-run build_graph.py
  - graph/ directory missing → create it (mkdir graph)
  - Browser doesn't open (--open) → not critical, open graph.html manually
"""

import json
import argparse
import webbrowser
from pathlib import Path

from shared import REPO_ROOT, GRAPH_DIR, GRAPH_JSON, TYPE_COLORS, TYPE_COLORS_FADED

GRAPH_HTML = GRAPH_DIR / "graph.html"

LOGO_B64 = (REPO_ROOT / ".claude" / "logo-b64.txt").read_text(encoding="utf-8").strip() if (REPO_ROOT / ".claude" / "logo-b64.txt").exists() else ""


def render_html(nodes: list[dict], edges: list[dict], tag_filter: list[str] | None = None, built_date: str | None = None) -> str:
    """Generate self-contained vis.js HTML with JanusLM brand styling."""
    nodes_json = json.dumps(nodes, indent=2, ensure_ascii=False)
    edges_json = json.dumps(edges, indent=2, ensure_ascii=False)
    filter_json = json.dumps(tag_filter, ensure_ascii=False) if tag_filter else "null"

    legend_items = "".join(
        f'<button class="legend-dot" style="--dot-color:{color}" data-type="{t}" onclick="toggleTypeFilter(\'{t}\')">{t}</button>'
        for t, color in TYPE_COLORS.items() if t != "unknown"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>JanusLM — Knowledge Graph</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Urbanist:wght@400;500;600;700&family=Anybody:wght@400;600;700&family=Overpass+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  :root {{
    --bg: #FAFAF8;
    --bg-card: #FFFFFF;
    --text: #2A3439;
    --text-secondary: #6B7280;
    --border: rgba(229, 228, 226, 0.8);
    --accent: #D6B656;
    --accent-faded: rgba(214, 182, 86, 0.15);
    --edge-color: #B8B4AE;
    --label-color: #2A3439;
    --label-stroke: #FAFAF8;
    --node-deemph-alpha: 0.14;
    --font-deemph: rgba(42, 52, 57, 0.2);
    --code-bg: rgba(42, 52, 57, 0.06);
    --code-color: #8B5E3C;
    --quote-border: #D6B656;
    --wikilink-color: #7A6532;
    --chip-bg: rgba(42, 52, 57, 0.06);
    --chip-color: #2A3439;
    --chip-border: rgba(229, 228, 226, 0.6);
    --drawer-shadow: rgba(0, 0, 0, 0.08);
  }}

  body.dark {{
    --bg: #1a1a2e;
    --bg-card: rgba(10, 10, 30, 0.88);
    --text: #E8E8EC;
    --text-secondary: #9ea3b0;
    --border: rgba(255, 255, 255, 0.08);
    --accent: #D6B656;
    --accent-faded: rgba(214, 182, 86, 0.12);
    --edge-color: #5A574F;
    --label-color: #f2f3f8;
    --label-stroke: #1a1a2e;
    --node-deemph-alpha: 0.14;
    --font-deemph: rgba(242, 243, 248, 0.2);
    --code-bg: rgba(255, 255, 255, 0.06);
    --code-color: #ffde91;
    --quote-border: rgba(214, 182, 86, 0.7);
    --wikilink-color: #D6B656;
    --chip-bg: rgba(255, 255, 255, 0.08);
    --chip-color: #f1f2f7;
    --chip-border: rgba(255, 255, 255, 0.08);
    --drawer-shadow: rgba(0, 0, 0, 0.35);
  }}

  * {{ box-sizing: border-box; }}

  body {{
    margin: 0;
    background: var(--bg);
    font-family: 'Urbanist', system-ui, sans-serif;
    color: var(--text);
    transition: background 0.3s, color 0.3s;
  }}

  #header {{
    position: fixed; top: 0; left: 0; right: 0; z-index: 15;
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 20px;
    background: var(--bg-card);
    border-bottom: 1px solid var(--border);
    backdrop-filter: blur(10px);
  }}

  #header-left {{
    display: flex; align-items: center; gap: 10px;
  }}

  #header-logo {{
    height: 38px; width: auto;
  }}

  #header .brand {{
    font-family: 'Anybody', 'Urbanist', serif;
    font-weight: 700; font-size: 17px; letter-spacing: -0.3px;
  }}

  #header .separator {{
    color: var(--border); font-weight: 300; font-size: 18px; margin: 0 2px;
  }}

  #header .title {{
    font-family: 'Urbanist', sans-serif;
    font-weight: 500; font-size: 14px; color: var(--text-secondary);
    letter-spacing: 0.2px;
  }}
  .built-date {{
    font-family: 'Overpass Mono', monospace;
    font-weight: 400; font-size: 11px; color: var(--text-secondary); opacity: 0.6;
    margin-left: 16px; letter-spacing: 0.3px;
  }}

  #header-right {{
    display: flex; align-items: center; gap: 12px;
  }}

  #theme-toggle {{
    background: var(--chip-bg); border: 1px solid var(--border);
    color: var(--text); cursor: pointer; border-radius: 8px;
    width: 36px; height: 36px; font-size: 16px;
    display: flex; align-items: center; justify-content: center;
    transition: background 0.2s;
  }}
  #theme-toggle:hover {{ background: var(--accent-faded); }}

  .legend {{
    display: flex; align-items: center; gap: 18px;
  }}

  .legend-dot {{
    display: flex; align-items: center; gap: 7px;
    font-size: 14px; font-weight: 600; color: var(--text-secondary);
    text-transform: capitalize;
    background: none; border: none; cursor: pointer;
    padding: 4px 8px; border-radius: 6px;
    font-family: 'Urbanist', sans-serif;
    transition: opacity 0.15s, background 0.15s;
  }}
  .legend-dot:hover {{ background: var(--accent-faded); }}
  .legend-dot.dimmed {{ opacity: 0.35; }}

  .legend-dot::before {{
    content: ''; display: inline-block;
    width: 14px; height: 14px; border-radius: 50%;
    background: var(--dot-color);
    box-shadow: 0 0 0 2px var(--bg), 0 0 0 3px var(--dot-color);
  }}

  #graph {{ width: 100vw; height: 100vh; padding-top: 52px; }}
  #graph.dragging, #graph.dragging canvas {{ cursor: grabbing !important; }}

  #controls {{
    position: fixed; top: 62px; left: 12px;
    background: var(--bg-card);
    padding: 14px 16px; border-radius: 10px; z-index: 10; max-width: 340px;
    backdrop-filter: blur(8px); border: 1px solid var(--border);
    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
  }}

  #search-wrap {{
    display: flex; align-items: stretch; gap: 0;
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 8px; transition: border-color 0.2s;
    overflow: hidden;
  }}
  #search-wrap:focus-within {{ border-color: var(--accent); }}

  #search {{
    flex: 1; padding: 10px 14px;
    background: transparent; color: var(--text);
    border: none;
    font-size: 15px; font-family: 'Urbanist', sans-serif;
    outline: none;
  }}
  #search::placeholder {{ color: var(--text-secondary); }}

  #content-toggle {{
    background: transparent; border: none; border-left: 1px solid var(--border);
    color: var(--text-secondary); cursor: pointer;
    padding: 0 10px; display: flex; align-items: center; justify-content: center;
    transition: background 0.15s, color 0.15s;
  }}
  #content-toggle:hover {{ background: var(--accent-faded); color: var(--text); }}
  #content-toggle.active {{
    background: var(--accent); color: #fff;
  }}
  body.dark #content-toggle.active {{ color: #1a1a2e; }}

  #search-options {{
    display: flex; align-items: center; gap: 10px;
    margin: 5px 0 0; font-size: 12px; min-height: 18px;
  }}

  #content-hint {{
    font-size: 11px; color: var(--text-secondary);
    font-family: 'Urbanist', sans-serif; font-style: italic;
  }}

  #match-count {{
    font-family: 'Overpass Mono', monospace;
    font-size: 11px; color: var(--accent); font-weight: 600;
    margin-left: auto; white-space: nowrap;
  }}

  #tag-filter {{
    display: flex; flex-wrap: wrap; gap: 5px;
    margin: 10px 0 0; max-height: 90px; overflow-y: auto;
  }}

  .tag-chip {{
    background: var(--chip-bg); color: var(--chip-color);
    border: 1px solid var(--chip-border);
    border-radius: 999px; font-size: 11px; padding: 3px 10px;
    cursor: pointer; font-family: 'Urbanist', sans-serif;
    font-weight: 500; transition: all 0.15s; user-select: none;
  }}
  .tag-chip:hover {{
    background: var(--accent-faded); border-color: var(--accent);
  }}
  .tag-chip.active {{
    background: var(--accent); color: #fff;
    border-color: var(--accent); font-weight: 600;
  }}
  body.dark .tag-chip.active {{
    color: #1a1a2e;
  }}

  #spacing-bar {{
    position: fixed; bottom: 12px; right: 12px;
    display: flex; align-items: center; gap: 10px;
    background: var(--bg-card); padding: 8px 14px;
    border-radius: 8px; border: 1px solid var(--border);
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    z-index: 10;
  }}
  #spacing-bar label {{
    font-size: 12px; font-weight: 600; color: var(--text-secondary);
    font-family: 'Urbanist', sans-serif; white-space: nowrap;
  }}
  #spacing-slider {{
    width: 120px; height: 4px; accent-color: var(--accent);
    cursor: pointer;
  }}

  #controls .hint {{
    margin: 8px 0 0; font-size: 11px; color: var(--text-secondary); line-height: 1.5;
  }}

  #drawer {{
    position: fixed; top: 0; right: 0;
    width: clamp(480px, 33vw, 720px); max-width: 100vw; height: 100vh;
    background: var(--bg-card);
    border-left: 1px solid var(--border);
    box-shadow: -12px 0 32px var(--drawer-shadow);
    z-index: 20; display: none; flex-direction: column;
    backdrop-filter: blur(10px);
  }}
  #drawer.open {{ display: flex; }}

  #drawer-header {{
    padding: 18px 18px 12px;
    border-bottom: 1px solid var(--border);
  }}

  #drawer-topline {{
    display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
  }}

  #drawer-title {{
    margin: 0; font-size: 20px; line-height: 1.2;
    font-family: 'Anybody', 'Urbanist', serif; font-weight: 600;
  }}

  #drawer-close {{
    background: transparent; color: var(--text-secondary);
    border: 0; font-size: 22px; line-height: 1;
    cursor: pointer; padding: 2px 6px; border-radius: 6px;
    transition: background 0.15s;
  }}
  #drawer-close:hover {{ background: var(--chip-bg); }}

  #drawer-meta {{
    margin-top: 8px; font-size: 12px; color: var(--text-secondary);
    font-family: 'Overpass Mono', monospace;
  }}

  #drawer-path {{
    margin-top: 5px; font-size: 12px; color: var(--text-secondary);
    opacity: 0.7; word-break: break-all;
    font-family: 'Overpass Mono', monospace;
  }}

  #drawer-preview {{
    margin-top: 10px; font-size: 13px; color: var(--text);
    line-height: 1.6; opacity: 0.85;
  }}

  #drawer-related {{
    padding: 12px 18px 0; font-size: 12px; color: var(--text-secondary);
    font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
  }}

  #drawer-related-list {{
    display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px;
  }}

  .related-chip {{
    background: var(--chip-bg); color: var(--chip-color);
    border: 1px solid var(--chip-border);
    border-radius: 999px; font-size: 12px; padding: 4px 10px;
    cursor: pointer; font-family: 'Urbanist', sans-serif;
    transition: background 0.15s, border-color 0.15s;
  }}
  .related-chip:hover {{
    background: var(--accent-faded); border-color: var(--accent);
  }}

  #drawer-content {{
    flex: 1; min-height: 0; padding: 14px 18px 18px; overflow: auto;
  }}

  #drawer-markdown {{
    color: var(--text); font-size: 13px; line-height: 1.72;
  }}
  #drawer-markdown h1, #drawer-markdown h2, #drawer-markdown h3,
  #drawer-markdown h4, #drawer-markdown h5, #drawer-markdown h6 {{
    margin: 1.2em 0 0.55em; line-height: 1.3;
    font-family: 'Anybody', 'Urbanist', serif;
  }}
  #drawer-markdown h1 {{ font-size: 22px; }}
  #drawer-markdown h2 {{ font-size: 18px; }}
  #drawer-markdown h3 {{ font-size: 15px; }}
  #drawer-markdown p {{ margin: 0 0 0.95em; }}
  #drawer-markdown ul, #drawer-markdown ol {{ margin: 0 0 1em 1.35em; padding: 0; }}
  #drawer-markdown li {{ margin: 0.35em 0; }}
  #drawer-markdown hr {{ border: 0; border-top: 1px solid var(--border); margin: 1.2em 0; }}
  #drawer-markdown blockquote {{
    margin: 0 0 1em; padding: 0.85em 1em;
    border-left: 3px solid var(--quote-border);
    background: var(--code-bg); border-radius: 0 8px 8px 0;
  }}
  #drawer-markdown pre {{
    margin: 0 0 1em; white-space: pre-wrap; word-break: break-word; line-height: 1.55;
    font-size: 12px; background: var(--code-bg);
    border: 1px solid var(--border); border-radius: 8px; padding: 14px;
    font-family: 'Overpass Mono', ui-monospace, monospace;
  }}
  #drawer-markdown code {{
    font-family: 'Overpass Mono', ui-monospace, monospace;
    font-size: 0.9em; background: var(--code-bg); padding: 0.15em 0.35em;
    border-radius: 5px; color: var(--code-color);
  }}
  #drawer-markdown pre code {{ background: transparent; padding: 0; color: inherit; border-radius: 0; }}
  #drawer-markdown .wikilink {{ color: var(--wikilink-color); font-weight: 600; }}

  @media (max-width: 960px) {{
    #drawer {{ width: 100vw; }}
  }}

  #stats {{
    position: fixed; bottom: 12px; left: 12px;
    background: var(--bg-card);
    padding: 8px 14px; border-radius: 8px;
    font-size: 12px; font-family: 'Overpass Mono', monospace;
    color: var(--text-secondary);
    border: 1px solid var(--border);
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  }}

  #stats-toggle {{
    display: flex; align-items: center; gap: 6px;
    width: 100%; margin-top: 10px; padding: 8px 0 0;
    border: none; background: none; cursor: pointer;
    font-size: 12px; font-family: 'Urbanist', sans-serif;
    color: var(--text-secondary); font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.3px;
    border-top: 1px solid var(--border);
  }}
  #stats-toggle:hover {{ color: var(--accent); }}
  #stats-toggle .arrow {{
    transition: transform 0.2s;
    font-size: 10px; display: inline-block;
  }}
  #stats-toggle.open .arrow {{ transform: rotate(90deg); }}

  #stats-content {{
    max-height: 0; overflow: hidden;
    transition: max-height 0.3s ease;
  }}
  #stats-content.open {{ max-height: 500px; }}

  .stat-row {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 5px 0; font-size: 13px;
  }}
  .stat-label {{ color: var(--text-secondary); }}
  .stat-value {{
    font-weight: 600;
    font-family: 'Overpass Mono', monospace; font-size: 12px;
  }}

  .stat-health {{
    display: inline-block; padding: 2px 8px;
    border-radius: 999px; font-size: 11px; font-weight: 600;
  }}
  .stat-health.healthy {{ background: rgba(34,197,94,0.12); color: #16a34a; }}
  .stat-health.warning {{ background: rgba(234,179,8,0.15); color: #a16207; }}
  .stat-health.critical {{ background: rgba(239,68,68,0.12); color: #dc2626; }}

  body.dark .stat-health.healthy {{ background: rgba(34,197,94,0.18); color: #4ade80; }}
  body.dark .stat-health.warning {{ background: rgba(234,179,8,0.18); color: #facc15; }}
  body.dark .stat-health.critical {{ background: rgba(239,68,68,0.18); color: #f87171; }}

  .stat-divider {{ border: none; border-top: 1px solid var(--border); margin: 6px 0; }}
</style>
</head>
<body>
<div id="header">
  <div id="header-left">
    {"<img id=" + '"header-logo" src="data:image/png;base64,' + LOGO_B64 + '" alt="JanusLM">' if LOGO_B64 else ""}
    <span class="brand">JanusLM</span>
    <span class="separator">|</span>
    <span class="title">Knowledge graph{" — filtered" if tag_filter else ""}</span>
    {f'<span class="built-date">Report date: {built_date}</span>' if built_date else ""}
  </div>
  <div id="header-right">
    <div class="legend">{legend_items}</div>
    <button id="theme-toggle" onclick="toggleTheme()" aria-label="Toggle theme"></button>
  </div>
</div>
<div id="controls">
  <div id="search-wrap">
    <input id="search" type="text" placeholder="Search by name..." oninput="onSearchInput()">
    <button id="content-toggle" onclick="toggleContentSearch()" aria-label="Toggle content search" title="Search inside page content"><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="1" width="12" height="14" rx="1.5"/><line x1="5" y1="4.5" x2="11" y2="4.5"/><line x1="5" y1="7.5" x2="11" y2="7.5"/><line x1="5" y1="10.5" x2="8.5" y2="10.5"/></svg></button>
  </div>
  <div id="search-options">
    <span id="content-hint"></span>
    <span id="match-count"></span>
  </div>
  <input type="checkbox" id="content-search" hidden>
  <div id="tag-filter"></div>
  <p class="hint">Click a node to explore. Toggle tags to filter.</p>
  <button id="stats-toggle" onclick="toggleStats()">
    <span class="arrow">&#9654;</span> Graph Insights
  </button>
  <div id="stats-content">
    <div id="stats-body"></div>
  </div>
</div>
<div id="graph"></div>
<aside id="drawer">
  <div id="drawer-header">
    <div id="drawer-topline">
      <h2 id="drawer-title"></h2>
      <button id="drawer-close" onclick="clearSelection()" aria-label="Close drawer">&times;</button>
    </div>
    <div id="drawer-meta"></div>
    <div id="drawer-path"></div>
    <div id="drawer-preview"></div>
  </div>
  <div id="drawer-related">
    Related nodes
    <div id="drawer-related-list"></div>
  </div>
  <div id="drawer-content">
    <div id="drawer-markdown"></div>
  </div>
</aside>
<div id="spacing-bar">
  <label for="spacing-slider">Spacing</label>
  <input id="spacing-slider" type="range" min="0" max="100" value="50" oninput="updateSpacing(this.value)">
</div>
<div id="stats"></div>
<script>
const originalNodes = {nodes_json};
const originalEdges = {edges_json};
const graphFilter = {filter_json};
const nodes = new vis.DataSet(originalNodes);
const edges = new vis.DataSet(originalEdges);
const adjacency = new Map();
const searchInput = document.getElementById("search");
const contentSearchCb = document.getElementById("content-search");
const matchCountEl = document.getElementById("match-count");
const tagFilterEl = document.getElementById("tag-filter");
const stats = document.getElementById("stats");
const nodeMap = new Map(originalNodes.map(node => [node.id, node]));
let activeNodeId = null;
let activeTags = new Set();
let activeTypes = new Set();

function isDark() {{ return document.body.classList.contains("dark"); }}

function toggleTheme() {{
  document.body.classList.toggle("dark");
  const dark = isDark();
  localStorage.setItem("janus-graph-theme", dark ? "dark" : "light");
  document.getElementById("theme-toggle").textContent = dark ? "\\u2600" : "\\u263E";
  updateNetworkColors();
}}

(function initTheme() {{
  const saved = localStorage.getItem("janus-graph-theme");
  if (saved === "dark") document.body.classList.add("dark");
  document.getElementById("theme-toggle").textContent = isDark() ? "\\u2600" : "\\u263E";
}})();

function updateNetworkColors() {{
  if (typeof network === "undefined") return;
  const dark = isDark();
  network.setOptions({{
    nodes: {{
      font: {{
        color: dark ? "#f2f3f8" : "#2A3439",
        strokeColor: dark ? "#1a1a2e" : "#FAFAF8",
      }},
    }},
  }});
  applyFilters();
}}

function fuzzyMatch(query, text) {{
  const q = query.toLowerCase();
  const t = text.toLowerCase();
  if (!q) return {{ match: true, score: 0 }};
  if (t.includes(q)) return {{ match: true, score: 1000 - t.indexOf(q) }};
  let qi = 0, score = 0, lastPos = -1;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {{
    if (t[ti] === q[qi]) {{
      score += (lastPos === ti - 1) ? 15 : 5;
      if (ti === 0 || /[\\s_\\x2d./]/.test(t[ti - 1])) score += 10;
      lastPos = ti;
      qi++;
    }}
  }}
  if (qi < q.length) return {{ match: false, score: 0 }};
  return {{ match: true, score }};
}}

function buildTagChips() {{
  const allTags = new Set();
  originalNodes.forEach(n => (n.tags || []).forEach(t => allTags.add(t)));
  const sorted = [...allTags].sort();

  tagFilterEl.innerHTML = "";
  const allChip = document.createElement("button");
  allChip.className = "tag-chip active";
  allChip.textContent = "All";
  allChip.dataset.tag = "__all__";
  allChip.onclick = () => {{
    activeTags.clear();
    tagFilterEl.querySelectorAll(".tag-chip").forEach(c => {{
      c.classList.toggle("active", c.dataset.tag === "__all__");
    }});
    applyFilters();
  }};
  tagFilterEl.appendChild(allChip);

  for (const tag of sorted) {{
    const chip = document.createElement("button");
    chip.className = "tag-chip";
    chip.textContent = tag;
    chip.dataset.tag = tag;
    chip.onclick = () => {{
      if (activeTags.has(tag)) activeTags.delete(tag);
      else activeTags.add(tag);
      tagFilterEl.querySelectorAll(".tag-chip").forEach(c => {{
        if (c.dataset.tag === "__all__") c.classList.toggle("active", activeTags.size === 0);
        else c.classList.toggle("active", activeTags.has(c.dataset.tag));
      }});
      applyFilters();
    }};
    tagFilterEl.appendChild(chip);
  }}
}}

function toggleTypeFilter(type) {{
  if (activeTypes.has(type)) activeTypes.delete(type);
  else activeTypes.add(type);
  document.querySelectorAll(".legend-dot").forEach(el => {{
    el.classList.toggle("dimmed", activeTypes.size > 0 && !activeTypes.has(el.dataset.type));
  }});
  applyFilters();
}}

function toggleContentSearch() {{
  const cb = contentSearchCb;
  cb.checked = !cb.checked;
  const btn = document.getElementById("content-toggle");
  const hint = document.getElementById("content-hint");
  btn.classList.toggle("active", cb.checked);
  searchInput.placeholder = cb.checked ? "Search in page content..." : "Search by name...";
  hint.textContent = cb.checked ? "Searching names + page content" : "";
  applyFilters();
  searchInput.focus();
}}

function onSearchInput() {{
  applyFilters(searchInput.value, activeNodeId);
}}

function contrastRing(color) {{
  if (!color) return "#5BA4E6";
  const hex = color.replace("#", "");
  const v = hex.length === 3
    ? hex.split("").map(c => c + c).join("")
    : hex;
  const n = Number.parseInt(v, 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.45 ? "#2D6ACA" : "#5BA4E6";
}}

function hexToRgba(color, alpha) {{
  if (!color) return `rgba(255, 255, 255, ${{alpha}})`;
  const normalized = color.replace("#", "");
  const value = normalized.length === 3
    ? normalized.split("").map(ch => ch + ch).join("")
    : normalized;
  const intValue = Number.parseInt(value, 16);
  const r = (intValue >> 16) & 255;
  const g = (intValue >> 8) & 255;
  const b = intValue & 255;
  return `rgba(${{r}}, ${{g}}, ${{b}}, ${{alpha}})`;
}}

function escapeHtml(text) {{
  return (text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}}

function stripFrontmatter(markdown) {{
  return (markdown || "").replace(/^---\\n[\\s\\S]*?\\n---\\n?/, "");
}}

function renderInlineMarkdown(text) {{
  let html = escapeHtml(text);
  html = html.replace(/\\[\\[([^\\]]+)\\]\\]/g, '<span class="wikilink">[[$1]]</span>');
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\\*\\*([^*]+)\\*\\*/g, "<strong>$1</strong>");
  html = html.replace(/\\*([^*]+)\\*/g, "<em>$1</em>");
  return html;
}}

function renderMarkdown(markdown) {{
  const lines = stripFrontmatter(markdown).split(/\\r?\\n/);
  const html = [];
  let paragraph = [];
  let listType = null;
  let listItems = [];
  let quoteLines = [];
  let inCodeBlock = false;
  let codeLines = [];

  function flushParagraph() {{
    if (!paragraph.length) return;
    html.push(`<p>${{renderInlineMarkdown(paragraph.join(" "))}}</p>`);
    paragraph = [];
  }}

  function flushList() {{
    if (!listType || !listItems.length) return;
    const items = listItems.map(item => `<li>${{renderInlineMarkdown(item)}}</li>`).join("");
    html.push(`<${{listType}}>${{items}}</${{listType}}>`);
    listType = null;
    listItems = [];
  }}

  function flushQuote() {{
    if (!quoteLines.length) return;
    html.push(`<blockquote>${{quoteLines.map(line => renderInlineMarkdown(line)).join("<br>")}}</blockquote>`);
    quoteLines = [];
  }}

  function flushCode() {{
    if (!codeLines.length) {{
      html.push("<pre><code></code></pre>");
      return;
    }}
    html.push(`<pre><code>${{escapeHtml(codeLines.join("\\n"))}}</code></pre>`);
    codeLines = [];
  }}

  for (const rawLine of lines) {{
    const line = rawLine.replace(/\\t/g, "    ");
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {{
      flushParagraph();
      flushList();
      flushQuote();
      if (inCodeBlock) {{
        flushCode();
        inCodeBlock = false;
      }} else {{
        inCodeBlock = true;
      }}
      continue;
    }}

    if (inCodeBlock) {{
      codeLines.push(rawLine);
      continue;
    }}

    if (!trimmed) {{
      flushParagraph();
      flushList();
      flushQuote();
      continue;
    }}

    const headingMatch = trimmed.match(/^(#{{1,6}})\\s+(.+)$/);
    if (headingMatch) {{
      flushParagraph();
      flushList();
      flushQuote();
      const level = headingMatch[1].length;
      html.push(`<h${{level}}>${{renderInlineMarkdown(headingMatch[2])}}</h${{level}}>`);
      continue;
    }}

    if (/^(-{{3,}}|\\*{{3,}})$/.test(trimmed)) {{
      flushParagraph();
      flushList();
      flushQuote();
      html.push("<hr>");
      continue;
    }}

    const quoteMatch = trimmed.match(/^>\\s?(.*)$/);
    if (quoteMatch) {{
      flushParagraph();
      flushList();
      quoteLines.push(quoteMatch[1]);
      continue;
    }}
    flushQuote();

    const unorderedMatch = trimmed.match(/^[-*]\\s+(.+)$/);
    if (unorderedMatch) {{
      flushParagraph();
      if (listType && listType !== "ul") flushList();
      listType = "ul";
      listItems.push(unorderedMatch[1]);
      continue;
    }}

    const orderedMatch = trimmed.match(/^\\d+\\.\\s+(.+)$/);
    if (orderedMatch) {{
      flushParagraph();
      if (listType && listType !== "ol") flushList();
      listType = "ol";
      listItems.push(orderedMatch[1]);
      continue;
    }}

    flushList();
    paragraph.push(trimmed);
  }}

  if (inCodeBlock) flushCode();
  flushParagraph();
  flushList();
  flushQuote();
  return html.join("");
}}

function rebuildAdjacency() {{
  adjacency.clear();
  for (const node of originalNodes) {{
    adjacency.set(node.id, new Set());
  }}
  for (const edge of originalEdges) {{
    if (!adjacency.has(edge.from)) adjacency.set(edge.from, new Set());
    if (!adjacency.has(edge.to)) adjacency.set(edge.to, new Set());
    adjacency.get(edge.from).add(edge.to);
    adjacency.get(edge.to).add(edge.from);
  }}
}}

function closeDrawer() {{
  document.getElementById("drawer").classList.remove("open");
}}

function openDrawer(node, relatedIds) {{
  document.getElementById("drawer").classList.add("open");
  document.getElementById("drawer-title").textContent = node.label;
  const communityText = Number.isInteger(node.group) && node.group >= 0 ? ` · community ${{node.group}}` : "";
  const tagsText = (node.tags || []).length ? ` · ${{node.tags.join(", ")}}` : "";
  document.getElementById("drawer-meta").textContent = `${{node.type}}${{communityText}}${{tagsText}}`;
  document.getElementById("drawer-path").textContent = node.path;
  document.getElementById("drawer-preview").textContent = node.preview || "";
  document.getElementById("drawer-markdown").innerHTML = renderMarkdown(node.markdown || "");

  const relatedList = document.getElementById("drawer-related-list");
  relatedList.innerHTML = "";
  const relatedNodes = originalNodes
    .filter(item => relatedIds.has(item.id) && item.id !== node.id)
    .sort((a, b) => a.label.localeCompare(b.label));

  if (relatedNodes.length === 0) {{
    const empty = document.createElement("span");
    empty.textContent = "No directly connected nodes";
    empty.style.color = "var(--text-secondary)";
    relatedList.appendChild(empty);
    return;
  }}

  for (const related of relatedNodes) {{
    const chip = document.createElement("button");
    chip.className = "related-chip";
    chip.textContent = related.label;
    chip.onclick = () => focusNode(related.id);
    relatedList.appendChild(chip);
  }}
}}

function clearSelection() {{
  activeNodeId = null;
  closeDrawer();
  applyFilters(searchInput.value, null);
}}

function applyFilters(query = searchInput.value, selectedNodeId = activeNodeId) {{
  const q = (query || "").trim();
  const dark = isDark();
  const searchContent = contentSearchCb.checked;

  const relatedIds = selectedNodeId
    ? new Set([selectedNodeId, ...(adjacency.get(selectedNodeId) || [])])
    : null;

  let matchCount = 0;
  const hasQuery = q.length > 0;
  const hasTagFilter = activeTags.size > 0;
  const hasTypeFilter = activeTypes.size > 0;

  const nodeMatchScores = new Map();
  originalNodes.forEach(node => {{
    let matchesSearch = true;
    let score = 0;
    if (hasQuery) {{
      const labelResult = fuzzyMatch(q, node.label);
      if (labelResult.match) {{
        score = labelResult.score;
      }} else if (searchContent) {{
        const plain = (node.markdown || "").replace(/^---\\n[\\s\\S]*?\\n---\\n?/, "").toLowerCase();
        if (plain.includes(q.toLowerCase())) {{
          score = 1;
        }} else {{
          matchesSearch = false;
        }}
      }} else {{
        matchesSearch = false;
      }}
    }}

    let matchesTag = true;
    if (hasTagFilter) {{
      const nodeTags = new Set(node.tags || []);
      matchesTag = [...activeTags].some(t => nodeTags.has(t));
    }}

    let matchesType = true;
    if (hasTypeFilter) {{
      matchesType = activeTypes.has(node.type);
    }}

    const matches = matchesSearch && matchesTag && matchesType;
    if (matches) matchCount++;
    nodeMatchScores.set(node.id, {{ matches, score }});
  }});

  const nodeUpdates = originalNodes.map(node => {{
    const {{ matches }} = nodeMatchScores.get(node.id);
    const isActive = selectedNodeId === node.id;
    const isRelated = !relatedIds || relatedIds.has(node.id);
    const emphasized = matches && isRelated;

    const ring = contrastRing(node.color);

    return {{
      id: node.id,
      hidden: false,
      color: {{
        background: isActive ? node.color : (emphasized ? node.color : hexToRgba(node.color, 0.14)),
        border: isActive ? ring : (emphasized ? hexToRgba(node.color, 0.96) : hexToRgba(node.color, 0.22)),
        highlight: {{ background: node.color, border: ring }},
        hover: {{ background: node.color, border: hexToRgba(node.color, 1) }},
      }},
      font: {{
        color: (isActive || emphasized)
          ? (dark ? "#f2f3f8" : "#2A3439")
          : (dark ? "rgba(242,243,248,0.2)" : "rgba(42,52,57,0.2)"),
        strokeColor: dark ? "#1a1a2e" : "#FAFAF8",
      }},
      borderWidth: isActive ? 5 : 1.5,
      size: isActive ? 18 : 12,
      shadow: isActive
        ? {{ enabled: true, color: hexToRgba(ring, 0.4), size: 16 }}
        : {{ enabled: false }},
    }};
  }});

  const nodeMatchSet = new Set(
    originalNodes.filter(n => nodeMatchScores.get(n.id).matches).map(n => n.id)
  );

  const edgeUpdates = originalEdges.map(edge => {{
    const bothMatch = nodeMatchSet.has(edge.from) && nodeMatchSet.has(edge.to);
    const eitherMatch = nodeMatchSet.has(edge.from) || nodeMatchSet.has(edge.to);
    const isRelated = !relatedIds || relatedIds.has(edge.from) || relatedIds.has(edge.to);
    const touchesActive = !!selectedNodeId && (edge.from === selectedNodeId || edge.to === selectedNodeId);
    const anyFilter = hasQuery || hasTagFilter || hasTypeFilter;
    const emphasized = anyFilter ? (bothMatch && isRelated) : isRelated;

    return {{
      id: edge.id,
      hidden: false,
      width: touchesActive ? 2.5 : emphasized ? 0.8 : 0.4,
      color: emphasized ? hexToRgba(edge.color, 0.45) : hexToRgba(edge.color, 0.08),
    }};
  }});

  nodes.update(nodeUpdates);
  edges.update(edgeUpdates);

  if (selectedNodeId) {{
    const activeNode = nodeMap.get(selectedNodeId);
    if (activeNode) {{
      openDrawer(activeNode, relatedIds || new Set([selectedNodeId]));
    }}
  }}

  if (hasQuery || hasTagFilter || hasTypeFilter) {{
    matchCountEl.textContent = `${{matchCount}}/${{originalNodes.length}}`;
  }} else {{
    matchCountEl.textContent = "";
  }}

  const focusSuffix = selectedNodeId && nodeMap.get(selectedNodeId)
    ? ` | ${{nodeMap.get(selectedNodeId).label}}`
    : "";
  stats.textContent = `${{originalNodes.length}} nodes / ${{originalEdges.length}} edges${{focusSuffix}}`;
}}

const container = document.getElementById("graph");

const nodeCount = originalNodes.length;
const gravConst = nodeCount > 80 ? -12000 : nodeCount > 30 ? -8000 : -5000;
const springLen = nodeCount > 80 ? 350 : nodeCount > 30 ? 280 : 220;

const dark = isDark();
const network = new vis.Network(container, {{ nodes, edges }}, {{
  nodes: {{
    shape: "dot",
    font: {{
      face: "Urbanist, system-ui, sans-serif",
      color: dark ? "#f2f3f8" : "#2A3439",
      size: 12,
      strokeWidth: 3,
      strokeColor: dark ? "#1a1a2e" : "#FAFAF8",
    }},
    borderWidth: 1.5,
    scaling: {{
      min: 8,
      max: 40,
      label: {{ enabled: true, min: 10, max: 20, drawThreshold: 6, maxVisible: 24 }},
    }},
  }},
  edges: {{
    width: 0.8,
    smooth: {{ type: "continuous" }},
    arrows: {{ to: {{ enabled: true, scaleFactor: 0.35 }} }},
    color: {{ inherit: false }},
    hoverWidth: 2,
    chosen: false,
    selectionWidth: 0,
  }},
  physics: {{
    stabilization: {{ iterations: 250, updateInterval: 25, fit: true }},
    barnesHut: {{ gravitationalConstant: gravConst, springLength: springLen, springConstant: 0.02, damping: 0.15 }},
    minVelocity: 0.75,
  }},
  interaction: {{ hover: true, tooltipDelay: 150, hideEdgesOnDrag: true, hideEdgesOnZoom: true }},
}});

network.once("stabilizationIterationsDone", function () {{
  network.fit({{ animation: {{ duration: 400, easingFunction: "easeInOutQuad" }} }});
}});


function focusNode(nodeId) {{
  activeNodeId = nodeId;
  applyFilters(searchInput.value, nodeId);
  const node = nodeMap.get(nodeId) || nodes.get(nodeId);
  const relatedIds = new Set([nodeId, ...(adjacency.get(nodeId) || [])]);
  openDrawer(node, relatedIds);
  network.focus(nodeId, {{
    scale: 1.1,
    animation: {{ duration: 300, easingFunction: "easeInOutQuad" }},
  }});
}}

function updateSpacing(val) {{
  const t = val / 100;
  const grav = -1500 - t * 12000;
  const spr = 100 + t * 300;
  network.setOptions({{
    physics: {{
      barnesHut: {{
        gravitationalConstant: grav,
        springLength: spr,
      }},
    }},
  }});
}}

network.on("dragStart", function () {{ container.classList.add("dragging"); }});
network.on("dragEnd", function () {{ container.classList.remove("dragging"); }});

network.on("click", params => {{
  if (params.nodes.length > 0) {{
    focusNode(params.nodes[0]);
  }} else {{
    clearSelection();
  }}
}});

function toggleStats() {{
  document.getElementById("stats-toggle").classList.toggle("open");
  document.getElementById("stats-content").classList.toggle("open");
}}

function computeStats() {{
  const n = originalNodes.length;
  const e = originalEdges.length;
  const epn = n ? (e / n) : 0;

  const degree = {{}};
  originalNodes.forEach(nd => degree[nd.id] = 0);
  originalEdges.forEach(ed => {{
    degree[ed.from] = (degree[ed.from] || 0) + 1;
    degree[ed.to] = (degree[ed.to] || 0) + 1;
  }});

  const orphanCount = Object.values(degree).filter(d => d === 0).length;
  const orphanPct = n ? (orphanCount / n * 100) : 0;

  const communities = new Set(originalNodes.map(nd => nd.group).filter(g => g >= 0));

  const degValues = Object.values(degree);
  const mean = degValues.length ? degValues.reduce((a, b) => a + b, 0) / degValues.length : 0;
  const std = degValues.length > 1
    ? Math.sqrt(degValues.reduce((s, d) => s + (d - mean) ** 2, 0) / (degValues.length - 1))
    : 0;
  const godCount = degValues.filter(d => d > mean + 2 * std).length;

  const crossComm = {{}};
  originalEdges.forEach(ed => {{
    const na = nodeMap.get(ed.from);
    const nb = nodeMap.get(ed.to);
    if (!na || !nb) return;
    const ca = na.group, cb = nb.group;
    if (ca >= 0 && cb >= 0 && ca !== cb) {{
      const key = Math.min(ca, cb) + "-" + Math.max(ca, cb);
      crossComm[key] = (crossComm[key] || 0) + 1;
    }}
  }});
  const fragileCount = Object.values(crossComm).filter(c => c === 1).length;

  const density = n > 1 ? (2 * e) / (n * (n - 1)) : 0;

  let health, hc;
  if (epn >= 2.0) {{ health = "healthy"; hc = "healthy"; }}
  else if (epn >= 1.0) {{ health = "warning"; hc = "warning"; }}
  else {{ health = "critical"; hc = "critical"; }}

  const filterNote = graphFilter
    ? `<div style="font-size:11px;color:var(--text-secondary);padding:6px 0 4px;line-height:1.4;font-style:italic;">Filtered by: ${{graphFilter.join(", ")}} — stats reflect subset only</div><hr class="stat-divider">`
    : "";

  document.getElementById("stats-body").innerHTML = filterNote + `
    <div class="stat-row">
      <span class="stat-label">Health</span>
      <span class="stat-health ${{hc}}">${{health}}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Nodes</span>
      <span class="stat-value">${{n}}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Edges</span>
      <span class="stat-value">${{e}}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Edges / node</span>
      <span class="stat-value">${{epn.toFixed(2)}}</span>
    </div>
    <hr class="stat-divider">
    <div class="stat-row">
      <span class="stat-label">Orphans</span>
      <span class="stat-value">${{orphanCount}} (${{orphanPct.toFixed(1)}}%)</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Communities</span>
      <span class="stat-value">${{communities.size}}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">God nodes</span>
      <span class="stat-value">${{godCount}}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Fragile bridges</span>
      <span class="stat-value">${{fragileCount}}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Density</span>
      <span class="stat-value">${{density.toFixed(4)}}</span>
    </div>
  `;
}}

rebuildAdjacency();
buildTagChips();
computeStats();
applyFilters();
</script>
</body>
</html>"""


def print_graph(open_browser: bool = False):
    if not GRAPH_JSON.exists():
        print(f"Error: {GRAPH_JSON.relative_to(REPO_ROOT)} not found. Run build_graph.py first.")
        raise SystemExit(1)

    data = json.loads(GRAPH_JSON.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    tag_filter = data.get("filter")
    built_date = data.get("built")

    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    html = render_html(nodes, edges, tag_filter=tag_filter, built_date=built_date)
    GRAPH_HTML.write_text(html, encoding="utf-8")
    print(f"Generated: graph/graph.html ({len(nodes)} nodes, {len(edges)} edges)")

    if open_browser:
        webbrowser.open(str(GRAPH_HTML.resolve()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Render the wiki knowledge graph as interactive HTML (from graph.json)"
    )
    parser.add_argument("--open", action="store_true", help="Open graph.html in browser")
    args = parser.parse_args()
    print_graph(open_browser=args.open)
