"""Import-boundary guard for the ``autoinfo.output`` package.

After the Wave-4 extraction the hub (``output/__init__.py``) is no longer the
only place a leaf can import from. Two rules keep it honest:

1. **No leaf-owned name crosses the hub.** If a leaf defines a symbol, another
   leaf must import it from that leaf — unless a test patches the symbol
   through ``autoinfo.output``, in which case the hub alias is the seam and a
   sibling import would bind a copy and silently stop intercepting.
2. **The hub-imported set is frozen.** A new hub read must be justified (the
   name is hub-defined, a package re-export, a module, or a live patch seam),
   so "someone added an import and no one noticed" fails the suite.

The frozen set is *measured*, not projected: the plan's 43-name estimate
predated the test-patch audit. Eleven names it omitted
(``_call_llm_for_tutorial``, ``_call_llm_for_presentation``, ``_group_by_theme``
siblings, ``_llm_key_available``…) are live ``autoinfo.output.<name>`` patch
targets, so they must keep arriving through the hub.

Also asserts every logging leaf binds ``logging.getLogger("autoinfo.output")``
— the documented single log target — never ``__name__``.
"""

from __future__ import annotations

import ast
import pathlib
import re

OUT = pathlib.Path(__file__).resolve().parents[2] / "src" / "autoinfo" / "output"
HUB = OUT / "__init__.py"
TESTS = pathlib.Path(__file__).resolve().parents[1]

# Measured over src/autoinfo/output/*.py: names imported from autoinfo.output.
FROZEN_HUB_IMPORTS = frozenset(
    """Config KBStore URL_VERBATIM_CONSTRAINT
    _GENERIC_THEME_LABELS _GROUPING_BATCH_SIZE _GROUPING_DEGRADATION_MARKER
    _GROUPING_MAX_WORKERS _GROUPING_TARGET_MIN_SIMILARITY _GROUPING_TARGET_RANGE
    _NO_DATA_REPORT_MARKER _SOURCE_TYPE_THEME_LABELS _STRUCTURAL_THEME_LABELS
    _TEMPLATES_DIR _THEME_SYNONYMS _build_bundle_pdf _build_tutorial_markdown_prompt
    _call_llm_for_presentation _call_llm_for_tutorial
    _filter_entries_by_content_preference _filter_product_entries _filter_stale_entries
    _fire_agent_notification _get_domain_exclude_keywords _get_domain_source_configs
    _keyword_topic_labels _llm_group_batch _llm_json_extract _llm_key_available
    _load_keyword_topics _parse_json_response _render_audio _render_presentation_html
    _resolve_content_preference _run_grouping_batches _sanitize_presentation_sources
    _seed_domain_default_language _select_story_set call_with_fallback datetime
    fault_inject generate_digest generate_report get_config_path get_prompt load_config
    localize_content timezone""".split()
)


def _leaves() -> list[pathlib.Path]:
    return [p for p in sorted(OUT.glob("*.py")) if p != HUB]


def _defined_names(path: pathlib.Path) -> set[str]:
    """Names the file defines OR re-exports (imports are part of its surface)."""
    names: set[str] = set()
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _hub_imports() -> dict[str, list[str]]:
    imports: dict[str, list[str]] = {}
    for path in _leaves():
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module == "autoinfo.output":
                for alias in node.names:
                    imports.setdefault(alias.name, []).append(f"{path.name}:{node.lineno}")
    return imports


def _patched_through_hub() -> set[str]:
    pattern = re.compile(r"""autoinfo\.output\.([A-Za-z_][A-Za-z0-9_]*)["']""")
    names: set[str] = set()
    for path in TESTS.rglob("*.py"):
        names.update(pattern.findall(path.read_text(encoding="utf-8")))
    return names


def test_hub_imported_set_is_frozen() -> None:
    imports = _hub_imports()
    extra = sorted(set(imports) - FROZEN_HUB_IMPORTS)
    missing = sorted(FROZEN_HUB_IMPORTS - set(imports))
    assert extra == [] and missing == [], (
        "the autoinfo.output import surface changed. Added: "
        f"{[(n, imports[n]) for n in extra]}; removed: {missing}. "
        "A new hub read needs a justification (hub-defined / package re-export / "
        "module / live patch seam); a removed one means a leaf stopped reading a seam."
    )


def test_every_hub_import_has_a_reason() -> None:
    hub_defined = _defined_names(HUB)
    patched = _patched_through_hub()
    leaf_owned = {name for path in _leaves() for name in _defined_names(path)}
    unjustified = []
    for name in sorted(FROZEN_HUB_IMPORTS):
        if name in hub_defined or name in patched or name == "fault_inject":
            continue
        if name in leaf_owned:
            unjustified.append(name)
    assert unjustified == [], (
        "leaf-owned names imported through the hub without being a patch seam: "
        f"{unjustified}. Import them from their owning module instead."
    )


def test_no_leaf_name_crosses_the_hub_without_a_seam() -> None:
    hub_defined = _defined_names(HUB)
    patched = _patched_through_hub()
    violations: list[tuple[str, str]] = []
    for name, sites in _hub_imports().items():
        if name in hub_defined or name in patched or name == "fault_inject":
            continue
        violations.append((name, ",".join(sites)))
    assert violations == [], (
        "a leaf imports a leaf-owned name from the hub, so patching the owner "
        f"cannot intercept: {violations}"
    )


def test_report_hub_accessor_reads_real_seams() -> None:
    defined = _defined_names(HUB)
    patched = _patched_through_hub()
    report = (OUT / "report.py").read_text(encoding="utf-8")
    read = set(re.findall(r'_hub\("([A-Za-z_][A-Za-z0-9_]*)"\)', report))
    assert read, "report.py no longer reads hub seams through _hub()"
    unknown = sorted(read - defined - patched)
    assert unknown == [], (
        f"report.py reads hub names that no longer exist or are not seams: {unknown}"
    )


def test_leaf_loggers_bind_the_shared_output_logger() -> None:
    wrong: list[tuple[str, str]] = []
    for path in _leaves():
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name) or target.id != "logger":
                continue
            value = node.value
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and value.func.attr == "getLogger"
                and value.args
                and isinstance(value.args[0], ast.Name)
                and value.args[0].id == "__name__"
            ):
                wrong.append((path.name, ast.unparse(value)))
    assert wrong == [], (
        'output leaves must bind logging.getLogger("autoinfo.output"), the '
        f"documented single log target, not __name__: {wrong}"
    )
