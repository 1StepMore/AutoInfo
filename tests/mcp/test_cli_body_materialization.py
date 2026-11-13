"""Windows seam: multi-line python scenario bodies become temp scripts (#729).

cmd.exe has no heredoc and its C runtime splits the child's argv on
newlines, so a scenario seeding step written as ``python - <<'PY'`` or
``python -c '<multiline body>'`` can never run as-is on Windows — and
``_cmd_quote_compat`` can only fold FLAT statement bodies, not indented
blocks (``for``/``class``).  :func:`_materialize_python_body` writes the
body verbatim to a temp ``.py`` and rewrites the command to run that file;
anything that is not exactly one such block passes through untouched.
POSIX never calls the function (the seam is ``os.name == "nt"``-gated in
``_run_cli_step``) — these tests exercise it directly for contract.
"""

from __future__ import annotations

import shlex

from autoinfo.mcp.validation import _materialize_python_body

HEREDOC_CMD = (
    "python3 - <<'PY'\nfrom autoinfo.kb import KBStore\nstore = KBStore()\nprint('ok')\nPY\n"
)
DASH_C_CMD = (
    "python3 -c '\n"
    "INTENTS = [\n"
    '    ("a", "b", set()),\n'
    "]\n"
    "for intent, expected, forbid in INTENTS:\n"
    "    assert intent\n"
    "print(len(INTENTS))\n"
    "'"
)


def test_heredoc_body_is_materialized_to_a_temp_script() -> None:
    rewritten, script = _materialize_python_body(HEREDOC_CMD)

    assert script is not None and script.exists()
    assert script.suffix == ".py"
    assert script.name.startswith("autoinfo-scenario-")
    # The interpreter token is preserved; the block is replaced by the path.
    assert rewritten.startswith("python3 ")
    assert str(script) in rewritten or shlex.quote(str(script)) in rewritten
    assert "KBStore" not in rewritten  # the body moved into the file
    assert script.read_text(encoding="utf-8").startswith("from autoinfo.kb")
    script.unlink()


def test_multiline_dash_c_body_is_materialized() -> None:
    rewritten, script = _materialize_python_body(DASH_C_CMD)

    assert script is not None and script.exists()
    assert rewritten.startswith("python3 ")
    assert "for intent" not in rewritten  # indented body lives in the file
    body = script.read_text(encoding="utf-8")
    assert "INTENTS = [" in body
    assert "for intent, expected, forbid in INTENTS:" in body
    script.unlink()


def test_single_line_dash_c_is_left_alone() -> None:
    cmd = "python3 -c 'print(1)'"
    rewritten, script = _materialize_python_body(cmd)
    assert rewritten == cmd
    assert script is None


def test_plain_commands_are_left_alone() -> None:
    for cmd in ("autoinfo status --json", "autoinfo doctor --json", "echo python3 -c 'x'"):
        rewritten, script = _materialize_python_body(cmd)
        assert rewritten == cmd
        assert script is None


def test_body_with_surrounding_text_is_left_alone() -> None:
    """A heredoc embedded in a larger command degrades honestly (untouched)."""
    cmd = "echo before && " + HEREDOC_CMD.strip() + " && echo after"
    rewritten, script = _materialize_python_body(cmd)
    assert rewritten == cmd
    assert script is None
