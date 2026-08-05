"""SEO output module — sitemap and structured data generation.

Generates:
- XML sitemaps (sitemaps.org protocol) for KB entries
- JSON-LD structured data (schema.org) for KB entries
"""

import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def generate_sitemap(
    domain: str = "",
    base_url: str = "",
    entries: Optional[list[dict]] = None,
) -> str:
    """Generate an XML sitemap for KB entries.

    Args:
        domain: Domain name (for filtering)
        base_url: Base URL for the sitemap (required; no default is assumed)
        entries: List of entry dicts with keys: url, lastmod, changefreq, priority
                 If None, generates a placeholder sitemap

    Returns:
        XML string conforming to sitemaps.org schema

    Raises:
        ValueError: If ``base_url`` is not provided.
    """
    if not base_url:
        raise ValueError(
            "Sitemap generation requires an explicit base_url (no default is "
            "assumed). Pass base_url='https://your-site.example' to "
            "generate_sitemap() or export_kb(format='sitemap', "
            "base_url='https://your-site.example'), or use the CLI: "
            "autoinfo output sitemap --base-url https://your-site.example"
        )
    urlset = ET.Element("urlset")
    urlset.set("xmlns", "https://www.sitemaps.org/schemas/sitemap/0.9")

    if entries:
        for entry in entries:
            url_elem = ET.SubElement(urlset, "url")

            loc = ET.SubElement(url_elem, "loc")
            loc.text = entry.get("url", base_url)

            if "lastmod" in entry:
                lm = ET.SubElement(url_elem, "lastmod")
                lm.text = entry["lastmod"]

            if "changefreq" in entry:
                cf = ET.SubElement(url_elem, "changefreq")
                cf.text = entry["changefreq"]

            if "priority" in entry:
                pr = ET.SubElement(url_elem, "priority")
                pr.text = str(entry["priority"])

    # Add index page
    url_elem = ET.SubElement(urlset, "url")
    loc = ET.SubElement(url_elem, "loc")
    loc.text = base_url
    lm = ET.SubElement(url_elem, "lastmod")
    lm.text = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cf = ET.SubElement(url_elem, "changefreq")
    cf.text = "daily"
    pr = ET.SubElement(url_elem, "priority")
    pr.text = "1.0"

    return ET.tostring(urlset, encoding="unicode", xml_declaration=True)


def generate_structured_data(
    title: str,
    description: str = "",
    date_published: str = "",
    author: str = "AutoInfo",
    url: str = "",
    article_type: str = "Article",
) -> str:
    """Generate JSON-LD structured data for a KB entry.

    Args:
        title: Article title
        description: Article description/abstract
        date_published: ISO-8601 date string
        author: Author name
        url: Article URL
        article_type: schema.org type (Article, NewsArticle, Report, etc.)

    Returns:
        JSON-LD string suitable for <script type="application/ld+json">
    """
    ld: dict = {
        "@context": "https://schema.org",
        "@type": article_type,
        "headline": title,
        "description": description or title,
        "author": {
            "@type": "Organization",
            "name": author,
        },
    }

    if date_published:
        ld["datePublished"] = date_published
        ld["dateModified"] = date_published

    if url:
        ld["url"] = url
        ld["mainEntityOfPage"] = {
            "@type": "WebPage",
            "@id": url,
        }

    return json.dumps(ld, ensure_ascii=False, indent=2)
