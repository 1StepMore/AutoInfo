"""Regression test for Bug #40.

Bug: The ``raw_ids`` and ``tags`` parameters of ``create_draft()`` in
``src/autoinfo/cli/kb.py`` were missing ``: list[str]`` type annotations.
Without them, Typer only reads the first character of the first ``--raw-id``
value instead of parsing multiple ``--raw-id`` options into a list.

Fix: Added ``: list[str]`` type annotations to both parameters.

Note: CliRunner-based tests cannot be used here due to a Python 3.14
compatibility issue with Typer's ``inspect.signature(func, eval_str=True)``
(``annotationlib._rewrite_star_unpack`` eval failure). This is a pre-existing
issue affecting all CLI tests (including Bug #39 regression tests).
Instead, we verify the annotations at the AST and type-hints level.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


def test_create_draft_has_list_annotation_on_raw_ids() -> None:
    """raw_ids parameter must have ``: list[str]`` annotation."""
    from autoinfo.cli.kb import create_draft

    ann = create_draft.__annotations__.get("raw_ids")
    assert ann is not None, "raw_ids has no type annotation"
    # With ``from __future__ import annotations``, __annotations__ are strings
    assert "list" in str(ann).lower(), (
        f"Expected raw_ids annotation to mention list, got {ann!r}"
    )


def test_create_draft_has_list_annotation_on_tags() -> None:
    """tags parameter must have ``: list[str]`` annotation."""
    from autoinfo.cli.kb import create_draft

    ann = create_draft.__annotations__.get("tags")
    assert ann is not None, "tags has no type annotation"
    assert "list" in str(ann).lower(), (
        f"Expected tags annotation to mention list, got {ann!r}"
    )


def test_raw_ids_annotation_is_list_of_str() -> None:
    """raw_ids should be ``list[str]`` specifically."""
    from autoinfo.cli.kb import create_draft

    ann = create_draft.__annotations__.get("raw_ids")
    assert ann is not None, "raw_ids has no type annotation"
    assert "list[str]" in str(ann), (
        f"Expected raw_ids annotation to be list[str], got {ann!r}"
    )


def test_tags_annotation_is_list_of_str() -> None:
    """tags should be ``list[str]`` specifically."""
    from autoinfo.cli.kb import create_draft

    ann = create_draft.__annotations__.get("tags")
    assert ann is not None, "tags has no type annotation"
    assert "list[str]" in str(ann), (
        f"Expected tags annotation to be list[str], got {ann!r}"
    )


def test_create_draft_source_has_subscript_annotations() -> None:
    """Verify ``list[str]`` appears literally in the AST for both params."""
    # TRIAGE #55 (stale): cwd-relative path broke when an earlier test leaked
    # `os.chdir` (e.g. test_backward_compat chdir without restore). Resolve
    # against this test file so it works from any cwd.
    kb_path = Path(__file__).resolve().parent.parent / "src" / "autoinfo" / "cli" / "kb.py"
    with open(kb_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "create_draft":
            arg_names = {a.arg: a for a in node.args.args}
            _assert_is_list_subscript(arg_names["raw_ids"].annotation, "raw_ids")
            _assert_is_list_subscript(arg_names["tags"].annotation, "tags")
            return
    pytest.fail("create_draft function not found in AST")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_is_list_subscript(
    ann: ast.AST | None, param_name: str
) -> None:
    """Assert that an AST annotation node represents a ``list[...]``."""
    assert ann is not None, f"{param_name} has no annotation in AST"
    if isinstance(ann, ast.Subscript):
        assert isinstance(ann.value, ast.Name), (
            f"Expected {param_name} annotation base to be a Name, "
            f"got {type(ann.value).__name__}"
        )
        assert ann.value.id == "list", (
            f"Expected {param_name} annotation to be list[...], "
            f"got {ann.value.id}[...]"
        )
    elif isinstance(ann, ast.Name):
        assert ann.id == "list", (
            f"Expected {param_name} annotation to be list, got {ann.id}"
        )
    else:
        pytest.fail(
            f"Unexpected AST annotation type for {param_name}: "
            f"{type(ann).__name__}"
        )
