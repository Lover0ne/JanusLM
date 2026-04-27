#!/usr/bin/env python3
from __future__ import annotations

"""
Build the knowledge graph from wiki [[wikilinks]]. Analysis only — no visualization.

Contract:
  (no flags)       → scans wiki, writes graph/graph.json
  --report         → also prints markdown report to stdout (orphans, hubs, communities)
  --report --save  → saves report to graph/graph-report.md
  --json           → outputs structured JSON report to stdout (used by heal.py --detect)

Inputs:  wiki/**/*.md files (scans for [[wikilinks]] and YAML frontmatter)
Outputs: graph/graph.json (nodes + edges), stdout (report), optionally graph/graph-report.md

Dependencies: networkx (required), community/louvain (optional, for community detection)

For HTML visualization, run print_graph.py AFTER this script.

If this script fails:
  - ImportError networkx → pip install networkx
  - No wiki .md files found → not an error, produces empty graph
  - graph/ directory missing → create it (mkdir graph)
  - Malformed [[wikilinks]] → skipped silently, check source page manually
"""

import re
import json
import argparse
import statistics
from pathlib import Path
from datetime import date

try:
    import networkx as nx
    from networkx.algorithms import community as nx_community
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("Warning: networkx not installed. Community detection disabled. Run: pip install networkx")

from shared import (
    REPO_ROOT, WIKI_DIR, GRAPH_DIR, GRAPH_JSON,
    TYPE_COLORS, read_file, all_wiki_pages, append_log_raw, extract_tags,
)

COMMUNITY_COLORS = [
    "#D6B656", "#3D4A50", "#A69882", "#C4956A", "#7A8B6F",
    "#8B7355", "#5C6B73", "#B8926A", "#6B5B4E", "#9DA5AA",
]

EDGE_COLOR = "#B8B4AE"


def extract_wikilinks(content: str) -> list[str]:
    return list(set(re.findall(r'\[\[([^\]]+)\]\]', content)))


def extract_frontmatter_type(content: str) -> str:
    match = re.search(r'^type:\s*(\S+)', content, re.MULTILINE)
    return match.group(1).strip('"\'') if match else "unknown"


def page_id(path: Path) -> str:
    return path.relative_to(WIKI_DIR).as_posix().replace(".md", "")


def edge_id(src: str, target: str) -> str:
    return f"{src}->{target}"


def build_nodes(pages: list[Path]) -> list[dict]:
    nodes = []
    for p in pages:
        content = read_file(p)
        node_type = extract_frontmatter_type(content)
        title_match = re.search(r'^title:\s*"?([^"\n]+)"?', content, re.MULTILINE)
        label = title_match.group(1).strip() if title_match else p.stem
        body = re.sub(r"^---\n.*?\n---\n?", "", content, flags=re.DOTALL)
        preview_lines = [line.strip() for line in body.splitlines() if line.strip()]
        preview = " ".join(preview_lines[:3])[:220]
        nodes.append({
            "id": page_id(p),
            "label": label,
            "type": node_type,
            "color": TYPE_COLORS.get(node_type, TYPE_COLORS["unknown"]),
            "path": str(p.relative_to(REPO_ROOT)),
            "markdown": content,
            "preview": preview,
        })
    return nodes


def build_edges(pages: list[Path]) -> list[dict]:
    """Build edges from explicit [[wikilinks]]."""
    stem_map = {p.stem.lower(): page_id(p) for p in pages}
    edges = []
    seen = set()
    for p in pages:
        content = read_file(p)
        src = page_id(p)
        for link in extract_wikilinks(content):
            target = stem_map.get(link.lower())
            if target and target != src:
                key = (src, target)
                if key not in seen:
                    seen.add(key)
                    edges.append({
                        "id": edge_id(src, target),
                        "from": src,
                        "to": target,
                        "type": "EXTRACTED",
                        "color": EDGE_COLOR,
                        "confidence": 1.0,
                    })
    return edges


def build_nx_graph(nodes: list[dict], edges: list[dict]):
    """Build NetworkX graph from node/edge lists. Single construction point."""
    if not HAS_NETWORKX:
        return None
    G = nx.Graph()
    for n in nodes:
        G.add_node(n["id"])
    for e in edges:
        G.add_edge(e["from"], e["to"])
    return G


def detect_communities(G) -> dict[str, int]:
    """Assign community IDs to nodes using Louvain algorithm."""
    if G is None or G.number_of_edges() == 0:
        return {}

    try:
        communities = nx_community.louvain_communities(G, seed=42)
        node_to_community = {}
        for i, comm in enumerate(communities):
            for node in comm:
                node_to_community[node] = i
        return node_to_community
    except Exception:
        return {}


def find_phantom_hubs(pages: list[Path], min_refs: int = 2) -> list[dict]:
    """Find wikilinks referenced by multiple pages but pointing to non-existent pages."""
    existing_stems = {p.stem.lower() for p in pages}
    refs: dict[str, set[str]] = {}
    for p in pages:
        content = read_file(p)
        links = extract_wikilinks(content)
        src = page_id(p)
        for link in links:
            if link.lower() not in existing_stems:
                refs.setdefault(link, set()).add(src)

    phantoms = [
        {
            "name": name,
            "ref_count": len(sources),
            "referenced_by": sorted(sources),
        }
        for name, sources in refs.items()
        if len(sources) >= min_refs
    ]
    phantoms.sort(key=lambda x: x["ref_count"], reverse=True)
    return phantoms


def generate_report_json(G, nodes: list[dict], edges: list[dict],
                         communities: dict[str, int],
                         pages: list[Path] | None = None) -> dict:
    """Generate graph analysis as structured JSON (consumed by heal.py)."""
    today = date.today().isoformat()
    n_nodes = len(nodes)
    n_edges = len(edges)

    result: dict = {
        "date": today,
        "nodes": n_nodes,
        "edges": n_edges,
        "orphans": [],
        "phantom_hubs": [],
        "god_nodes": [],
        "fragile_bridges": [],
        "communities": [],
    }

    if n_nodes == 0 or G is None:
        return result

    degrees = dict(G.degree())
    edges_per_node = n_edges / n_nodes if n_nodes else 0
    result["edges_per_node"] = round(edges_per_node, 2)
    result["density"] = round(nx.density(G), 4)

    result["orphans"] = [
        {"id": n, "path": next((nd["path"] for nd in nodes if nd["id"] == n), n)}
        for n, d in sorted(degrees.items()) if d == 0
    ]

    deg_values = list(degrees.values())
    mean_deg = statistics.mean(deg_values) if deg_values else 0
    std_deg = statistics.stdev(deg_values) if len(deg_values) > 1 else 0
    god_threshold = mean_deg + 2 * std_deg
    result["god_nodes"] = [
        {"id": n, "degree": d}
        for n, d in sorted(degrees.items(), key=lambda x: x[1], reverse=True)
        if d > god_threshold
    ]

    community_count = len(set(communities.values())) if communities else 0
    comm_members: dict[int, list[str]] = {}
    for node_id, comm_id in communities.items():
        comm_members.setdefault(comm_id, []).append(node_id)

    result["communities"] = [
        {"id": comm_id, "members": sorted(members)}
        for comm_id, members in sorted(comm_members.items())
    ]

    cross_comm_edges: dict[tuple[int, int], list[dict]] = {}
    for e in edges:
        ca = communities.get(e["from"], -1)
        cb = communities.get(e["to"], -1)
        if ca >= 0 and cb >= 0 and ca != cb:
            key = (min(ca, cb), max(ca, cb))
            cross_comm_edges.setdefault(key, []).append(e)
    result["fragile_bridges"] = [
        {"community_a": pair[0], "community_b": pair[1],
         "from": edge_list[0]["from"], "to": edge_list[0]["to"]}
        for pair, edge_list in sorted(cross_comm_edges.items())
        if len(edge_list) == 1
    ]

    if pages:
        result["phantom_hubs"] = find_phantom_hubs(pages)

    return result


def generate_report(G, nodes: list[dict], edges: list[dict], communities: dict[str, int],
                    pages: list[Path] | None = None) -> str:
    """Generate a structured graph health report as markdown."""
    today = date.today().isoformat()
    n_nodes = len(nodes)
    n_edges = len(edges)

    if n_nodes == 0:
        return f"# Graph Insights Report — {today}\n\nWiki is empty — nothing to report.\n"

    if G is None:
        return f"# Graph Insights Report — {today}\n\nnetworkx not installed. Run: pip install networkx\n"

    degrees = dict(G.degree())
    edges_per_node = n_edges / n_nodes if n_nodes else 0
    density = nx.density(G)

    if edges_per_node >= 2.0:
        health = "healthy"
    elif edges_per_node >= 1.0:
        health = "warning"
    else:
        health = "critical"

    orphans = sorted([n for n, d in degrees.items() if d == 0])
    orphan_count = len(orphans)
    orphan_pct = (orphan_count / n_nodes * 100) if n_nodes else 0

    deg_values = list(degrees.values())
    mean_deg = statistics.mean(deg_values) if deg_values else 0
    std_deg = statistics.stdev(deg_values) if len(deg_values) > 1 else 0
    god_threshold = mean_deg + 2 * std_deg
    god_nodes = sorted(
        [(n, d) for n, d in degrees.items() if d > god_threshold],
        key=lambda x: x[1],
        reverse=True,
    )

    community_count = len(set(communities.values())) if communities else 0
    comm_members: dict[int, list[str]] = {}
    for node_id, comm_id in communities.items():
        comm_members.setdefault(comm_id, []).append(node_id)

    cross_comm_edges: dict[tuple[int, int], list[dict]] = {}
    for e in edges:
        ca = communities.get(e["from"], -1)
        cb = communities.get(e["to"], -1)
        if ca >= 0 and cb >= 0 and ca != cb:
            key = (min(ca, cb), max(ca, cb))
            cross_comm_edges.setdefault(key, []).append(e)
    fragile_bridges = [
        (pair, edge_list[0])
        for pair, edge_list in sorted(cross_comm_edges.items())
        if len(edge_list) == 1
    ]

    lines = [
        f"# Graph Insights Report — {today}",
        "",
        "## Health Summary",
        f"- **{n_nodes}** nodes, **{n_edges}** edges ({edges_per_node:.2f} edges/node — {health})",
        f"- **{orphan_count}** orphan nodes ({orphan_pct:.1f}%) — target: <10%",
        f"- **{community_count}** communities",
        f"- Link density: {density:.4f}",
        "",
    ]

    lines.append(f"## Orphan Nodes ({orphan_count} pages, {orphan_pct:.1f}%)")
    if orphans:
        lines.append("These pages have zero graph connections. Consider adding [[wikilinks]]:")
        for o in orphans:
            lines.append(f"- `{o}`")
    else:
        lines.append("No orphan nodes — excellent!")
    lines.append("")

    lines.append("## God Nodes (Hub Pages)")
    if god_nodes:
        lines.append("These nodes carry disproportionate connectivity (degree > mean+2*stdev):")
        lines.append("")
        lines.append("| Node | Degree | % of Edges | Community |")
        lines.append("|---|---|---|---|")
        for node_id, deg in god_nodes:
            edge_pct = (deg / (2 * n_edges) * 100) if n_edges else 0
            comm = communities.get(node_id, -1)
            lines.append(f"| `{node_id}` | {deg} | {edge_pct:.1f}% | {comm} |")
    else:
        lines.append("No god nodes detected — degree distribution is balanced.")
    lines.append("")

    lines.append("## Fragile Bridges")
    if fragile_bridges:
        lines.append("Community pairs connected by only 1 edge:")
        for (ca, cb), edge in fragile_bridges:
            lines.append(f"- Community {ca} <-> Community {cb} via `{edge['from']}` -> `{edge['to']}`")
    else:
        lines.append("No fragile bridges — all community connections are redundant.")
    lines.append("")

    lines.append("## Community Overview")
    if comm_members:
        lines.append("")
        lines.append("| Community | Nodes | Key Members |")
        lines.append("|---|---|---|")
        for comm_id in sorted(comm_members.keys()):
            members = comm_members[comm_id]
            members_sorted = sorted(members, key=lambda m: degrees.get(m, 0), reverse=True)
            key_members = ", ".join(members_sorted[:5])
            if len(members_sorted) > 5:
                key_members += ", ..."
            lines.append(f"| {comm_id} | {len(members)} | {key_members} |")
    else:
        lines.append("No communities detected.")
    lines.append("")

    phantoms = find_phantom_hubs(pages) if pages else []
    lines.append("## Phantom Hubs (referenced but non-existent pages)")
    if phantoms:
        lines.append("These pages are referenced by 2+ existing pages but don't exist yet:")
        lines.append("")
        lines.append("| Page Name | References | Referenced By |")
        lines.append("|---|---|---|")
        for ph in phantoms:
            refs_preview = ", ".join(ph["referenced_by"][:3])
            if len(ph["referenced_by"]) > 3:
                refs_preview += ", ..."
            lines.append(f"| `[[{ph['name']}]]` | {ph['ref_count']} | {refs_preview} |")
    elif pages:
        lines.append("No phantom hubs — all referenced pages exist.")
    else:
        lines.append("Phantom hub detection skipped (no page data available).")
    lines.append("")

    lines.append("## Suggested Actions")
    actions = []
    if orphans:
        actions.append(f"1. Add wikilinks to top orphan pages (highest potential impact: {orphans[0]})")
    if god_nodes:
        actions.append(f"{len(actions)+1}. Review god nodes for stub content vs. genuine hubs")
    if fragile_bridges:
        actions.append(f"{len(actions)+1}. Strengthen fragile bridges with cross-references")
    if phantoms:
        actions.append(f"{len(actions)+1}. Create pages for top phantom hubs (start with `[[{phantoms[0]['name']}]]` — {phantoms[0]['ref_count']} references)")
    if not actions:
        actions.append("1. Graph is in good shape — maintain current linking practices")
    lines.extend(actions)
    lines.append("")

    return "\n".join(lines)


def build_graph(report: bool = False, save: bool = False, as_json: bool = False,
                tag_filter: list[str] | None = None):
    pages = all_wiki_pages()
    if tag_filter:
        tags_set = set(tag_filter)
        pages = [p for p in pages if set(extract_tags(read_file(p))) & tags_set]
    today = date.today().isoformat()

    if not pages:
        if as_json:
            print(json.dumps({"date": today, "nodes": 0, "edges": 0,
                               "orphans": [], "phantom_hubs": [],
                               "god_nodes": [], "fragile_bridges": [],
                               "communities": []}, indent=2))
        else:
            print("Wiki is empty. Ingest some sources first.")
        return

    if not as_json:
        print(f"Building graph from {len(pages)} wiki pages...")

    GRAPH_DIR.mkdir(parents=True, exist_ok=True)

    nodes = build_nodes(pages)
    edges = build_edges(pages)
    G = build_nx_graph(nodes, edges)

    if not as_json:
        print(f"  Extracting wikilinks... {len(edges)} edges")
        print("  Running Louvain community detection...")

    communities = detect_communities(G)
    for node in nodes:
        comm_id = communities.get(node["id"], -1)
        if comm_id >= 0:
            node["color"] = COMMUNITY_COLORS[comm_id % len(COMMUNITY_COLORS)]
        node["group"] = comm_id

    degree_map: dict[str, int] = {}
    for e in edges:
        degree_map[e["from"]] = degree_map.get(e["from"], 0) + 1
        degree_map[e["to"]] = degree_map.get(e["to"], 0) + 1
    for node in nodes:
        node["value"] = degree_map.get(node["id"], 0) + 1

    graph_data = {"nodes": nodes, "edges": edges, "built": today, "filter": tag_filter}
    GRAPH_JSON.write_text(json.dumps(graph_data, indent=2, ensure_ascii=False), encoding="utf-8")

    if not as_json:
        print(f"  saved: graph/graph.json  ({len(nodes)} nodes, {len(edges)} edges)")

    tag_suffix = f" (tag: {','.join(tag_filter)})" if tag_filter else ""
    append_log_raw(f"## [{today}] graph | Knowledge graph rebuilt{tag_suffix}\n\n{len(nodes)} nodes, {len(edges)} edges.")

    if as_json:
        report_data = generate_report_json(G, nodes, edges, communities, pages=pages)
        print(json.dumps(report_data, indent=2))
    elif report:
        if not HAS_NETWORKX:
            print("Warning: networkx not installed. Cannot generate report.")
        else:
            report_text = generate_report(G, nodes, edges, communities, pages=pages)
            print("\n" + report_text)
            if save:
                report_path = GRAPH_DIR / "graph-report.md"
                report_path.write_text(report_text, encoding="utf-8")
                print(f"  saved: {report_path.relative_to(REPO_ROOT)}")
            append_log_raw(f"## [{today}] report | Graph health report generated\n\n{len(nodes)} nodes analyzed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build wiki knowledge graph")
    parser.add_argument("--report", action="store_true", help="Generate graph health report")
    parser.add_argument("--save", action="store_true", help="Save report to graph/graph-report.md")
    parser.add_argument("--json", action="store_true", help="Output report as JSON (for heal.py)")
    parser.add_argument("--tag", type=str,
                        help="Filter by project tag(s), comma-separated (e.g. project-alpha,project-beta)")
    args = parser.parse_args()
    tag_list = [t.strip() for t in args.tag.split(",")] if args.tag else None
    build_graph(report=args.report, save=args.save, as_json=args.json, tag_filter=tag_list)
