"""
Shared constants and utilities for wiki tools.

Used by: health.py, heal.py, build_graph.py, print_graph.py, log_report.py,
         log_write.py, wiki_stats.py
Do not add tool-specific logic here — only genuinely shared definitions.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
WIKI_DIR = REPO_ROOT / "wiki"
LOG_FILE = WIKI_DIR / "log.md"
GRAPH_DIR = REPO_ROOT / "graph"
GRAPH_JSON = GRAPH_DIR / "graph.json"
MASKZONE_DIR = REPO_ROOT / "maskzone"
QUEUE_FILE = REPO_ROOT / "heal_queue.json"

TYPE_COLORS = {
    "source": "#D6B656",
    "entity": "#3D4A50",
    "concept": "#A69882",
    "unknown": "#9E9E9E",
}

TYPE_COLORS_FADED = {
    "source": "#E8D9A8",
    "entity": "#9DA5AA",
    "concept": "#CCC5B8",
    "unknown": "#C8C8C8",
}

WIKI_META_FILES = {"index.md", "log.md", "lint-report.md", "health-report.md", "validation-report.md"}


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def strip_frontmatter(content: str) -> str:
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            return content[end + 3:].strip()
    return content.strip()


def all_wiki_pages() -> list[Path]:
    return [p for p in WIKI_DIR.rglob("*.md") if p.name not in WIKI_META_FILES]


def append_log_raw(entry: str):
    existing = read_file(LOG_FILE)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(entry.strip() + "\n\n" + existing, encoding="utf-8")


def extract_tags(content: str) -> list[str]:
    """Extract tags list from YAML frontmatter. Returns [] if no tags field or empty."""
    import re
    match = re.search(r'^tags:\s*\[([^\]]*)\]', content, re.MULTILINE)
    if not match:
        return []
    raw = match.group(1).strip()
    if not raw:
        return []
    return [t.strip().strip("'\"") for t in raw.split(",") if t.strip().strip("'\"")]
