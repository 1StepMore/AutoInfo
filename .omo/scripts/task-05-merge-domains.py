#!/usr/bin/env python3
"""Merge 4 missing demo domains into .autoinfo/config.yaml, preserving existing medical-research."""

import yaml
import sys
from pathlib import Path

REPO_ROOT = Path("/mnt/d/贯维/AutoInfo")
CONFIG_PATH = REPO_ROOT / ".autoinfo" / "config.yaml"
DOMAINS_DIR = REPO_ROOT / "src" / "autoinfo" / "data" / "domains"

NEW_DOMAINS = [
    "ai-commercial",
    "financial-intelligence",
    "tech-ai-developer",
    "language-learning",
]

# Defaults for fields that may be missing in sources.yaml
SOURCE_DEFAULTS = {
    "tos_classification": "open",
    "frequency": "daily",
    "access": "free",
    "rate_limit": 10,
}

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def write_config(config):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

def load_domain_sources(domain_name):
    path = DOMAINS_DIR / domain_name / "sources.yaml"
    with open(path, "r") as f:
        return yaml.safe_load(f)

def normalize_source(source):
    """Fill in missing fields with defaults for a source entry."""
    s = dict(source)
    for key, default in SOURCE_DEFAULTS.items():
        s.setdefault(key, default)
    # enabled is optional; if not present, treat as true (active)
    s.setdefault("enabled", True)
    return s

def normalize_topic(topic):
    """Return topic as-is; ensure keywords is a list."""
    return {"name": topic["name"], "keywords": list(topic.get("keywords", []))}

def main():
    config = load_config()
    existing_names = {d["name"] for d in config.get("domains", [])}

    for dn in NEW_DOMAINS:
        if dn in existing_names:
            print(f"  [SKIP] {dn} already exists in config")
            continue

        data = load_domain_sources(dn)
        domain_entry = {
            "name": data["name"],
            "active": True,
            "sources": [normalize_source(s) for s in data.get("sources", [])],
            "topics": [normalize_topic(t) for t in data.get("topics", [])],
        }
        config.setdefault("domains", []).append(domain_entry)
        print(f"  [ADD] {dn} — {len(domain_entry['sources'])} sources, {len(domain_entry['topics'])} topics")

    write_config(config)
    print(f"\nWrote {CONFIG_PATH}")

    # Validate
    with open(CONFIG_PATH, "r") as f:
        reloaded = yaml.safe_load(f)
    domains = reloaded.get("domains", [])
    print(f"\nTotal domains in config: {len(domains)}")
    for d in domains:
        src_count = len(d.get("sources", []))
        topic_count = len(d.get("topics", []))
        print(f"  {d['name']}: {src_count} sources, {topic_count} topics, active={d.get('active', False)}")

if __name__ == "__main__":
    main()
