"""Product delivery gates and quality guards.

Extracted from ``output/__init__.py`` (#582 phase 3). ``_llm_key_available`` is
read through the hub at call time because tests patch it there; the contract
types come from the dependency-free ``output.contracts`` leaf.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable, cast

from autoinfo.config import Config
from autoinfo.output.contracts import (
    _DELIVERY_GATES_BYPASS,
    DeliveryOutput,
    _DeliveryGatesBypass,
)
from autoinfo.output.entries import _contains_raw_llm_leak
from autoinfo.prompts import render_prompt
from autoinfo.section_parser import _apply_format_sections, _sections_from_headings

logger = logging.getLogger("autoinfo.output")


def _resolve_delivery_gate_configs(
    domain: str,
    delivery_gate_configs: dict[str, dict[str, Any]] | _DeliveryGatesBypass | None,
) -> dict[str, dict[str, Any]] | None:
    """Resolve the effective delivery-gate config for *domain*.

    - An explicit dict is used as-is.
    - The ``_DELIVERY_GATES_BYPASS`` sentinel resolves to ``None`` (gates
      bypassed, plain ``str`` output).
    - ``None`` resolves from the project config: the domain's
      ``delivery_gates`` first, falling back to the global
      ``delivery_gates``.  Returns ``None`` when the config carries no
      delivery gates (backward-compatible plain ``str`` output).
    """
    if delivery_gate_configs is _DELIVERY_GATES_BYPASS:
        return None
    if delivery_gate_configs is not None:
        # Both guards passed: not the sentinel, not None -> provably a dict.
        return cast(dict[str, dict[str, Any]], delivery_gate_configs)
    from autoinfo.output import get_config_path, load_config

    try:
        cfg_path = get_config_path()
        if cfg_path is None:
            return None
        cfg = load_config(cfg_path)
    except Exception:
        return None
    domain_cfg = next((d for d in cfg.domains if d.name == domain), None)
    gates = domain_cfg.delivery_gates if domain_cfg is not None else {}
    if not gates:
        gates = cfg.delivery_gates
    if not gates:
        return None
    return {
        name: {
            "enabled": dgc.enabled,
            "action_on_failure": dgc.action_on_failure,
        }
        for name, dgc in gates.items()
    }


def _sections_from_rendered_body(
    body: str, output_format: str, product_type: str
) -> dict[str, str] | None:
    """Detect D1 sections from the RENDERED body.

    Returns a ``{key_findings, summary, recommendations}`` mapping for
    markdown/html bodies (possibly all-empty when the body is empty), or
    ``None`` for formats that cannot be parsed (json/agent/audio/...).
    """
    if output_format not in ("markdown", "html"):
        return None
    sections = _sections_from_headings(body, product_type)
    return _apply_format_sections(sections, product_type)


_MIN_PRODUCT_CONTENT_CHARS = 200


_MIN_PRODUCT_HEADINGS = 1


def _product_body_text_len(body: str, output_format: str) -> int:
    """Length of the rendered body's visible text (tags stripped for html)."""
    if output_format == "html":
        return len(re.sub(r"<[^>]+>", " ", body).strip())
    return len(body.strip())


def _product_heading_count(body: str, output_format: str) -> int:
    """Number of headings in the rendered body (md ``#`` or html ``<hN>``)."""
    if output_format == "html":
        return len(re.findall(r"<h[1-6][^>]*>", body, re.IGNORECASE))
    return len(re.findall(r"^#{1,6}\s+", body, re.MULTILINE))


_PRODUCT_JUDGE_ENABLED = True  # env AUTOINFO_PRODUCT_JUDGE=0 disables


def _product_judge_enabled() -> bool:
    raw = os.environ.get("AUTOINFO_PRODUCT_JUDGE", "")
    if raw.strip().lower() in ("0", "false", "no", "off"):
        return False
    return _PRODUCT_JUDGE_ENABLED


def _llm_key_available(llm_config: Config | None) -> bool:
    """True when an LLM API key is resolvable (config or environment)."""
    if llm_config is not None and (llm_config.llm.api_key or "").strip():
        return True
    if os.environ.get("AUTOINFO_LLM_API_KEY", "").strip():
        return True
    from autoinfo.output import get_config_path, load_config

    try:
        cfg_path = get_config_path()
        if cfg_path is not None and cfg_path.is_file():
            cfg = load_config(cfg_path)
            if (cfg.llm.api_key or "").strip():
                return True
    except Exception:
        pass
    return False


def _build_product_judge_prompt(body: str, output_format: str) -> str:
    return render_prompt("product_judge", output_format=output_format, body=body)


def _escalate_product_judge_prompt(prompt: str, reason: str) -> str:
    return (
        prompt + f"\n\nA previous review found the body inadequate: {reason}. "
        "Re-review carefully and return the same JSON verdict shape."
    )


def _parse_product_judge_verdict(response: Any) -> tuple[bool, str] | None:
    """Parse the judge's JSON verdict; ``None`` when unparseable."""
    content = getattr(response, "content", None)
    if content is None:
        content = response
    if isinstance(content, str):
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return None
    elif isinstance(content, dict):
        data = content
    else:
        return None
    if not isinstance(data, dict) or "ok" not in data:
        return None
    return bool(data["ok"]), str(data.get("reason") or "")


def _run_product_judge(
    body: str,
    output_format: str,
    product_type: str,
    llm_config: Config | None = None,
) -> tuple[bool, str]:
    """LLM-judge the rendered body for non-trivial content.

    Returns ``(passed, reason)``.  Fails open on any error (no key, network,
    parse) so the judge never blocks a product on infrastructure failure.
    Retries once with escalating context before failing.
    """
    if not _product_judge_enabled():
        return True, ""
    if product_type.upper() != "PROCESSED" or output_format not in ("markdown", "html"):
        return True, ""
    from autoinfo.output import _llm_key_available as _hub_llm_key_available

    if not _hub_llm_key_available(llm_config):
        return True, ""
    try:
        prompt = _build_product_judge_prompt(body, output_format)
        from autoinfo.output import call_with_fallback

        for attempt in range(2):
            response = call_with_fallback(
                [{"role": "user", "content": prompt}],
                config=llm_config,
                task="product_judge",
                json_mode=True,
            )
            verdict = _parse_product_judge_verdict(response)
            if verdict is not None:
                ok, reason = verdict
                if ok:
                    return True, ""
                if attempt == 0:
                    prompt = _escalate_product_judge_prompt(prompt, reason)
                    continue
                return False, reason
        return False, "judge returned no verdict"
    except Exception:
        logger.debug("Product judge skipped (fail-open)", exc_info=True)
        return True, ""


_MIN_SUBSTANTIVE_SUMMARY_CHARS = 40


_SYNTHETIC_ENTRY_MARKERS = (
    "kb tier matrix",
    "kb-tier-matrix",
    "autoinfo.dev",
    "test entry",
    "placeholder entry",
)


def _is_substantive_entry(entry: dict[str, Any]) -> bool:
    """Return True when *entry* carries material a product could honestly report.

    Issue #446: a domain whose entire knowledge base is one synthetic
    tier-matrix fixture (``summary: ''``, ``source_url`` on a reserved test
    host) still passes a ``if not entries`` check, so synthesis would be asked
    to write an Executive Summary with nothing to draw on. Counting entries
    cannot see that; checking whether they carry material can.

    Against the authoritative store (``autoinfo.db`` — 1821 entries, 23 domains)
    this blocks 1 domain: ``default``, whose only two entries are the literal
    rows ``x`` and ``y`` with empty summaries and no URL.

    An earlier claim that it blocked 9 domains and that a fabricated
    "OpenAI Jalapeño" chip motivated it is withdrawn — that chip is a real
    collected entry (techcrunch, 2026-08-25). The 9-domain figure came from
    reading the ``knowledge/`` file tree, which holds one file for some domains,
    instead of the database the pipeline actually reads.
    """
    title = str(entry.get("title") or "").strip()
    summary = str(entry.get("summary") or "").strip()
    url = str(entry.get("source_url") or "").strip()

    probe = f"{title} {url}".lower()
    if any(marker in probe for marker in _SYNTHETIC_ENTRY_MARKERS):
        return False
    return bool(url) or len(summary) >= _MIN_SUBSTANTIVE_SUMMARY_CHARS


def _apply_min_content_guard(
    result: DeliveryOutput,
    entries: list[dict[str, Any]],
    product_type: str,
) -> DeliveryOutput:
    """Force the blocked flag when a PROCESSED product has no usable source.

    Layer 1 min-content guard (issue #298): a product with zero usable entries
    after filtering must never be silently shipped as an empty shell.

    Issue #446 extends it: zero *substantive* entries is the same failure with
    a worse disguise. Counting entries alone let a domain whose only knowledge
    base row is a synthetic test fixture ship eight products full of invented
    facts.
    """
    if product_type == "RAW":
        return result

    def _block(reason: str) -> DeliveryOutput:
        result.delivery_blocked = True
        if not any("min-content guard" in w for w in result.warnings):
            result.warnings.append(f"min-content guard: {reason}")
        return result

    if not entries:
        return _block("0 usable entries after filtering")

    substantive = sum(1 for entry in entries if _is_substantive_entry(entry))
    if substantive == 0:
        return _block(
            f"0 of {len(entries)} entr(ies) carry substantive source material "
            "(empty summary or synthetic test fixture); synthesis would have to "
            "invent content — collect real material before generating"
        )
    return result


def _apply_delivery_gates(
    rendered_output: str,
    output_format: str,
    entries: list[dict[str, Any]],
    context: dict[str, Any],
    product_type: str,
    delivery_gate_configs: dict[str, dict[str, Any]] | None = None,
    fallback_render_fn: Callable[[], str] | None = None,
    llm_config: Config | None = None,
) -> DeliveryOutput:
    """Run D1-D3 delivery gates on rendered output.

    Parameters
    ----------
    rendered_output:
        The rendered output string (markdown, html, or json).
    output_format:
        The format of the rendered output (``"markdown"``, ``"html"``,
        ``"json"``).
    entries:
        List of KB entry dicts used to produce the output.
    context:
        Digest or report context dict.  May contain ``llm_synthesis``
        (for D1 completeness checks).
    product_type:
        ``"PROCESSED"`` or ``"RAW"``.  RAW skips all delivery gates.
    delivery_gate_configs:
        Optional dict of ``{gate_name: config_dict}``.  When ``None``,
        no gates are run and the output is returned as-is.
    fallback_render_fn:
        Optional callable that re-renders the output as markdown.
        Invoked when D2 fails with ``action="fallback"``.
    llm_config:
        Optional :class:`Config` for the LLM product judge (layer 3).

    Returns
    -------
    DeliveryOutput
        Contains the (possibly modified) output, gate results, and
        delivery metadata (blocked flag, warnings).
    """
    if delivery_gate_configs is None:
        return DeliveryOutput(
            output=rendered_output,
            gate_results={},
            delivery_format=output_format,
        )

    # Deferred imports to avoid circular dependencies
    from autoinfo.quality import QualityResult, run_delivery_gates  # noqa: PLC0415, F401

    llm_synthesis: dict[str, Any] = context.get("llm_synthesis", {})

    # D1 completeness is checked against the RENDERED body (issue #298): a
    # body that is empty/garbled but whose synthesis dict is non-empty must
    # fail D1.  Fall back to the synthesis dict only when the body cannot be
    # parsed (json/agent/audio/...).
    body_sections = _sections_from_rendered_body(rendered_output, output_format, product_type)
    if body_sections is not None:
        key_findings: Any = body_sections.get("key_findings", "")
        summary: Any = body_sections.get("summary", "")
        recommendations: Any = body_sections.get("recommendations", "")
    else:
        key_findings = llm_synthesis.get("key_findings", [])
        summary = llm_synthesis.get("executive_summary", "")
        recommendations = llm_synthesis.get("recommendations", [])

    # Build product_output dict expected by run_delivery_gates
    product_output: dict[str, Any] = {
        "product_type": product_type,
        "format": output_format,
        "body": rendered_output,
        "key_findings": key_findings,
        "summary": summary,
        "recommendations": recommendations,
        "entries": entries,
    }

    gate_results = run_delivery_gates(product_output, context, delivery_gate_configs)
    warnings: list[str] = []
    delivery_blocked = False
    output = rendered_output
    final_format = output_format

    # --- D1: Completeness -----------------------------------------------
    d1_result = gate_results.get("D1-ProductCompleteness")
    if d1_result is not None and not d1_result.passed:
        action = d1_result.details.get("action", "block")
        if action == "block":
            error_detail = d1_result.details.get("error", "incomplete product")
            logger.warning("Delivery blocked by D1: %s", error_detail)
            delivery_blocked = True
            warnings.append(f"D1 blocked: {error_detail}")

    # --- D2: Format integrity (ToS block + format fallback + content) ------
    d2_result = gate_results.get("D2-FormatIntegrity")
    if d2_result is not None:
        # Content-substance check (issue #298): markdown/html bodies must
        # carry a minimum amount of content and at least one heading — the
        # quality.py D2 check treats markdown as "trivially valid".
        _leak_detected = bool(
            rendered_output
            and output_format in ("markdown", "html")
            and _contains_raw_llm_leak(rendered_output)
        )
        if (
            d2_result.passed
            and output_format in ("markdown", "html")
            and product_type.upper() != "RAW"
        ):
            text_len = _product_body_text_len(rendered_output, output_format)
            heading_count = _product_heading_count(rendered_output, output_format)
            if (
                text_len < _MIN_PRODUCT_CONTENT_CHARS
                or heading_count < _MIN_PRODUCT_HEADINGS
                or _leak_detected
            ):
                d2_result = QualityResult(
                    gate_name="D2-FormatIntegrity",
                    passed=False,
                    score=0.0,
                    flagged=True,
                    details={
                        "action": "fallback",
                        "format": output_format,
                        "valid": False,
                        "error": (
                            f"insufficient content: {text_len} chars, "
                            f"{heading_count} headings"
                            + ("; raw LLM error text detected" if _leak_detected else "")
                        ),
                        "content_chars": text_len,
                        "heading_count": heading_count,
                    },
                )
                gate_results["D2-FormatIntegrity"] = d2_result

        # ToS-based block: RAW delivery from restricted/sensitive sources (F46)
        if not d2_result.passed:
            action = d2_result.details.get("action", "")
            if action == "block":
                error_detail = d2_result.details.get("error", "delivery blocked")
                logger.warning("Delivery blocked by D2 (ToS): %s", error_detail)
                delivery_blocked = True
                warnings.append(f"D2 blocked (ToS): {error_detail}")

        # Format integrity fallback (flagged with action="fallback")
        if d2_result.flagged:
            action = d2_result.details.get("action", "fallback")
            if action == "fallback":
                d2_error = d2_result.details.get("error", "format integrity issue")
                if fallback_render_fn is not None and output_format != "markdown":
                    logger.warning(
                        "D2 fallback: %s — re-rendering as markdown",
                        d2_error,
                    )
                    output = fallback_render_fn()
                    final_format = "markdown"
                    warnings.append("D2 fallback: re-rendered as markdown")
                else:
                    logger.warning("D2 flagged: %s", d2_error)
                    warnings.append(f"D2 flagged: {d2_error}")
            elif action == "flag" and d2_result.details.get("self_claim"):
                # #445 escalation: an entity the body never states cannot block
                # (measured ~27% false-positive rate), but it must reach the
                # delivery log and the packaged gate report — a silent flag is
                # not an escalation.
                raw_escalation = d2_result.details.get("self_claim_orphan_entities")
                escalation = (
                    [str(entity) for entity in raw_escalation]
                    if isinstance(raw_escalation, list)
                    else []
                )
                logger.warning("D2 self-claim escalation: %s", "; ".join(escalation[:3]))
                warnings.append(
                    f"D2 escalation: {len(escalation)} ungrounded narrative entity "
                    f"name(s), first: {escalation[0] if escalation else 'n/a'}"
                )

    # --- D3: Freshness (flag) -------------------------------------------
    d3_result = gate_results.get("D3-Freshness")
    if d3_result is not None and d3_result.flagged:
        stale = d3_result.details.get("stale_count", 0)
        total = d3_result.details.get("total_entries", 0)
        if stale:
            logger.warning("D3 flagged: %d/%d stale entries", stale, total)
            warnings.append(f"D3: {stale}/{total} entries stale")

    # --- LLM product judge (issue #298 — layer 3, optional) --------------
    if not delivery_blocked:
        judge_passed, judge_reason = _run_product_judge(
            output, final_format, product_type, llm_config
        )
        if not judge_passed:
            logger.warning("Product judge blocked: %s", judge_reason)
            delivery_blocked = True
            warnings.append(f"product judge blocked: {judge_reason}")

    return DeliveryOutput(
        output=output,
        gate_results=gate_results,
        delivery_blocked=delivery_blocked,
        delivery_format=final_format,
        warnings=warnings,
    )
