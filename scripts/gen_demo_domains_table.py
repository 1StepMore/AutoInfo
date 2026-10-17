#!/usr/bin/env python3
"""gen_demo_domains_table.py — regenerate the README "Demo Domains" table.

The **single source of truth** for demo-domain sources is
``src/autoinfo/data/domains/*/sources.yaml``. Every curated-source count and
source-name list in the README "## Demo Domains" table is derived from those
files (``enabled: true`` only; a missing ``enabled`` key counts as enabled,
matching ``autoinfo.collect._resolve_sources``), so the table can never drift
from the seed configs again.

What is **not** derivable from YAML and therefore lives here as maintained
metadata (drift is bounded, not eliminated, for these):

* the human display name of each domain (``DOMAIN_META[*]["display"]``);
* the roadmap priority badge (🔴 P0 / 🟡 P1 / 🟢 P2), a product decision;
* the free-text disabled-source note (``disabled_note``) preserving the *why*
  a feed is off (GFW-blocked / dead / 404). The enabled source list and the
  curated count are always generated.

Usage::

    python3 scripts/gen_demo_domains_table.py            # rewrite README.md
    python3 scripts/gen_demo_domains_table.py --check    # exit 1 if README drifts

The section heading ``## Demo Domains`` is load-bearing: ``scripts/doc_inventory.py``
uses it as the terminator of the README "MCP Tools" section. Do not rename it.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"
DOMAINS_DIR = REPO / "src" / "autoinfo" / "data" / "domains"

#: Table cell for the status column; the heading stays `## Demo Domains`.
_HEADER = "| Domain | Sources | Priority | Status |"
_SEPARATOR = "|--------|---------|----------|--------|"

#: (slug, display, priority, disabled_note). Row order mirrors the README
#: (roughly P0 → P1 → P2, then the language-learning family). `display` and
#: `priority` are product metadata; `disabled_note` is the maintained
#: explanation for feeds that ship `enabled: false`.
DOMAIN_META: list[tuple[str, str, str, str]] = [
    ("medical-research", "Medical Research", "🔴 P0", ""),
    ("ai-commercial", "AI Commercial Intelligence", "🟡 P1", ""),
    ("financial-intelligence", "Financial/Business Intelligence", "🟡 P1", "WSJ Markets disabled"),
    (
        "tech-ai-developer",
        "Tech/AI/Developer",
        "🟡 P1",
        "Spotify AI Podcasts GFW-blocked, disabled",
    ),
    ("language-learning", "Language Learning", "🟢 P2", ""),
    (
        "online-video",
        "Online Video / OTT",
        "🟡 P1",
        "YouTube/Apple Music GFW-blocked/dead, disabled",
    ),
    ("financial-news", "Financial News", "🟡 P1", "5 dead/GFW feeds disabled"),
    (
        "online-education",
        "Online Education",
        "🟢 P2",
        "Class Central/Khan/dedao/ncpssd/wanfang GFW-blocked/dead, disabled",
    ),
    ("legal-compliance", "Legal Compliance", "🟢 P2", "IAPP/Law.com 404, disabled"),
    (
        "general-news",
        "General News",
        "🟢 P2",
        "GDELT/Google News/NYT/Medium/Atlantic/Time/Mastodon/Bluesky/wechat2rss "
        "GFW-blocked or throttled, disabled",
    ),
    ("gaming", "Gaming", "🟢 P2", "Polygon/游研社-via-GoogleNews disabled"),
    ("b2b", "B2B / Enterprise", "🟢 P2", "a16z feed 404, disabled"),
    ("retail", "Retail / E-commerce", "🟢 P2", "亿邦-via-GoogleNews disabled"),
    ("english-learning", "English Learning", "🟢 P2", ""),
    ("french-learning", "French Learning", "🟢 P2", ""),
    ("hindi-learning", "Hindi Learning", "🟢 P2", ""),
    ("italian-learning", "Italian Learning", "🟢 P2", ""),
    ("korean-learning", "Korean Learning", "🟢 P2", ""),
    ("portuguese-learning", "Portuguese Learning", "🟢 P2", ""),
    ("russian-learning", "Russian Learning", "🟢 P2", ""),
    ("spanish-learning", "Spanish Learning", "🟢 P2", ""),
]

#: Friendly display names for YAML source slugs. Unknown names fall through to
#: the raw YAML ``name`` (never silently dropped).
SOURCE_DISPLAY: dict[str, str] = {
    # medical-research
    "pubmed": "PubMed (REST API)",
    "semantic-scholar": "Semantic Scholar",
    "CrossRef": "CrossRef",
    "dblp": "DBLP",
    "openalex": "OpenAlex",
    "uspto": "USPTO",
    # ai-commercial
    "techcrunch": "TechCrunch RSS",
    "producthunt": "ProductHunt RSS",
    "Crunchbase": "Crunchbase",
    "36kr": "36kr",
    # tech-ai-developer
    "hnrss": "hnrss",
    "ars-technica": "Ars Technica",
    "techcrunch-ai": "TechCrunch AI",
    "infoq-cn": "InfoQ 中文",
    "lobsters": "Lobsters",
    "juejin": "掘金 (Juejin)",
    "qbitai": "量子位 (QbitAI)",
    # language-learning
    "project-gutenberg": "Project Gutenberg",
    "news-in-levels": "news-in-levels",
    "commonlit": "commonlit",
    # online-video
    "variety": "Variety",
    "hollywood-reporter": "Hollywood Reporter",
    "netflix-tech-blog": "Netflix Tech Blog",
    "pitchfork": "Pitchfork",
    "billboard": "Billboard",
    "bilibili-popular": "Bilibili (popular)",
    "thewrap": "TheWrap",
    "the-verge": "The Verge",
    "comingsoon": "ComingSoon",
    # financial-news
    "cnbc": "CNBC",
    "seeking-alpha": "Seeking Alpha",
    "microsoft-newsroom": "Microsoft Newsroom",
    # online-education
    "coursera-blog": "Coursera Blog",
    "edsurge": "EdSurge",
    "open-culture": "Open Culture",
    "coursera": "Coursera",
    "arxiv-cs-cy": "arXiv (cs.CY)",
    "inside-higher-ed": "Inside Higher Ed",
    # legal-compliance
    "scotusblog": "SCOTUSblog",
    "oyez": "Oyez",
    "gdpr-eu": "GDPR.eu",
    "court-gov": "court.gov",
    "thepaper-legal": "澎湃新闻 (The Paper)",
    # general-news
    "guardian-open-platform": "Guardian Open Platform",
    "ap-api": "AP API",
    "zhihu-daily": "知乎日报",
    "jiemian": "界面新闻 (Jiemian)",
    "wired": "Wired",
    "france24": "France24",
    "engadget": "Engadget",
    "spacenews": "SpaceNews",
    "people-cn-world": "人民网 (People's Daily)",
    "cgtn-world": "CGTN",
    "sina-marquee": "新浪娱乐 (Sina)",
    # gaming
    "ign-rss": "IGN RSS",
    "gamesindustry-biz": "GamesIndustry.biz",
    "gcores-rss": "机核网 gcores",
    "gamespot": "GameSpot",
    "pc-gamer": "PC Gamer",
    "eurogamer": "Eurogamer",
    "rock-paper-shotgun": "Rock Paper Shotgun",
    "gematsu": "Gematsu",
    # b2b
    "crunchbase-news": "Crunchbase News",
    "hackernews": "HackerNews",
    "saastr": "SaaStr",
    "b2b-news-network": "B2B News Network",
    "marTech": "MarTech",
    # retail
    "retail-dive": "Retail Dive",
    "modern-retail": "Modern Retail",
    "shopify-news": "Shopify News",
    "digiday": "Digiday",
    "retailwire": "RetailWire",
    # english-learning
    "duolingo-blog": "Duolingo Blog (RSS)",
    "npr-news": "NPR News (RSS)",
    # french-learning
    "france24-fr": "France24 (RSS)",
    "le-figaro": "Le Figaro (RSS)",
    # hindi-learning
    "aaj-tak": "Aaj Tak (RSS)",
    "bbc-hindi": "BBC Hindi (RSS)",
    "ndtv-khabar": "NDTV Khabar (RSS)",
    "amar-ujala": "Amar Ujala (RSS)",
    # korean-learning
    "donga": "Donga",
    "khan": "Khan",
    # portuguese-learning
    "observador": "Observador (RSS)",
    "g1-globo": "G1 Globo (RSS)",
    "folha-de-sao-paulo": "Folha de S.Paulo (RSS)",
    "publico-pt": "Público (RSS)",
    # russian-learning
    "tass": "TASS (RSS)",
    "rt-news": "RT News (RSS)",
    "interfax": "Interfax (RSS)",
    # spanish-learning
    "20minutos": "20 Minutos (RSS)",
    "el-pais": "El País (RSS)",
    "el-mundo": "El Mundo (RSS)",
    "bbc-mundo": "BBC Mundo (RSS)",
    # disabled sources (kept for completeness / future auto-listing)
    "WSJ Markets": "WSJ Markets",
    "Spotify AI Podcasts": "Spotify AI Podcasts",
    "youtube-mkbhd": "YouTube (MKBHD)",
    "apple-music": "Apple Music",
    "reuters-business": "Reuters Business",
    "ft-alphaville": "FT Alphaville",
    "businesswire-technology": "BusinessWire Technology",
    "prnewswire-financial-services": "PR Newswire (Financial Services)",
    "nvidia-newsroom": "NVIDIA Newsroom",
    "class-central": "Class Central",
    "khan-academy": "Khan Academy",
    "dedao": "得到 (dedao)",
    "ncpssd": "国家哲学社会科学文献中心 (ncpssd)",
    "wanfang": "万方 (Wanfang)",
    "iapp-privacy": "IAPP Privacy",
    "law-com": "Law.com",
    "gdelt": "GDELT",
    "google-news-rss": "Google News RSS",
    "nyt": "New York Times",
    "mastodon": "Mastodon",
    "bluesky": "Bluesky",
    "wechat2rss": "wechat2rss (微信公众号)",
    "medium-user": "Medium (user)",
    "medium-publication": "Medium (publication)",
    "medium-tag": "Medium (tag)",
    "the-atlantic": "The Atlantic",
    "time-magazine": "Time Magazine",
    "polygon-rss": "Polygon",
    "yystv-via-google-news": "游研社 via Google News",
    "a16z": "a16z",
    "ebrun-via-google-news": "亿邦 via Google News",
}

#: Per-domain display overrides for slugs whose friendly name differs between
#: domains (e.g. ``techcrunch`` is "TechCrunch RSS" in ai-commercial but plain
#: "TechCrunch" in b2b). Checked before :data:`SOURCE_DISPLAY`.
SOURCE_DISPLAY_BY_DOMAIN: dict[str, dict[str, str]] = {
    "b2b": {"techcrunch": "TechCrunch", "producthunt": "ProductHunt"},
    "general-news": {"npr-news": "NPR"},
}


def _load_yaml(path: Path) -> dict:
    """Load a sources.yaml. PyYAML is a hard dependency, so import lazily."""
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def enabled_and_disabled(slug: str) -> tuple[list[str], list[str]]:
    """Return ``(enabled_names, disabled_names)`` for a demo domain.

    A source with no explicit ``enabled`` key counts as enabled — this mirrors
    ``autoinfo.collect._resolve_sources`` (``settings.get("enabled", True)``).
    """
    raw = _load_yaml(DOMAINS_DIR / slug / "sources.yaml")
    enabled: list[str] = []
    disabled: list[str] = []
    for s in raw.get("sources", []) or []:
        if not isinstance(s, dict):
            continue
        name = str(s.get("name", "")).strip()
        if not name:
            continue
        if s.get("enabled", True) is False:
            disabled.append(name)
        else:
            enabled.append(name)
    return enabled, disabled


def display(slug: str, name: str) -> str:
    """Map a YAML source name to its friendly display form for *slug*."""
    return SOURCE_DISPLAY_BY_DOMAIN.get(slug, {}).get(name) or SOURCE_DISPLAY.get(name, name)


def render_table() -> str:
    """Render the full Demo Domains markdown table from the seed YAMLs."""
    lines = [_HEADER, _SEPARATOR]
    for slug, disp, priority, note in DOMAIN_META:
        enabled, disabled = enabled_and_disabled(slug)
        sources = ", ".join(display(slug, n) for n in enabled)
        n = len(enabled)
        noun = "source" if n == 1 else "sources"
        status = f"✅ Implemented ({n} curated {noun}"
        if note:
            if not disabled:
                raise SystemExit(
                    f"!! {slug}: disabled_note is set but sources.yaml has no "
                    f"`enabled: false` source — the note would lie."
                )
            status += f"; {note}"
        elif disabled:
            disabled_names = ", ".join(display(slug, n) for n in disabled)
            status += f"; {len(disabled)} disabled: {disabled_names}"
        status += ")"
        lines.append(f"| **{disp}** | {sources} | {priority} | {status} |")
    return "\n".join(lines)


_TABLE_RE = re.compile(
    r"(##\s+Demo Domains\s*\n\n)(\| Domain \|.*?\n\|[^\n]*\n(?:\|[^\n]*\n)*)",
    re.S,
)


def replace_table(readme_text: str, table: str) -> str:
    """Replace the Demo Domains table body in *readme_text*."""
    m = _TABLE_RE.search(readme_text)
    if not m:
        raise SystemExit("!! could not locate the '## Demo Domains' table in README.md")
    return readme_text[: m.start(2)] + table + "\n" + readme_text[m.end(2) :]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if README's Demo Domains table differs from the generated one; write nothing.",
    )
    args = ap.parse_args(argv)

    expected = render_table()
    current = README.read_text(encoding="utf-8")
    updated = replace_table(current, expected)

    if args.check:
        if updated != current:
            print("drift: README's Demo Domains table does not match sources.yaml")
            for a, b in zip(current.splitlines(), updated.splitlines()):
                if a != b:
                    print(f"  README: {a}")
                    print(f"  expect: {b}")
            return 1
        print("ok: README Demo Domains table matches sources.yaml")
        return 0

    if updated == current:
        print("no change: README Demo Domains table already matches sources.yaml")
        return 0
    README.write_text(updated, encoding="utf-8")
    print("updated: README.md Demo Domains table regenerated from sources.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
