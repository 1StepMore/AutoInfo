"""RED-by-design regression file for issue #400 (single-source section parser).

The markdown section parser exists in THREE places with identical function
bodies but separate module-level tables:

- ``src/autoinfo/delivery/gate_report.py``
- ``src/autoinfo/output/__init__.py``
- ``scripts/validation_delivery.py``

Issue #396 proved the hazard of that layout: the alias fix was applied to two
copies while ``scripts/validation_delivery.py`` silently kept the stale
pre-#396 table, so the validation-packaging path never received the fix. This
file pins the refactor that extracts ONE canonical implementation into
``src/autoinfo/section_parser.py`` and makes all three sites re-export the
SAME objects — object identity, not value equality, so that no local
redefinition may remain.

It also pins the behavioural defects proven during the #400 investigation:

- ``_PRODUCT_TYPE_REQUIRED_SECTIONS`` is keyed by underscore spellings
  (``premium_briefing``) while the generation path passes hyphen family
  names (``premium-briefing``); the lookup misses and silently falls back to
  the ``report`` rules (all three sections required), D1-blocking complete
  premium/enterprise/magazine products.
- ``magazine_digest`` is D1-blocked on both spellings: the template emits no
  summary-alias heading and the any-content fallback tuple only knows
  ``("column", "magazine")``; the hardened guard
  ``"key_findings" not in found`` must also stop an already-found summary
  from suppressing the required key_findings fallback.
- The skeleton-aware ``_is_empty_placeholder`` from ``autoinfo.output`` must
  be adopted everywhere (the other two copies let an LLM skeleton echo such
  as ``<finding 1>`` satisfy D1), while B-04 (#172) placeholder rejection
  (``_No exercises provided._``) must stay intact.

The file is RED against the current code: ``autoinfo.section_parser`` does
not exist yet and the three sites carry independent objects. The B-04
preservation tests document invariants that are green today and must remain
green after the refactor.

All tests are hermetic: pure string parsing and module loading, no files
written, no LLM, no network, no domain state.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Load the real scripts/validation_delivery.py with the same
# spec_from_file_location pattern as tests/validation/test_validation_delivery.py.
# The script inserts <repo>/src into sys.path itself before importing
# autoinfo, so this mirrors the sibling test's handling exactly.
_VD_SPEC = importlib.util.spec_from_file_location(
    "validation_delivery_section_parser_tests", ROOT / "scripts" / "validation_delivery.py"
)
assert _VD_SPEC is not None and _VD_SPEC.loader is not None
vd = importlib.util.module_from_spec(_VD_SPEC)
_VD_SPEC.loader.exec_module(vd)

from autoinfo import output as output_mod  # noqa: E402
from autoinfo.delivery import gate_report as gr  # noqa: E402

#: The three sites that must re-export ONE implementation (#396 lesson).
_SITES: tuple[tuple[str, ModuleType], ...] = (
    ("autoinfo.delivery.gate_report", gr),
    ("autoinfo.output", output_mod),
    ("scripts/validation_delivery.py", vd),
)

#: Function names that must resolve to the same object at every site.
_SHARED_FUNCTIONS: tuple[str, ...] = (
    "_sections_from_headings",
    "_apply_format_sections",
    "_is_empty_placeholder",
)

#: Module-level table names that must resolve to the same object everywhere.
_SHARED_TABLES: tuple[str, ...] = (
    "_SECTION_HEADING_ALIASES",
    "_PRODUCT_TYPE_REQUIRED_SECTIONS",
)


def _load_section_parser() -> ModuleType | None:
    """Resolve ``autoinfo.section_parser`` without breaking collection.

    Returns ``None`` while the canonical module does not exist yet (the
    pre-refactor state) so tests fail with a readable RED message instead of
    an ImportError during collection.
    """
    try:
        spec = importlib.util.find_spec("autoinfo.section_parser")
    except (ImportError, ValueError):
        return None
    if spec is None or spec.loader is None:
        return None
    return importlib.import_module("autoinfo.section_parser")


def _canonical() -> ModuleType:
    """Return the canonical module, or fail with the migration message."""
    module = _load_section_parser()
    if module is None:
        pytest.fail(
            "autoinfo.section_parser does not exist yet - the issue #400 "
            "single-source refactor (ONE section parser in "
            "src/autoinfo/section_parser.py, re-exported by gate_report, "
            "output and scripts/validation_delivery.py) is not applied. "
            "no local redefinition may remain."
        )
    return module


# ---------------------------------------------------------------------------
# Identity / no-duplication guard (the issue #396 class of bug)
# ---------------------------------------------------------------------------


class TestSingleSourceImplementation:
    """All three sites must re-export ONE implementation (#396/#400).

    Issue #396 fixed the alias table in two of the three copies;
    ``scripts/validation_delivery.py`` silently kept the stale pre-#396
    table. Object identity is the only drift-proof guard: a re-export cannot
    diverge, a copy can.
    """

    def test_no_local_redefinitions_across_sites(self) -> None:
        """Every shared name must be the SAME object at all three sites."""
        for name in _SHARED_FUNCTIONS + _SHARED_TABLES:
            resolved: list[tuple[str, object]] = [
                (label, getattr(module, name, None)) for label, module in _SITES
            ]
            missing = [label for label, attr in resolved if attr is None]
            assert not missing, (
                f"issue #400: '{name}' no longer resolves at {missing}; the "
                "re-export surface must keep every site working"
            )
            first_label, first = resolved[0]
            for label, attr in resolved[1:]:
                assert attr is first, (
                    f"issue #396/#400: '{name}' is defined independently in "
                    f"'{label}' and in '{first_label}' - every site must "
                    "re-export autoinfo.section_parser; no local redefinition "
                    "may remain"
                )

    def test_sites_reexport_the_canonical_section_parser_module(self) -> None:
        """The shared object must be the canonical section_parser object."""
        canonical = _canonical()
        for name in _SHARED_FUNCTIONS + _SHARED_TABLES:
            for label, module in _SITES:
                assert getattr(module, name, None) is getattr(canonical, name, None), (
                    f"issue #400: '{name}' at '{label}' is not the canonical "
                    "autoinfo.section_parser object; no local redefinition "
                    "may remain"
                )


# ---------------------------------------------------------------------------
# Alias-table freshness (issue #396 missed third copy)
# ---------------------------------------------------------------------------


class TestAliasTableFreshness:
    """The #396 aliases must exist at every site - including the third one.

    ``scripts/validation_delivery.py`` never received the #396 alias fix: its
    table lacks both "key takeaways" and "recommended actions", so a premium
    product packaged through validation delivery parsed with ``summary``
    alone. After the single-sourcing this is implied by object identity; the
    explicit membership assert keeps the requirement legible.
    """

    @pytest.mark.parametrize(
        ("canonical_key", "alias"),
        [("key_findings", "key takeaways"), ("recommendations", "recommended actions")],
    )
    def test_every_site_knows_the_issue_396_aliases(self, canonical_key: str, alias: str) -> None:
        for label, module in _SITES:
            table: dict[str, tuple[str, ...]] = module._SECTION_HEADING_ALIASES
            assert alias in table[canonical_key], (
                f"issue #396: alias table at '{label}' is missing '{alias}' - "
                "the missed third copy (scripts/validation_delivery.py) must "
                "carry the same #396 aliases"
            )


# ---------------------------------------------------------------------------
# product_type normalization (issue #400 finding F9 - the D1-block proof)
# ---------------------------------------------------------------------------


class TestProductTypeNormalization:
    """Hyphen family names must resolve like their underscore table keys.

    ``_PRODUCT_TYPE_REQUIRED_SECTIONS`` keys are underscore spellings
    (``premium_briefing``) but the generation path passes the hyphen family
    name (``premium-briefing``; ``product_type = report_family`` in
    autoinfo.output). The lookup misses, silently falls back to the
    ``report`` rules (all three sections required) and a complete premium
    briefing is D1-blocked. The refactor adds the idempotent normalizer
    ``pt.strip().lower().replace("-", "_")``.
    """

    @pytest.mark.parametrize(
        ("hyphen", "underscore"),
        [
            ("premium-briefing", "premium_briefing"),
            ("enterprise-briefing", "enterprise_briefing"),
            ("magazine-digest", "magazine_digest"),
        ],
    )
    def test_hyphen_and_underscore_spellings_agree(self, hyphen: str, underscore: str) -> None:
        mapped_hyphen: dict[str, str] = output_mod._apply_format_sections({}, hyphen)
        mapped_underscore: dict[str, str] = output_mod._apply_format_sections({}, underscore)
        assert mapped_hyphen == mapped_underscore, (
            f"issue #400: product_type '{hyphen}' resolves differently from "
            f"'{underscore}' - the required-section lookup must normalize "
            "hyphens to underscores"
        )

    @pytest.mark.parametrize("spelling", ["PREMIUM-BRIEFING", " premium-briefing "])
    def test_normalization_is_idempotent(self, spelling: str) -> None:
        """Case/whitespace variants must land on the same required set."""
        expected: dict[str, str] = output_mod._apply_format_sections({}, "premium_briefing")
        assert output_mod._apply_format_sections({}, spelling) == expected, (
            f"issue #400: product_type {spelling!r} must normalize "
            "(strip/lower/hyphen-to-underscore) to the briefing required set"
        )

    def test_premium_briefing_hyphen_resolves_briefing_required_set(self) -> None:
        """D1-block proof: 'premium-briefing' maps like ('summary',) required.

        key_findings/recommendations are non-required for a briefing so they
        get the 'present' marker; under today's report fallback they stay
        empty and D1 rejects a complete premium product.
        """
        expected = {
            "key_findings": "present",
            "summary": "",
            "recommendations": "present",
        }
        mapped: dict[str, str] = output_mod._apply_format_sections({}, "premium-briefing")
        assert mapped == expected, (
            "issue #400: 'premium-briefing' must resolve to the briefing "
            "required set ('summary',), not the report 3-tuple - today the "
            "hyphen spelling falls back to report and leaves key_findings "
            "empty, which D1-blocks the product"
        )


# ---------------------------------------------------------------------------
# B-04 placeholder preservation (issue #172 - must survive the unification)
# ---------------------------------------------------------------------------


class TestB04PlaceholderPreservation:
    """Placeholder-only sections must STAY empty after the unification.

    The refactor adopts the skeleton-aware ``_is_empty_placeholder``
    everywhere. That unification may only tighten (also reject LLM skeleton
    echoes); the ``_No ..._`` placeholder rejection that keeps B-04 (#172)
    failing must not loosen. These guards are green today and must stay green.
    """

    def test_exercises_placeholder_section_stays_empty_at_every_site(self) -> None:
        md = "## Exercises\n\n_No exercises provided._\n"
        for label, module in _SITES:
            found: dict[str, str] = module._sections_from_headings(md, "tutorial")
            assert found.get("recommendations") == "", (
                f"B-04 (#172): the placeholder-only Exercises section at "
                f"'{label}' must be kept empty so D1 keeps rejecting it"
            )

    def test_placeholder_string_is_rejected_at_every_site(self) -> None:
        for label, module in _SITES:
            rejected: bool = module._is_empty_placeholder("_No exercises provided._")
            assert rejected is True, (
                f"B-04 (#172): '_No exercises provided._' must be an empty placeholder at '{label}'"
            )

    def test_real_content_is_not_a_placeholder_at_any_site(self) -> None:
        for label, module in _SITES:
            rejected: bool = module._is_empty_placeholder(
                "- Hospitals adopt AI triage at growing scale"
            )
            assert rejected is False, (
                f"B-04 (#172): real content must not be classified as a placeholder at '{label}'"
            )


# ---------------------------------------------------------------------------
# magazine_digest fallback (issue #400, Oracle correction 1)
# ---------------------------------------------------------------------------


class TestMagazineDigestFallback:
    """``magazine_digest`` must get key_findings from the any-content fallback.

    ``magazine-digest.md.j2`` emits no summary-alias heading, so ``summary``
    is never found for the type; the fallback that rescues column/magazine
    products only knows ``("column", "magazine")``. The refactor adds
    ``"magazine_digest"`` to the fallback tuple, sets
    ``_PRODUCT_TYPE_REQUIRED_SECTIONS["magazine_digest"] = ("key_findings",)``
    and hardens the guard from ``and not found`` to
    ``and "key_findings" not in found`` so an already-found summary cannot
    suppress the required key_findings fallback.
    """

    MAGAZINE_BODY = (
        "# City Weekly\n\n"
        "## Neighbourhood Watch\n\n"
        "A new cafe downtown drew record crowds this weekend.\n"
    )

    def test_fallback_yields_key_findings_without_summary_heading(self) -> None:
        for label, module in _SITES:
            found: dict[str, str] = module._sections_from_headings(
                self.MAGAZINE_BODY, "magazine_digest"
            )
            assert found.get("key_findings", "").strip(), (
                f"issue #400: the magazine_digest any-content fallback must "
                f"surface a content heading as key_findings at '{label}'"
            )

    def test_fallback_fires_even_when_summary_was_already_found(self) -> None:
        """Hardened guard: an already-found summary must not suppress it."""
        md = (
            "# City Weekly\n\n"
            "## Executive Summary\n\nQuiet week across the sector.\n\n"
            "## Neighbourhood Watch\n\nA new cafe downtown drew record crowds.\n"
        )
        for label, module in _SITES:
            found: dict[str, str] = module._sections_from_headings(md, "magazine_digest")
            assert found.get("key_findings", "").strip(), (
                f"issue #400: the hardened fallback guard ('key_findings' not "
                f"in found) must still add key_findings when summary was "
                f"already found at '{label}'"
            )


# ---------------------------------------------------------------------------
# Skeleton-aware placeholder unification (issue #400, Oracle correction 4)
# ---------------------------------------------------------------------------


class TestSkeletonAwarePlaceholderUnification:
    """The skeleton-aware ``_is_empty_placeholder`` must be adopted everywhere.

    ``autoinfo.output`` also rejects LLM skeleton echoes (``_LLM_SKELETON_RE``
    matches ``<finding 1>``-style prompt-template placeholders); the
    gate_report and scripts/validation_delivery.py copies do NOT, so a
    product whose section is only the model echoing the prompt skeleton
    passes D1 there. The refactor adopts the output version - it can only
    tighten (reject), never let a placeholder pass.
    """

    def test_skeleton_echo_counts_as_placeholder_at_every_site(self) -> None:
        for label, module in _SITES:
            rejected: bool = module._is_empty_placeholder("<finding 1>")
            assert rejected is True, (
                f"issue #400: skeleton-aware _is_empty_placeholder must "
                f"reject the LLM skeleton echo '<finding 1>' at '{label}'"
            )

    def test_list_skeleton_echo_counts_as_placeholder_at_every_site(self) -> None:
        skeleton = "- <finding 1>\n- <finding 2>\n- <finding 3>"
        for label, module in _SITES:
            rejected: bool = module._is_empty_placeholder(skeleton)
            assert rejected is True, (
                f"issue #400: skeleton-aware _is_empty_placeholder must "
                f"reject a multi-item LLM skeleton list at '{label}'"
            )
