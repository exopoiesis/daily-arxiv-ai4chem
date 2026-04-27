#!/usr/bin/env python3
"""Generate compact README.md as a landing page.

Default: top-50 most recent papers per topic (~350 entries total). Sorted by
`updated` descending within each topic. Designed as a "what's hot per topic"
view — for full filtering by date/tags use GitHub Pages.
"""
import argparse
import logging
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_io import (ROOT, ABSTRACTS_DIR, load_all_months, render_md_row,
                     write_abstract)

LOG = logging.getLogger("render_readme")
README_PATH = ROOT / "README.md"


def topic_anchor(text):
    """GitHub-flavored slug for a markdown header.

    Rules (matching what GitHub generates from `## Heading`):
      1. Lowercase
      2. Strip everything except alphanumerics, spaces, hyphens, underscores
      3. Replace spaces with hyphens (consecutive spaces preserved as multi-hyphen)

    Example: 'Reaction, Synthesis & Catalysis' → 'reaction-synthesis--catalysis'
    """
    s = text.lower()
    s = "".join(c if (c.isalnum() or c in " -_") else "" for c in s)
    return s.replace(" ", "-")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=50,
                        help="max papers per topic (default: 50)")
    parser.add_argument("--out", default=str(README_PATH),
                        help="output path (default: README.md)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="[%(asctime)s %(levelname)s] %(message)s",
                        datefmt="%H:%M:%S")

    by_month, _ = load_all_months()
    total = sum(len(m) for m in by_month.values())
    LOG.info(f"loaded {total} papers across {len(by_month)} months")

    by_topic = defaultdict(list)
    untagged = 0
    for month_data in by_month.values():
        for pid, rec in month_data.items():
            if not rec["topics"]:
                untagged += 1
                continue
            for topic in rec["topics"]:
                by_topic[topic].append((pid, rec))

    for topic in by_topic:
        by_topic[topic].sort(key=lambda x: x[1]["updated"], reverse=True)
        by_topic[topic] = by_topic[topic][:args.top_n]

    shown = sum(len(v) for v in by_topic.values())
    LOG.info(f"showing top-{args.top_n} per topic: {shown} entries across "
             f"{len(by_topic)} topics ({untagged} untagged ignored)")

    today = date.today().isoformat().replace("-", ".")
    top_header = f"Updated on {today}"
    top_anchor = topic_anchor(top_header)

    lines = []
    lines.append(f"## {top_header}")
    lines.append("")
    lines.append(f"> Top {args.top_n} most recent papers per topic. "
                 f"For full filtering by date or tag, see [GitHub Pages](./docs/).")
    lines.append("")
    lines.append(f"**Total corpus:** {total} papers across {len(by_month)} months.")
    lines.append("")

    if by_topic:
        lines.append("<details>")
        lines.append("  <summary>Table of Contents</summary>")
        lines.append("  <ol>")
        for topic in by_topic:
            anchor = topic_anchor(topic)
            lines.append(f'    <li><a href=#{anchor}>{topic}</a> ({len(by_topic[topic])})</li>')
        lines.append("  </ol>")
        lines.append("</details>")
        lines.append("")

    for topic, papers in by_topic.items():
        lines.append(f"## {topic}")
        lines.append("")
        lines.append("|Publish Date|Title|Authors|arXiv|Abstract|")
        lines.append("|---|---|---|---|---|")
        for pid, rec in papers:
            lines.append(render_md_row(pid, rec))
        lines.append("")
        lines.append(f'<p align=right>(<a href=#{top_anchor}>back to top</a>)</p>')
        lines.append("")

    out = Path(args.out)
    out.write_text("\n".join(lines), encoding="utf-8")
    LOG.info(f"wrote {out} ({len(lines)} lines, {out.stat().st_size/1024:.1f} KB)")

    # Sync abstracts/<year>/<id>.md with what README links: write missing,
    # delete orphans. Keeps the legacy md tree bounded.
    selected = set()
    for papers in by_topic.values():
        for pid, rec in papers:
            year = rec["published"][:4]
            selected.add((year, pid))
            write_abstract(pid, rec)
    LOG.info(f"README references {len(selected)} unique papers")

    if ABSTRACTS_DIR.exists():
        deleted = 0
        for f in ABSTRACTS_DIR.rglob("*.md"):
            if (f.parent.name, f.stem) not in selected:
                f.unlink()
                deleted += 1
        for d in sorted(ABSTRACTS_DIR.iterdir()):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        LOG.info(f"abstracts md sync: deleted {deleted} orphans")


if __name__ == "__main__":
    main()
