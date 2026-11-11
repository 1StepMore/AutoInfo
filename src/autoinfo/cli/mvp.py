"""Concierge MVP pilot CLI (``autoinfo mvp``, plan todo 13).

``mvp init`` provisions a complete paying pilot end-to-end:

1. **EndUserProfile + Subscription** — the profile is provisioned with
   ``tier="premium"`` / ``status="active"`` DIRECTLY
   (:func:`autoinfo.user_store.create_profile`).  The premium fast path of
   :func:`autoinfo.billing.check_access` reads ``UserProfile.tier``
   (billing.py:736-750), NOT the subscription tier — so a
   ``tier="premium"``/``status="active"`` profile grants premium access
   with NO Stripe dependency.  A bare
   :func:`autoinfo.user_store.activate_trial` would set ``status="trial"``
   and fall through to the Stripe fallback (rejected without Stripe) — it
   is deliberately NOT used here.  A matching premium subscription row is
   created alongside.
2. **Demo domain import** — reuses ``domain.py`` ``import_cmd`` (the
   ``import --from-demo`` source of truth) so the pilot domain config is
   byte-identical to a hand-imported demo domain.  Idempotent.
3. **First product** — generated through the HERMETIC SEAM (KBStore + LLM
   injection, mirror of ``regression-no-placeholder-magazine-tutorial``):
   static fixture entries with complete source provenance are injected
   through a patched ``KBStore`` and every LLM seam is patched to its
   deterministic fallback, so a temp project with NO LLM key and NO
   network still produces a REAL, complete product (which honestly passes
   the D1-D3 delivery gates — not an empty shell).
4. **Delivery directory** — ``mvp/<user_id>/`` (sibling of ``outputs/``)
   receives the product file, its gate report (md + json, shared todo-7
   implementation from :mod:`autoinfo.delivery.gate_report`),
   ``provenance.json`` (per-entry source provenance + explicit hermetic
   disclosure), and a ``user.json`` placeholder metadata file.

``mvp list`` aggregates pilot users from the filesystem + user_store
(profile tier/status) + subscriptions (plan) and shows each pilot's latest
product path.  Every step of ``init`` is idempotent: re-running prints a
clear ``already exists`` message and creates no duplicates.

Must NOT (plan todo 13): no trial reminders, no email delivery, no
scheduling, no Stripe, no external channel delivery, no LLM/network calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import typer

from autoinfo.config import get_config_path, load_config

from ._output import emit_if_global, fail_if_global, global_json  # noqa: E402

app = typer.Typer(help="Concierge MVP pilots: provision and list paying pilot users")

_VALID_PRODUCTS = ("digest", "report", "premium-briefing")
_VALID_FREQUENCIES = ("daily", "weekly")

_NO_CONFIG_ERROR = (
    "Error: No configuration found. Run 'autoinfo init' first. "
    "See docs/dev/required-api-keys.md for API key setup."
)


_PILOT_NON_PRODUCT_MD = ("gate-report-", "README", "SOURCES")


def _existing_product_files(user_dir: Path) -> list[Path]:
    """Product markdown files in *user_dir* (reports/readme excluded)."""
    return [p for p in user_dir.glob("*.md") if not p.name.startswith(_PILOT_NON_PRODUCT_MD)]


# ---------------------------------------------------------------------------
# Hermetic first-product seam
# ---------------------------------------------------------------------------


def _domain_sources(domain: str) -> list[tuple[str, str, str]]:
    """Return up to three configured sources as (url, type, platform)."""
    fallback = (f"https://example.com/{domain}", "web", "pilot-source")
    config_path = get_config_path()
    if config_path is None:
        return [fallback]
    try:
        config = load_config(config_path)
    except Exception:  # noqa: BLE001 — a malformed config must not block the pilot
        return [fallback]
    domain_cfg = next((d for d in config.domains if d.name == domain), None)
    if domain_cfg is None or not domain_cfg.sources:
        return [fallback]
    return [
        (
            source.url or fallback[0],
            source.type or "web",
            source.name or "pilot-source",
        )
        for source in domain_cfg.sources[:3]
    ]


def _hermetic_entries(domain: str) -> list[dict[str, Any]]:
    """Static, domain-agnostic fixtures for a clean pilot project.

    A clean checkout has no collected items, so the first product is built
    from three substantive sample entries with complete source provenance.
    The text adapts to *domain*; each entry's URL/type/platform comes from
    the domain's configured sources, so the same command works for every
    demo domain instead of hardcoding medical-research.
    """
    sources = _domain_sources(domain)
    collected = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    base: list[tuple[str, str]] = [
        (
            f"Evidence review: current practice and outcomes in {domain}",
            f"A structured review compares recent {domain} practice patterns "
            "with measured outcomes and identifies where the evidence base is "
            "still thin.",
        ),
        (
            f"Adoption signals and operational constraints in {domain}",
            f"A second analysis tracks adoption signals across {domain} and "
            "documents the operational constraints teams report when scaling.",
        ),
        (
            f"Updated guidance for {domain}: what changed and what to watch",
            f"A guidance update consolidates the latest {domain} evidence, "
            "flags changed recommendations, and lists the open questions to "
            "monitor.",
        ),
    ]
    entries: list[dict[str, Any]] = []
    for i, (title, summary) in enumerate(base, start=1):
        source_url, source_type, source_platform = sources[(i - 1) % len(sources)]
        entries.append(
            {
                "entry_id": f"mvp-fixture-{i}",
                "title": title,
                "summary": summary,
                "content": summary,
                "source_url": source_url,
                "source_type": source_type,
                "source_platform": source_platform,
                "source_label": source_platform,
                "relevance_score": 90.0 - i,
                "tags": "[]",
                "tier": "01-Raw",
                "collected_at": collected,
                "domain": domain,
            }
        )
    return entries


def _generate_first_product(
    product: str,
    domain: str,
    period: str,
    user_id: str,
    user_dir: Path,
) -> tuple[Path, list[dict[str, Any]]]:
    """Generate the pilot's first product via the hermetic seam.

    Patch set (mirror of ``regression-no-placeholder-magazine-tutorial`` /
    ``tests/output/test_product_routing.py``):

    - ``autoinfo.output.KBStore`` — static fixture entries injected
    - ``autoinfo.llm.LLMExtractor.extract`` — empty deterministic extraction
    - ``autoinfo.output._call_llm_for_digest`` — ``{}`` → the digest path
      fills synthesis deterministically from the real entries (#217 fallback)
    - report path additionally: ``_group_by_theme`` (one static group),
      ``_generate_executive_summary`` (static synthesis),
      ``_call_llm_for_report_synthesis`` (empty)

    Returns ``(product_path, fixture_entries)``.  Never touches the network
    or an LLM endpoint.
    """
    from unittest.mock import MagicMock, patch

    from autoinfo.models import ExtractionResult
    from autoinfo.output import (
        PRODUCT_TEMPLATES,
        generate_digest,
        generate_report,
    )

    entries = _hermetic_entries(domain)
    generated_at = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    file_name = f"{product}-{period}-{generated_at}.md"

    empty_extract = ExtractionResult(item_id="mvp-seam", title="", custom_fields={})
    group = [
        {
            "theme": f"{domain} developments",
            "description": f"Recent evidence tracked for the {domain} pilot.",
            "entries": entries,
        }
    ]
    synthesis = {
        "executive_summary": (
            f"This briefing summarizes three recent developments tracked for "
            f"the {domain} pilot: current practice and outcomes, adoption "
            "constraints, and updated guidance."
        ),
        "key_findings": [e["summary"] for e in entries],
        "recommendations": [
            f"Track new {domain} evidence against the current practice baseline.",
            f"Review adoption constraints before scaling the {domain} workflow.",
            f"Monitor the updated {domain} guidance for changes that affect the pilot.",
        ],
    }

    def _kb_mock() -> MagicMock:
        kb = MagicMock()
        kb.list_entries.return_value = list(entries)
        return kb

    product_template = None
    if product == "premium-briefing":
        product_template = next(
            row["template"] for row in PRODUCT_TEMPLATES if row["name"] == product
        )

    with (
        patch("autoinfo.output.KBStore", return_value=_kb_mock()),
        patch("autoinfo.llm.LLMExtractor.extract", return_value=empty_extract),
        patch("autoinfo.output._call_llm_for_digest", return_value={}),
    ):
        if product == "digest":
            out = generate_digest(
                domain=domain,
                period=period,
                format="markdown",
                user_id=user_id,
            )
        else:
            with (
                patch("autoinfo.output._group_by_theme", return_value=group),
                patch(
                    "autoinfo.output._generate_executive_summary",
                    return_value=dict(synthesis),
                ),
                patch(
                    "autoinfo.output._call_llm_for_report_synthesis",
                    return_value="",
                ),
            ):
                out = generate_report(
                    domain=domain,
                    format="markdown",
                    user_id=user_id,
                    product_template=product_template,
                )

    if not isinstance(out, str) or not out.strip():
        raise ValueError(f"hermetic generation produced no output for product '{product}'")
    product_path = user_dir / file_name
    product_path.write_text(out, encoding="utf-8")
    return product_path, entries


def _write_provenance(
    user_dir: Path,
    product_path: Path,
    entries: list[dict[str, Any]],
    *,
    product: str,
    domain: str,
    period: str,
    user_id: str,
    gate: dict[str, Any],
) -> Path:
    """Write ``provenance.json`` — per-entry source provenance + disclosure."""
    provenance = {
        "user_id": user_id,
        "domain": domain,
        "product": product,
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "hermetic-fixture",
        "hermetic": True,
        "llm_calls": 0,
        "seam": (
            "KBStore+LLM injection seam (autoinfo mvp init first-product "
            "seam; mirror of regression-no-placeholder-magazine-tutorial) — "
            "static fixture entries, deterministic synthesis, no network"
        ),
        "product_file": product_path.name,
        "entries": [
            {
                "title": e.get("title", ""),
                "source_url": e.get("source_url", ""),
                "source_type": e.get("source_type", ""),
                "source_platform": e.get("source_platform", ""),
                "collected_at": e.get("collected_at", ""),
            }
            for e in entries
        ],
        "gate_report": {
            "md": gate["md"].name,
            "json": gate["json"].name,
            "quality": gate["quality"],
        },
    }
    path = user_dir / "provenance.json"
    path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_sources(
    user_dir: Path,
    entries: list[dict[str, Any]],
    *,
    domain: str,
    product: str,
    contact: str,
) -> Path:
    """Write ``SOURCES.md`` mapping every key finding to its source URL."""
    lines = [
        "# Sources",
        "",
        f"Pilot product: `{product}` · domain: `{domain}`",
        "",
        "Every key finding in the product maps to one numbered source below.",
        "This pilot runs in hermetic fixture mode: entries are static fixtures "
        "injected through the KB seam, not live collected items. The URLs are "
        "the configured source endpoints; they are not fetched during init.",
        "",
        "| # | Claim | Source URL | Type | Platform | Collected |",
        "|---|-------|------------|------|----------|-----------|",
    ]
    for i, entry in enumerate(entries, start=1):
        claim = str(entry.get("summary") or entry.get("title") or "").replace("|", "\\|")
        lines.append(
            f"| {i} | {claim} | {entry.get('source_url', '')} | "
            f"{entry.get('source_type', '')} | {entry.get('source_platform', '')} | "
            f"{entry.get('collected_at', '')} |"
        )
    if contact.strip():
        lines.extend(["", f"Contact: {contact.strip()}"])
    path = user_dir / "SOURCES.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_readme(
    user_dir: Path,
    *,
    user_id: str,
    domain: str,
    product: str,
    frequency: str,
    product_path: Path,
    contact: str,
) -> Path:
    """Write the three-sentence pilot README (contact is a placeholder)."""
    contact_text = contact.strip() or "（待填写）"
    text = (
        f"# 给试点用户\n\n"
        f"这是为 {user_id} 生成的 {product} 试点产物，域为 {domain}，"
        f"按 {frequency} 频率更新。\n\n"
        f"打开 `{product_path.name}` 阅读；每一条结论都能在 `SOURCES.md` "
        f"找到来源。\n\n"
        f"有问题请联系：{contact_text}。\n"
    )
    path = user_dir / "README-给试点用户.md"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# `mvp init`
# ---------------------------------------------------------------------------


@app.command()
def init(
    user: str = typer.Option(..., "--user", help="Pilot end-user ID"),
    domain: str = typer.Option(
        ..., "--domain", help="Demo domain to import (e.g. medical-research)"
    ),
    product: str = typer.Option(
        "digest",
        "--product",
        help="First product: digest, report, premium-briefing",
    ),
    frequency: str = typer.Option(
        "weekly", "--frequency", help="Delivery frequency: daily, weekly"
    ),
    contact: str = typer.Option(
        "",
        "--contact",
        help="Contact placeholder for the pilot README (no PII required)",
    ),
) -> None:
    """Provision a Concierge MVP pilot end-to-end (idempotent).

    Creates the premium end-user profile + subscription (no Stripe), imports
    the demo domain config, generates the first product via the hermetic
    seam, and writes the ``mvp/<user>/`` delivery directory: product,
    ``01-QA-GATES/`` reports, ``SOURCES.md``, ``README-给试点用户.md``,
    ``provenance.json`` and ``user.json``.
    """
    if product not in _VALID_PRODUCTS:
        fail_if_global(
            "ValidationError",
            f"Unknown product '{product}'. Valid products: {', '.join(_VALID_PRODUCTS)}",
        )
        typer.echo(
            f"Error: Unknown product '{product}'. Valid products: {', '.join(_VALID_PRODUCTS)}",
            err=True,
        )
        raise typer.Exit(code=1)
    if frequency not in _VALID_FREQUENCIES:
        fail_if_global(
            "ValidationError",
            f"Unknown frequency '{frequency}'. Valid frequencies: {', '.join(_VALID_FREQUENCIES)}",
        )
        typer.echo(
            f"Error: Unknown frequency '{frequency}'. "
            f"Valid frequencies: {', '.join(_VALID_FREQUENCIES)}",
            err=True,
        )
        raise typer.Exit(code=1)
    if not user or "/" in user or "\\" in user or user in (".", ".."):
        fail_if_global(
            "ValidationError",
            f"invalid user id {user!r} — must be a non-empty path-safe identifier (no slashes)",
        )
        typer.echo(
            f"Error: invalid user id {user!r} — must be a non-empty path-safe "
            f"identifier (no slashes)",
            err=True,
        )
        raise typer.Exit(code=1)

    if get_config_path() is None:
        fail_if_global("ConfigNotFound", _NO_CONFIG_ERROR.removeprefix("Error: "))
        typer.echo(_NO_CONFIG_ERROR, err=True)
        raise typer.Exit(code=1)

    def _echo(*args: Any, **kwargs: Any) -> None:
        if not global_json():
            typer.echo(*args, **kwargs)

    # --- (1) Domain import FIRST (clean early error before any user writes).
    # Reuses domain.py import_cmd verbatim — the --from-demo source of truth.
    from autoinfo.cli.domain import import_cmd as _import_demo_domain  # noqa: PLC0415
    from autoinfo.user_store import (  # noqa: PLC0415
        create_profile,
        create_subscription,
        get_profile,
        list_subscriptions,
    )

    _import_demo_domain(from_demo=domain)

    # --- (2) EndUserProfile — premium fast-path mechanism -------------------
    profile = get_profile(user)
    if profile is None:
        create_profile(
            user_id=user,
            name=user,
            email="",
            status="active",
            tier="premium",
        )
        _echo(f"Profile '{user}' created (tier=premium, status=active).")
    else:
        _echo(
            f"Profile '{user}' already exists "
            f"(tier={profile.tier}, status={profile.status}) — skipping."
        )

    # --- (3) Premium subscription (no Stripe) -------------------------------
    sub = next(
        (s for s in list_subscriptions(user) if s.plan == "premium" and s.tier == "premium"),
        None,
    )
    if sub is None:
        sub = create_subscription(
            user_id=user,
            plan="premium",
            status="active",
            tier="premium",
            auto_renew=True,
            channels=[],
            domains=[domain],
            products=[product],
            platform_limit=8,
            domain_limit=8,
            raw_access=False,
            processed_access=True,
            max_products=8,
            max_frequency="daily",
            allow_custom=True,
        )
        _echo(
            f"Subscription created: {sub.subscription_id} "
            f"(plan=premium, tier=premium, status=active)."
        )
    else:
        _echo(f"Subscription already exists ({sub.subscription_id}, plan=premium) — skipping.")

    # --- (4) First product via the hermetic seam ----------------------------
    user_dir = Path.cwd() / "mvp" / user
    existing_products = _existing_product_files(user_dir) if user_dir.is_dir() else []

    generated_product_path: Path | None = None
    gate: dict[str, Any] | None = None
    if existing_products:
        _echo(
            f"Pilot '{user}' already has a first product "
            f"({existing_products[-1].name}) — generation skipped."
        )
    else:
        user_dir.mkdir(parents=True, exist_ok=True)
        try:
            product_path, entries = _generate_first_product(
                product=product,
                domain=domain,
                period=frequency,
                user_id=user,
                user_dir=user_dir,
            )
        except Exception as exc:  # noqa: BLE001 — clean CLI error, no traceback
            fail_if_global("InternalError", f"first product generation failed: {exc}")
            typer.echo(f"Error: first product generation failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        from autoinfo.delivery.gate_report import write_gate_report  # noqa: PLC0415

        # Cwd-relative product path (mirrors validation_delivery's
        # relativized artifact paths, #143) so the report key never embeds
        # an absolute mount/user prefix.
        try:
            key_path = product_path.relative_to(Path.cwd())
        except ValueError:
            key_path = product_path
        gate_dir = user_dir / "01-QA-GATES"
        gate_dir.mkdir(parents=True, exist_ok=True)
        gate = write_gate_report(gate_dir, key_path, kind="PROCESSED", key=product)
        generated_product_path = product_path
        _write_sources(
            user_dir,
            entries,
            domain=domain,
            product=product,
            contact=contact,
        )
        _write_provenance(
            user_dir,
            product_path,
            entries,
            product=product,
            domain=domain,
            period=frequency,
            user_id=user,
            gate=gate,
        )
        _echo(
            f"First product generated: {product_path.as_posix()} "
            f"(gate: {gate['quality']}, hermetic seam: no LLM call)."
        )

    product_for_readme = generated_product_path or (
        existing_products[-1] if existing_products else None
    )
    if product_for_readme is not None:
        _write_readme(
            user_dir,
            user_id=user,
            domain=domain,
            product=product,
            frequency=frequency,
            product_path=product_for_readme,
            contact=contact,
        )

    # --- (5) user.json placeholder metadata ---------------------------------
    meta_path = user_dir / "user.json"
    meta = {
        "user_id": user,
        "name": user,
        "email": "",
        "contact": contact,
        "domain": domain,
        "product": product,
        "frequency": frequency,
        "tier": "premium",
        "plan": "premium",
        "status": "active",
        "subscription_id": sub.subscription_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mvp_dir": user_dir.as_posix(),
        "placeholder": True,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if emit_if_global(
        {
            "user_id": user,
            "domain": domain,
            "product": product,
            "frequency": frequency,
            "contact": contact,
            "subscription_id": sub.subscription_id,
            "mvp_dir": user_dir.as_posix(),
            "product_path": (generated_product_path.as_posix() if generated_product_path else None),
            "gate": gate,
            "already_existed": bool(existing_products),
        }
    ):
        return

    typer.echo(
        f"MVP pilot ready: {user_dir.as_posix()} (user={user}, domain={domain}, "
        f"product={product}, frequency={frequency})"
    )


# ---------------------------------------------------------------------------
# `mvp list`
# ---------------------------------------------------------------------------


@app.command(name="list")
def list_cmd() -> None:
    """List MVP pilot users with subscription status and latest product."""
    from autoinfo.user_store import get_profile, list_subscriptions  # noqa: PLC0415

    base = Path.cwd() / "mvp"
    pilots: list[tuple[Path, dict[str, Any]]] = []
    if base.is_dir():
        for d in sorted(base.iterdir()):
            meta_path = d / "user.json"
            if d.is_dir() and meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    meta = {}
                if isinstance(meta, dict):
                    pilots.append((d, meta))

    items: list[dict[str, Any]] = []
    for d, meta in pilots:
        uid = str(meta.get("user_id") or d.name)
        profile = get_profile(uid)
        tier = (profile.tier if profile else None) or str(meta.get("tier", "?"))
        status = (profile.status if profile else None) or str(meta.get("status", "?"))
        subs = list_subscriptions(uid)
        plan = subs[0].plan if subs else str(meta.get("plan", "?"))
        sub_status = subs[0].status if subs else "?"
        products = _existing_product_files(d)
        latest = max(products, key=lambda p: p.stat().st_mtime) if products else None
        product_name = str(meta.get("product", "?"))
        gate_json = d / "01-QA-GATES" / f"gate-report-{product_name}.json"
        if not gate_json.is_file():
            gate_json = d / f"gate-report-{product_name}.json"
        gate_passed: bool | None = None
        if gate_json.is_file():
            try:
                gate_payload = json.loads(gate_json.read_text(encoding="utf-8"))
                gate_passed = bool(gate_payload.get("delivered"))
            except (json.JSONDecodeError, OSError):
                gate_passed = None
        generated_at = (
            datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M"
            )
            if latest
            else "-"
        )
        items.append(
            {
                "user_id": uid,
                "domain": meta.get("domain", "?"),
                "tier": tier,
                "plan": plan,
                "status": status,
                "subscription_status": sub_status,
                "product": product_name,
                "frequency": meta.get("frequency", "?"),
                "product_generated": latest is not None,
                "generated_at": generated_at,
                "gate_passed": gate_passed,
                "latest_product": latest.as_posix() if latest else None,
            }
        )

    if emit_if_global({"items": items, "count": len(items)}):
        return

    if not pilots:
        typer.echo(
            "No MVP pilot users yet. Run 'autoinfo mvp init --user <id> "
            "--domain <domain>' to provision one."
        )
        return

    typer.echo(f"MVP pilot users ({len(pilots)}):")
    header = (
        f"{'USER':<12} {'DOMAIN':<22} {'PRODUCT':<18} {'FREQUENCY':<10} "
        f"{'GENERATED':<9} {'GENERATED_AT':<16} {'GATE':<6}"
    )
    typer.echo(header)
    typer.echo("-" * len(header))
    for item in items:
        gate = (
            "PASS"
            if item["gate_passed"] is True
            else ("FAIL" if item["gate_passed"] is False else "?")
        )
        typer.echo(
            f"{item['user_id']:<12} {str(item['domain']):<22} "
            f"{str(item['product']):<18} {str(item['frequency']):<10} "
            f"{('yes' if item['product_generated'] else 'no'):<9} "
            f"{item['generated_at']:<16} {gate:<6}"
        )
        typer.echo(
            f"      tier={item['tier']} plan={item['plan']} status={item['status']} "
            f"subscription={item['subscription_status']} latest product: "
            f"{item['latest_product'] or 'none'}"
        )


if __name__ == "__main__":
    app()
