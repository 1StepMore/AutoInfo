"""Import-boundary + import-completeness guard for ``mcp/tools/*.py``.

Wave 0 of #581 moves handler bodies out of the 7.8k-line server hub into
per-domain tools modules. That only works if no tools module reaches back into
the hub: a module-scope ``autoinfo.mcp.server`` import re-creates the cycle the
extraction exists to break, and a handler that reads a helper without importing
it (or reaching it as ``mcp_context.<name>``) fails only at call time.

Three AST checks:

1. No module-scope import of ``autoinfo.mcp.server`` (any spelling).
2. Function-body server imports exist solely for the two dispatch escapes the
   plan allows: ``call_tool`` in ``misc.py`` and ``_TOOL_DISPATCH`` in
   ``system.py``.
3. Import completeness per ``_handle_*`` function: every free global resolves
   to a module-level name or a builtin, and every ``mcp_context.<attr>``
   actually exists on the context module.
"""

from __future__ import annotations

import ast
import builtins
import pathlib
import symtable

from autoinfo.mcp import context as mcp_context
from tests.mcp._source_corpus import MCP_DIR

TOOLS_DIR = MCP_DIR / "tools"
CONTEXT_PY = MCP_DIR / "context.py"
# The plan allows exactly two escape hatches from a tools module back into the
# hub, keyed by the imported symbol (not the enclosing function):
#   misc.py   -> call_tool      (validation scenarios re-enter the dispatcher)
#   system.py -> _TOOL_DISPATCH (health/tool-count read the live registry)
FUNCTION_BODY_IMPORT_ALLOWLIST = {
    ("misc.py", "call_tool"),
    ("system.py", "_TOOL_DISPATCH"),
}

# Always bound by the import system in any module, so never an unresolved read.
MODULE_DUNDERS = frozenset(
    {"__file__", "__name__", "__doc__", "__package__", "__loader__", "__spec__", "__builtins__"}
)


def _tool_paths() -> list[pathlib.Path]:
    return sorted(TOOLS_DIR.glob("*.py"))


def _imports_server(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(
            alias.name == "autoinfo.mcp.server" or alias.name.startswith("autoinfo.mcp.server.")
            for alias in node.names
        )
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module == "autoinfo.mcp.server" or module.startswith("autoinfo.mcp.server."):
            return True
        if module == "autoinfo.mcp" and any(alias.name == "server" for alias in node.names):
            return True
        if node.level == 2:
            if module == "server":
                return True
            if module == "" and any(alias.name == "server" for alias in node.names):
                return True
    return False


class _ServerImportVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.function_stack: list[str] = []
        self.module_scope: list[int] = []
        self.function_body: list[tuple[int, str, list[str]]] = []

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def visit_Import(self, node: ast.Import) -> None:
        self._record(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._record(node)

    def _record(self, node: ast.AST) -> None:
        if not _imports_server(node):
            return
        if not self.function_stack:
            self.module_scope.append(node.lineno)
            return
        names = [alias.name for alias in node.names]
        self.function_body.append((node.lineno, self.function_stack[-1], names))


def _module_level_names(table: symtable.SymbolTable) -> set[str]:
    return {symbol.get_name() for symbol in table.get_symbols()}


def _handler_tables(table: symtable.SymbolTable) -> list[symtable.SymbolTable]:
    found: list[symtable.SymbolTable] = []
    for child in table.get_children():
        if child.get_type() == "function" and child.get_name().startswith("_handle_"):
            found.append(child)
        found.extend(_handler_tables(child))
    return found


def _context_attributes(node: ast.AST) -> set[str]:
    attrs: set[str] = set()
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id == "mcp_context"
        ):
            attrs.add(child.attr)
    return attrs


def test_no_module_scope_server_imports() -> None:
    violations: list[tuple[str, int]] = []
    for path in _tool_paths():
        visitor = _ServerImportVisitor()
        visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
        violations.extend((path.name, line) for line in visitor.module_scope)
    assert violations == [], (
        "module-scope autoinfo.mcp.server imports in tools modules re-create the "
        f"dependency cycle the extraction removes: {violations}"
    )


def test_function_body_server_imports_are_limited_to_dispatch() -> None:
    violations: list[tuple[str, int, str, str]] = []
    for path in _tool_paths():
        visitor = _ServerImportVisitor()
        visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
        for line, function, names in visitor.function_body:
            for name in names:
                if path.name == "autoinfo.mcp" and name == "server":
                    violations.append((path.name, line, function, name))
                elif (path.name, name) not in FUNCTION_BODY_IMPORT_ALLOWLIST:
                    violations.append((path.name, line, function, name))
    assert violations == [], (
        "function-body autoinfo.mcp.server imports are allowed only for "
        f"{sorted(FUNCTION_BODY_IMPORT_ALLOWLIST)}: {violations}"
    )


def test_handler_free_globals_are_importable() -> None:
    unresolved: list[tuple[str, str, str]] = []
    builtin_names = set(dir(builtins))
    for path in _tool_paths():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        module_table = symtable.symtable(source, path.name, "exec")
        module_names = _module_level_names(module_table)

        for table in _handler_tables(module_table):
            for name in table.get_globals():
                if name in module_names or name in builtin_names or name in MODULE_DUNDERS:
                    continue
                hint = f" (use mcp_context.{name})" if hasattr(mcp_context, name) else ""
                unresolved.append((path.name, table.get_name(), f"{name}{hint}"))

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("_handle_"):
                continue
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Attribute)
                    and isinstance(child.value, ast.Name)
                    and child.value.id == "mcp_context"
                    and not hasattr(mcp_context, child.attr)
                ):
                    unresolved.append(
                        (path.name, node.name, f"mcp_context.{child.attr} does not exist")
                    )

    assert unresolved == [], (
        "handlers read names that are neither module-level nor builtin; add the "
        f"import or reach the helper through mcp_context: {unresolved}"
    )


def test_context_module_does_not_import_server_or_tools() -> None:
    def targets_server_or_tools(module: str, names: list[str]) -> bool:
        if module == "autoinfo.mcp.server" or module.startswith("autoinfo.mcp.server."):
            return True
        if module == "autoinfo.mcp.tools" or module.startswith("autoinfo.mcp.tools."):
            return True
        if module == "autoinfo.mcp":
            return any(name in ("server", "tools") for name in names)
        return False

    violations: list[tuple[str, int, str]] = []
    tree = ast.parse(CONTEXT_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if targets_server_or_tools(alias.name, []):
                    violations.append(("import", node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            names = [alias.name for alias in node.names]
            if targets_server_or_tools(node.module or "", names):
                violations.append(("from", node.lineno, f"{node.module}:{names}"))
    assert violations == [], f"context.py must stay below the hub and tools: {violations}"
