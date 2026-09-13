#!/usr/bin/env python3
"""Surface parity audit — REST coverage (T-S-10) with CLI/MCP cross-checks.

Run from the project root::

    python3 scripts/surface_parity.py          # audit + write JSON report
    python3 scripts/surface_parity.py --check  # audit only, exit non-zero on gap

The parity matrix in ``docs/dev/cli-mcp-rest-parity.md`` is *derived*, not
hand-written.  This script supplies the machine-checkable half of that
derivation for the REST surface: it enumerates **every** FastAPI route mounted
on ``autoinfo.api.server:app`` (expanding the ``_IncludedRouter`` deferral the
way the parity doc describes) and asserts each one is accounted for by exactly
one of::

    scenario     — a real ``kind: http`` validation-scenario step
    artifact     — a real test file that exercises the endpoint
    disposition  — a documented reason it needs neither (framework docs)

The historical "8 REST endpoints" (the endpoints exercised by
``rest-api.yaml``) are pinned as :data:`CANONICAL_SCENARIO_ENDPOINTS` and must
each be covered by a **scenario** (not merely an artifact), so the canonical
surface claim can never silently regress to artifact-only evidence.

Exit 0 only when zero endpoints are unaccounted.  Counts are always derived
from the live registry — never hard-coded.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = ROOT / "src" / "autoinfo" / "mcp" / "scenarios"
PARITY_DOC = ROOT / "docs" / "dev" / "cli-mcp-rest-parity.md"
OUT_DIR = ROOT / "validation-runs" / "rest-surface"

#: HTTP methods that identify a capability endpoint (framework HEAD/OPTIONS
#: auto-variants are folded into GET).
DATA_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH")


@dataclass(frozen=True)
class Artifact:
    """A real test file that exercises an endpoint (T-S-10 evidence)."""

    path: str
    #: Substring guaranteed to appear in the artifact file; verified at audit
    #: time so a moved/renamed test fails loudly instead of passing vacuously.
    token: str


#: Endpoints with no scenario step, backed by a real test artifact.  The
#: concrete (method, path) keys mirror the live FastAPI route table; values
#: point at the test that drives the endpoint over HTTP.
REST_ARTIFACTS: dict[tuple[str, str], Artifact] = {
    ("GET", "/api/v1/entries/{entry_id}"): Artifact(
        "tests/api/test_error_responses.py", "/api/v1/entries/"
    ),
    ("POST", "/api/v1/entries"): Artifact("tests/api/test_v1_5_feed_api.py", "/api/v1/entries"),
    ("DELETE", "/api/v1/entries/{entry_id}"): Artifact(
        "tests/api/test_error_responses.py", "/api/v1/entries/"
    ),
    ("GET", "/api/v1/portal/preferences"): Artifact(
        "tests/integration/test_b11_fixes.py", "/api/v1/portal/preferences"
    ),
    ("PUT", "/api/v1/portal/preferences"): Artifact(
        "tests/integration/test_b11_fixes.py", "/api/v1/portal/preferences"
    ),
    ("GET", "/api/v1/portal/delivery-history"): Artifact(
        "tests/api/test_portal_delivery_history_api.py",
        "/api/v1/portal/delivery-history",
    ),
    ("GET", "/portal/{user_id}"): Artifact("tests/user/test_portal.py", "/portal/"),
    ("GET", "/portal/{user_id}/preferences"): Artifact("tests/user/test_portal.py", "/portal/"),
    ("GET", "/portal/{user_id}/history"): Artifact("tests/user/test_portal.py", "/portal/"),
    ("GET", "/portal/{user_id}/products"): Artifact("tests/user/test_portal.py", "/portal/"),
    ("GET", "/storefront"): Artifact("tests/api/test_storefront.py", "/storefront"),
    ("GET", "/storefront/products/{product_id}"): Artifact(
        "tests/api/test_storefront.py", "/storefront/products/"
    ),
    ("POST", "/storefront/subscriptions"): Artifact(
        "tests/api/test_storefront.py", "/storefront/subscriptions"
    ),
    ("GET", "/media/{file_path:path}"): Artifact("tests/delivery/test_podcast_rss.py", "/media/"),
    ("POST", "/api/v1/webhook/stripe"): Artifact(
        "tests/cost/test_stripe.py", "/api/v1/webhook/stripe"
    ),
}

#: Framework-internal endpoints that carry no AutoInfo capability and are
#: served by FastAPI itself; documented dispositions, no scenario/artifact.
REST_DISPOSITIONS: dict[tuple[str, str], str] = {
    ("GET", "/openapi.json"): "FastAPI-generated OpenAPI schema (framework)",
    ("GET", "/docs"): "FastAPI Swagger UI (framework)",
    ("GET", "/docs/oauth2-redirect"): "FastAPI OAuth2 redirect helper (framework)",
    ("GET", "/redoc"): "FastAPI ReDoc UI (framework)",
}

#: The eight endpoints the REST parity claim historically names.  Each MUST be
#: covered by a real scenario step (not just an artifact) so the canonical
#: claim keeps HTTP-level evidence.
CANONICAL_SCENARIO_ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("GET", "/health"),
    ("GET", "/"),
    ("GET", "/dashboard"),
    ("GET", "/api/v1/entries"),
    ("GET", "/api/v1/search"),
    ("GET", "/api/v1/feeds"),
    ("GET", "/metrics"),
    ("GET", "/storefront/products"),
)


# ---------------------------------------------------------------------------
# Live registry enumeration
# ---------------------------------------------------------------------------


def enumerate_rest_endpoints() -> list[dict[str, str]]:
    """Return ``[{method, path, name}]`` for every route mounted on the app.

    FastAPI's ``_IncludedRouter`` deferral means ``app.routes`` exposes the
    router include wrapper rather than the routes; this expands each wrapper
    through ``original_router.routes`` and applies its ``include_context``
    prefix (the same recipe the parity doc records).  HEAD/OPTIONS variants are
    folded away.
    """
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from autoinfo.api.server import app
    finally:
        sys.path.pop(0)

    endpoints: dict[tuple[str, str], str] = {}

    def _add(path: str, methods: Iterable[str], name: str) -> None:
        for method in methods:
            method = method.upper()
            if method in DATA_METHODS:
                endpoints.setdefault((method, path), name)

    for route in app.routes:
        original = getattr(route, "original_router", None)
        if original is not None:
            context = getattr(route, "include_context", None)
            prefix = (getattr(context, "prefix", "") or "") if context else ""
            for sub in original.routes:
                sub_path = getattr(sub, "path", None)
                if sub_path is None:
                    continue
                _add(
                    prefix + sub_path,
                    sorted(getattr(sub, "methods", set()) or set()),
                    getattr(sub, "name", ""),
                )
        else:
            path = getattr(route, "path", None)
            if path is None:
                continue
            _add(
                path,
                sorted(getattr(route, "methods", set()) or set()),
                getattr(route, "name", ""),
            )

    return [
        {"method": method, "path": path, "name": endpoints[(method, path)]}
        for method, path in sorted(endpoints)
    ]


def scenario_http_endpoints(scenarios_dir: Path | None = None) -> set[tuple[str, str]]:
    """Return the set of ``(METHOD, path)`` covered by scenario HTTP steps."""
    sd = scenarios_dir or SCENARIOS_DIR
    covered: set[tuple[str, str]] = set()
    if not sd.is_dir():
        return covered
    for yaml_path in sorted(sd.rglob("*.yaml")):
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for step in data.get("steps", []) or []:
            if step.get("kind") != "http":
                continue
            url = step.get("url", "")
            method = str(step.get("method", "GET")).upper()
            match = re.match(r"^https?://[^/]+(/[^?#]*)", url)
            path = match.group(1) if match else url
            covered.add((method, path.rstrip("/") or "/"))
    return covered


def cli_groups() -> list[str]:
    """Return the live Typer command-group names (derived from the CLI app)."""
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from autoinfo.cli import app as cli_app

        groups = []
        for info in getattr(cli_app, "registered_groups", []):
            name = getattr(info, "name", None)
            if name:
                groups.append(name)
        return sorted(groups)
    finally:
        sys.path.pop(0)


def mcp_tool_count() -> int:
    """Return the live declared MCP tool count from ``_full_tool_list()``."""
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from autoinfo.mcp.server import _full_tool_list

        return len(_full_tool_list())
    finally:
        sys.path.pop(0)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _route_matches(route_path: str, concrete_path: str) -> bool:
    """True when a concrete scenario/target path satisfies a route template.

    ``re.escape`` escapes the braces, so the parameter wildcard is rebuilt on
    the escaped string — a path like ``/entries/{entry_id}`` then matches the
    concrete ``/entries/abc``.
    """
    pattern = re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(route_path))
    return re.fullmatch(pattern, concrete_path.rstrip("/") or "/") is not None


def classify_endpoints(
    endpoints: list[dict[str, str]],
    scenario_endpoints: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Attach the covering evidence kind to every enumerated endpoint."""
    rows: list[dict[str, Any]] = []
    for endpoint in endpoints:
        key = (endpoint["method"], endpoint["path"])
        scenario_match = any(
            method == key[0] and _route_matches(endpoint["path"], path)
            for method, path in scenario_endpoints
        )
        artifact = REST_ARTIFACTS.get(key)
        disposition = REST_DISPOSITIONS.get(key)

        if scenario_match:
            kind, evidence = "scenario", "kind: http scenario step"
        elif artifact is not None:
            kind, evidence = "artifact", artifact.path
        elif disposition is not None:
            kind, evidence = "disposition", disposition
        else:
            kind, evidence = "unaccounted", ""

        rows.append({**endpoint, "evidence_kind": kind, "evidence": evidence})
    return rows


def verify_artifacts() -> list[str]:
    """Fail loudly when a declared artifact file/token is missing.

    Returns a list of human-readable problems (empty = all verified).
    """
    problems: list[str] = []
    for (method, path), artifact in REST_ARTIFACTS.items():
        target = ROOT / artifact.path
        if not target.is_file():
            problems.append(f"{method} {path}: artifact {artifact.path} does not exist")
            continue
        if artifact.token not in target.read_text(encoding="utf-8", errors="replace"):
            problems.append(
                f"{method} {path}: artifact {artifact.path} does not reference {artifact.token!r}"
            )
    return problems


def compute_parity(scenarios_dir: Path | None = None) -> dict[str, Any]:
    """Return the full REST parity report (endpoints + cli + mcp counts)."""
    endpoints = enumerate_rest_endpoints()
    scenario_endpoints = scenario_http_endpoints(scenarios_dir)
    rows = classify_endpoints(endpoints, scenario_endpoints)

    unaccounted = [r for r in rows if r["evidence_kind"] == "unaccounted"]
    canonical_missing = [
        key
        for key in CANONICAL_SCENARIO_ENDPOINTS
        if not any(
            method == key[0] and _route_matches(key[1], path) for method, path in scenario_endpoints
        )
    ]
    return {
        "endpoints": rows,
        "count": len(rows),
        "by_kind": {
            kind: sum(1 for r in rows if r["evidence_kind"] == kind)
            for kind in ("scenario", "artifact", "disposition", "unaccounted")
        },
        "unaccounted": unaccounted,
        "canonical_scenario_endpoints": [list(k) for k in CANONICAL_SCENARIO_ENDPOINTS],
        "canonical_missing": [list(k) for k in canonical_missing],
        "artifact_problems": verify_artifacts(),
        "cli_group_count": len(cli_groups()),
        "mcp_tool_count": mcp_tool_count(),
    }


def doc_missing_paths(report: dict[str, Any], doc_path: Path | None = None) -> list[str]:
    """Endpoint paths absent from the parity doc (doc/code drift guard)."""
    doc = doc_path or PARITY_DOC
    if not doc.is_file():
        return ["parity doc is missing"]
    text = doc.read_text(encoding="utf-8")
    missing: list[str] = []
    for row in report["endpoints"]:
        path = row["path"]
        # Compare on the static prefix so parameterized routes (which appear
        # in the doc as ``{entry_id}``) match regardless of spelling.
        prefix = path.split("{", 1)[0].rstrip("/")
        token = prefix or path
        if token not in text:
            missing.append(f"{row['method']} {path}")
    return missing


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="REST surface parity audit (T-S-10).")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Audit only; do not write the JSON report. Exits non-zero on any gap.",
    )
    args = parser.parse_args(argv)

    report = compute_parity()
    doc_missing = doc_missing_paths(report)

    print(f"REST endpoints enumerated: {report['count']}")
    for kind in ("scenario", "artifact", "disposition"):
        print(f"  {kind}: {report['by_kind'][kind]}")
    print(f"unaccounted endpoints: {report['by_kind']['unaccounted']}")
    for row in report["unaccounted"]:
        print(f"  UNACCOUNTED {row['method']} {row['path']}")
    print(
        "canonical scenario endpoints: "
        f"{len(CANONICAL_SCENARIO_ENDPOINTS) - len(report['canonical_missing'])}"
        f"/{len(CANONICAL_SCENARIO_ENDPOINTS)}"
    )
    for method, path in report["canonical_missing"]:
        print(f"  CANONICAL MISSING {method} {path}")
    for problem in report["artifact_problems"]:
        print(f"  ARTIFACT PROBLEM {problem}")
    for entry in doc_missing:
        print(f"  DOC MISSING {entry}")
    print(f"CLI command groups (live): {report['cli_group_count']}")
    print(f"MCP tools declared (live): {report['mcp_tool_count']}")

    ok = (
        report["by_kind"]["unaccounted"] == 0
        and not report["canonical_missing"]
        and not report["artifact_problems"]
        and not doc_missing
    )

    if not args.check:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        out_path = OUT_DIR / f"rest-parity-{stamp}.json"
        out_path.write_text(
            json.dumps(
                {
                    "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                    "rest_endpoint_count": report["count"],
                    "by_kind": report["by_kind"],
                    "endpoints": report["endpoints"],
                    "canonical_missing": report["canonical_missing"],
                    "artifact_problems": report["artifact_problems"],
                    "doc_missing": doc_missing,
                    "cli_group_count": report["cli_group_count"],
                    "mcp_tool_count": report["mcp_tool_count"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"REST parity report: {out_path}")

    if not ok:
        print("SURFACE_PARITY_FAIL")
        return 1
    print("SURFACE_PARITY_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
