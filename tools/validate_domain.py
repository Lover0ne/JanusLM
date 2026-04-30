#!/usr/bin/env python3
from __future__ import annotations

"""
Quantitative domain affinity scoring for wiki ingest.

Contract:
  --doc PATH --tag TAG   → compares document against wiki pages with that tag
  --json                 → outputs structured JSON report to stdout
  --save                 → saves report to wiki/

Inputs:  the document (--doc), wiki/**/*.md pages filtered by --tag
Outputs: stdout (affinity report with composite score), optionally wiki/ file

Metrics: TF-IDF cosine similarity (40%), entity overlap (30%), concept overlap (30%).
Used alongside the agent's independent semantic evaluation (blind review) —
the agent evaluates first WITHOUT seeing this score, then compares.

Dependencies: scikit-learn, python-frontmatter, rapidfuzz

If this script fails:
  - ImportError → pip install scikit-learn python-frontmatter rapidfuzz
  - No pages with target tag → first document for this project, skip validation
  - Document not found → check --doc path
  - Empty document → TF-IDF returns 0, not an error
"""

import re
import sys
import json
import argparse
from pathlib import Path

try:
    import frontmatter
except ImportError:
    print("Error: python-frontmatter not installed. Run: pip install python-frontmatter")
    sys.exit(1)

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    print("Error: scikit-learn not installed. Run: pip install scikit-learn")
    sys.exit(1)

try:
    from rapidfuzz import fuzz
except ImportError:
    print("Error: rapidfuzz not installed. Run: pip install rapidfuzz")
    sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent
WIKI_DIR = REPO_ROOT / "wiki"

LEXICAL_WEIGHT = 0.4
ENTITY_WEIGHT = 0.3
CONCEPT_WEIGHT = 0.3

FUZZY_THRESHOLD = 85
SHORT_NAME_MAX_LEN = 5


# ── Utilities ──────────────────────────────────────────────────────

def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def strip_frontmatter(content: str) -> str:
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            return content[end + 3:].strip()
    return content.strip()


def extract_wikilinks(content: str) -> list[str]:
    return re.findall(r'\[\[([^\]]+)\]\]', content)


def split_title_case(name: str) -> str:
    """SamAltman → sam altman, RAG → rag, ReinforcementLearning → reinforcement learning"""
    spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    spaced = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', spaced)
    return spaced.lower().strip()


def get_tags(path: Path) -> list[str]:
    """Extract tags from a wiki page's frontmatter."""
    try:
        post = frontmatter.load(str(path))
        tags = post.get("tags", [])
        if isinstance(tags, str):
            return [tags]
        if isinstance(tags, list):
            return [str(t) for t in tags]
    except Exception:
        pass
    return []


# ── Corpus Collection ──────────────────────────────────────────────

def collect_corpus(tag: str) -> dict:
    """Find all wiki pages tagged with the given project tag.

    Returns dict with:
        pages: list of Path
        entities: list of str (names from entities/ pages)
        concepts: list of str (names from concepts/ pages)
        text: concatenated body text (frontmatter stripped)
    """
    exclude = {"index.md", "log.md", "health-report.md", "validation-report.md"}
    pages = []
    entities = []
    concepts = []
    texts = []
    wikilink_names = set()

    for md_file in WIKI_DIR.rglob("*.md"):
        if md_file.name in exclude:
            continue

        file_tags = get_tags(md_file)
        if tag not in file_tags:
            continue

        pages.append(md_file)
        content = read_file(md_file)
        body = strip_frontmatter(content)
        texts.append(body)

        for link in extract_wikilinks(content):
            wikilink_names.add(link)

        rel = md_file.relative_to(WIKI_DIR)
        parts = rel.parts
        if len(parts) >= 2:
            if parts[0] == "entities":
                entities.append(md_file.stem)
            elif parts[0] == "concepts":
                concepts.append(md_file.stem)

    # Merge wikilink-derived names into entities/concepts
    entity_dir = WIKI_DIR / "entities"
    concept_dir = WIKI_DIR / "concepts"
    for name in wikilink_names:
        if (entity_dir / f"{name}.md").exists() and name not in entities:
            if tag in get_tags(entity_dir / f"{name}.md"):
                entities.append(name)
        if (concept_dir / f"{name}.md").exists() and name not in concepts:
            if tag in get_tags(concept_dir / f"{name}.md"):
                concepts.append(name)

    return {
        "pages": pages,
        "entities": list(set(entities)),
        "concepts": list(set(concepts)),
        "text": "\n\n".join(texts),
    }


# ── Scoring Functions ─────────────────────────────────────────────

def compute_lexical_similarity(doc_text: str, corpus_text: str) -> float:
    """TF-IDF cosine similarity between document and corpus."""
    if not doc_text.strip() or not corpus_text.strip():
        return 0.0

    vectorizer = TfidfVectorizer(
        max_features=5000,
        sublinear_tf=True,
        min_df=1,
    )

    try:
        tfidf_matrix = vectorizer.fit_transform([doc_text, corpus_text])
        sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return float(sim)
    except ValueError:
        return 0.0


def fuzzy_match_in_text(name: str, text: str) -> bool:
    """Check if a wiki entity/concept name appears in the document text."""
    normalized = split_title_case(name)
    text_lower = text.lower()

    # Short names (acronyms like RAG, PoC): exact case-insensitive word boundary match
    if len(name) <= SHORT_NAME_MAX_LEN:
        pattern = r'\b' + re.escape(name.lower()) + r'\b'
        if re.search(pattern, text_lower):
            return True
        # Also try the normalized form
        if normalized != name.lower():
            pattern = r'\b' + re.escape(normalized) + r'\b'
            if re.search(pattern, text_lower):
                return True
        return False

    # Long names: try exact match on original name first (e.g. "OpenAI" in text)
    if re.search(r'\b' + re.escape(name.lower()) + r'\b', text_lower):
        return True

    # Then try normalized form (e.g. "open ai" for "OpenAI")
    if normalized in text_lower:
        return True

    # Try last token only (e.g. "Altman" for "SamAltman")
    tokens = normalized.split()
    if len(tokens) > 1:
        last_token = tokens[-1]
        if len(last_token) >= 4:
            pattern = r'\b' + re.escape(last_token) + r'\b'
            if re.search(pattern, text_lower):
                return True

    # Fuzzy match against sliding windows of similar length
    words = text_lower.split()
    name_word_count = len(normalized.split())
    for i in range(len(words) - name_word_count + 1):
        window = " ".join(words[i:i + name_word_count])
        if fuzz.ratio(normalized, window) >= FUZZY_THRESHOLD:
            return True

    return False


def compute_overlap(known_names: list[str], doc_text: str) -> dict:
    """Compute Jaccard-like overlap between known names and document text."""
    if not known_names:
        return {"matched": 0, "total": 0, "score": 0.0, "names": [], "matched_names": []}

    matched = []
    for name in known_names:
        if fuzzy_match_in_text(name, doc_text):
            matched.append(name)

    total = len(known_names)
    score = len(matched) / total if total > 0 else 0.0

    return {
        "matched": len(matched),
        "total": total,
        "score": score,
        "names": known_names,
        "matched_names": matched,
    }


# ── Main Validation ───────────────────────────────────────────────

def validate(doc_path: Path, tag: str) -> dict:
    """Run full domain validation and return structured results."""
    doc_content = read_file(doc_path)
    doc_text = strip_frontmatter(doc_content)

    if not doc_text.strip():
        return {
            "document": str(doc_path),
            "tag": tag,
            "status": "ERROR",
            "message": "Document is empty",
        }

    corpus = collect_corpus(tag)

    if not corpus["pages"]:
        return {
            "document": str(doc_path),
            "tag": tag,
            "status": "SKIP",
            "message": f"No existing pages for tag '{tag}'. First document — skipping validation.",
            "corpus_pages": 0,
        }

    # Compute scores
    lexical = compute_lexical_similarity(doc_text, corpus["text"])
    entity_overlap = compute_overlap(corpus["entities"], doc_text)
    concept_overlap = compute_overlap(corpus["concepts"], doc_text)

    # Composite score
    composite = (
        LEXICAL_WEIGHT * lexical
        + ENTITY_WEIGHT * entity_overlap["score"]
        + CONCEPT_WEIGHT * concept_overlap["score"]
    )

    verdict = "PROCEED" if composite >= 0.60 else "WARN"

    return {
        "document": str(doc_path),
        "tag": tag,
        "corpus_pages": len(corpus["pages"]),
        "corpus_entities": len(corpus["entities"]),
        "corpus_concepts": len(corpus["concepts"]),
        "lexical_similarity": round(lexical, 4),
        "entity_overlap": {
            "matched": entity_overlap["matched"],
            "total": entity_overlap["total"],
            "score": round(entity_overlap["score"], 4),
            "matched_names": entity_overlap["matched_names"],
        },
        "concept_overlap": {
            "matched": concept_overlap["matched"],
            "total": concept_overlap["total"],
            "score": round(concept_overlap["score"], 4),
            "matched_names": concept_overlap["matched_names"],
        },
        "composite_score": round(composite, 4),
        "weights": {
            "lexical": LEXICAL_WEIGHT,
            "entity": ENTITY_WEIGHT,
            "concept": CONCEPT_WEIGHT,
        },
        "verdict": verdict,
        "status": "OK",
    }


# ── Output Formatting ─────────────────────────────────────────────

def format_report(result: dict) -> str:
    """Format validation results as a readable markdown report."""
    if result.get("status") == "SKIP":
        return (
            f"# Domain Validation Report\n\n"
            f"**Document:** `{result['document']}`\n"
            f"**Tag:** `{result['tag']}`\n\n"
            f"> {result['message']}\n"
        )

    if result.get("status") == "ERROR":
        return (
            f"# Domain Validation Report\n\n"
            f"**Document:** `{result['document']}`\n"
            f"**Tag:** `{result['tag']}`\n\n"
            f"> ERROR: {result['message']}\n"
        )

    eo = result["entity_overlap"]
    co = result["concept_overlap"]
    composite_pct = int(result["composite_score"] * 100)
    lexical_pct = int(result["lexical_similarity"] * 100)

    lines = [
        "# Domain Validation Report",
        "",
        f"**Document:** `{result['document']}`",
        f"**Tag:** `{result['tag']}`",
        f"**Corpus:** {result['corpus_pages']} pages "
        f"({result.get('corpus_entities', 0)} entities, {result.get('corpus_concepts', 0)} concepts)",
        "",
        "| Metric | Score | Detail |",
        "|---|---|---|",
        f"| Lexical similarity (TF-IDF) | {lexical_pct}% | cosine similarity on TF-IDF vectors |",
        f"| Entity overlap | {eo['matched']}/{eo['total']} ({int(eo['score']*100)}%) | {', '.join(eo['matched_names']) or '—'} |",
        f"| Concept overlap | {co['matched']}/{co['total']} ({int(co['score']*100)}%) | {', '.join(co['matched_names']) or '—'} |",
        f"| **Composite score** | **{composite_pct}%** | weights: lexical {result['weights']['lexical']}, entity {result['weights']['entity']}, concept {result['weights']['concept']} |",
        "",
        f"**Verdict:** {'PROCEED (>= 60%)' if result['verdict'] == 'PROCEED' else 'WARN (< 60%) — ask user for confirmation'}",
    ]

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Quantitative domain validation for wiki ingest"
    )
    parser.add_argument("--doc", required=True, help="Path to the document to validate")
    parser.add_argument("--tag", required=True, help="Target project tag")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--save", action="store_true",
                        help="Save report to wiki/validation-report.md")
    args = parser.parse_args()

    doc_path = Path(args.doc)
    if not doc_path.exists():
        print(f"Error: file not found: {args.doc}")
        sys.exit(1)

    result = validate(doc_path, args.tag)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))

    if args.save:
        report_path = WIKI_DIR / "validation-report.md"
        report_path.write_text(format_report(result), encoding="utf-8")
        print(f"\nSaved: {report_path.relative_to(REPO_ROOT)}")

    if result.get("verdict") == "WARN":
        sys.exit(2)
