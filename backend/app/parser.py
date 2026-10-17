"""
Safe Python AST parser for extracting imports, function calls, and arguments.

Uses Python's built-in ``ast`` module to analyze source code WITHOUT
executing it.  Never uses eval(), exec(), subprocess, or dynamic imports.

Key capabilities:
  - Import extraction (import / from-import / aliases).
  - Function and method call extraction.
  - Keyword argument, positional-arg-count, *args, **kwargs detection.
  - Line and column tracking.
  - Alias resolution so ``req.get`` → ``requests.get`` when possible.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data classes returned by the parser
# ---------------------------------------------------------------------------

@dataclass
class ImportInfo:
    """A single import statement."""
    module: str                     # e.g. "requests"
    name: str | None = None         # e.g. "get" (from-imports only)
    alias: str | None = None        # e.g. "req" (if aliased)
    line: int = 0
    is_from_import: bool = False


@dataclass
class CallInfo:
    """A single function / method call."""
    function: str                   # Raw name as written, e.g. "req.get"
    resolved_function: str | None = None  # Alias-resolved, e.g. "requests.get"
    line: int = 0
    column: int = 0
    keyword_arguments: list[str] = field(default_factory=list)
    positional_arg_count: int = 0
    has_starargs: bool = False      # *args present
    has_kwargs: bool = False        # **kwargs present
    module: str | None = None       # Resolved module, e.g. "requests"


@dataclass
class AttributeInfo:
    """A dotted attribute reference that is *not* a call, e.g. ``requests.exceptions.Timeout``."""
    name: str                       # as written
    resolved: str | None = None     # alias-resolved
    line: int = 0
    column: int = 0


@dataclass
class ParseResult:
    """Complete result of parsing Python source code."""
    imports: list[ImportInfo] = field(default_factory=list)
    calls: list[CallInfo] = field(default_factory=list)
    attributes: list[AttributeInfo] = field(default_factory=list)
    error: dict | None = None       # Non-None when syntax error occurred


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_dotted_name(node: ast.expr) -> str | None:
    """Convert an AST expression to a dotted name string.

    Returns None for complex expressions (e.g. ``f().method``) that
    cannot be represented as a simple dotted name.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _get_dotted_name(node.value)
        if parent is not None:
            return f"{parent}.{node.attr}"
    return None


def _build_alias_map(imports: list[ImportInfo]) -> dict[str, str]:
    """Build a mapping from local names to canonical module paths.

    Examples::

        import requests as req       → {"req": "requests"}
        from requests import get     → {"get": "requests.get"}
        from requests import get as fetch → {"fetch": "requests.get"}
        import requests              → {"requests": "requests"}
    """
    alias_map: dict[str, str] = {}
    for imp in imports:
        if imp.is_from_import and imp.name:
            local_name = imp.alias if imp.alias else imp.name
            canonical = f"{imp.module}.{imp.name}" if imp.module else imp.name
            alias_map[local_name] = canonical
        else:
            local_name = imp.alias if imp.alias else imp.module
            alias_map[local_name] = imp.module
    return alias_map


def _resolve_call(function_name: str, alias_map: dict[str, str]) -> str | None:
    """Resolve a call name through the alias map.

    Returns the canonical name, or None if resolution is not possible.
    """
    # Direct match  (bare name like "fetch" → "requests.get")
    if function_name in alias_map:
        return alias_map[function_name]

    # Prefix match  ("req.get" → "requests.get")
    if "." in function_name:
        prefix, rest = function_name.split(".", 1)
        if prefix in alias_map:
            return f"{alias_map[prefix]}.{rest}"

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_python_code(code: str) -> ParseResult:
    """Parse Python source and extract imports, calls, and arguments.

    Args:
        code: Python source code string.

    Returns:
        ParseResult with extracted data.  If the code has a syntax error,
        ``result.error`` is set and ``imports``/``calls`` are empty.
    """
    result = ParseResult()

    # --- Parse into AST (safe — no execution) ---
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        result.error = {
            "message": exc.msg if exc.msg else "Syntax error",
            "line": exc.lineno,
            "column": exc.offset,
        }
        return result

    # --- Extract imports ---
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.imports.append(ImportInfo(
                    module=alias.name,
                    alias=alias.asname,
                    line=node.lineno,
                    is_from_import=False,
                ))
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            for alias in node.names:
                result.imports.append(ImportInfo(
                    module=module_name,
                    name=alias.name,
                    alias=alias.asname,
                    line=node.lineno,
                    is_from_import=True,
                ))

    # Build alias map for call resolution
    alias_map = _build_alias_map(result.imports)

    # --- Extract function / method calls ---
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        function_name = _get_dotted_name(node.func)
        if function_name is None:
            continue  # Cannot represent; skip

        # Keyword arguments
        keyword_args: list[str] = []
        has_kwargs = False
        for kw in node.keywords:
            if kw.arg is None:
                has_kwargs = True   # **kwargs expansion
            else:
                keyword_args.append(kw.arg)

        # Starred positional arguments
        has_starargs = any(isinstance(a, ast.Starred) for a in node.args)

        # Positional argument count (excludes *-starred)
        positional_count = sum(
            1 for a in node.args if not isinstance(a, ast.Starred)
        )

        # Alias resolution
        resolved = _resolve_call(function_name, alias_map)

        # Determine associated module
        call_module: str | None = None
        source = resolved or function_name
        if "." in source:
            call_module = source.rsplit(".", 1)[0]

        result.calls.append(CallInfo(
            function=function_name,
            resolved_function=resolved,
            line=node.lineno,
            column=node.col_offset,
            keyword_arguments=keyword_args,
            positional_arg_count=positional_count,
            has_starargs=has_starargs,
            has_kwargs=has_kwargs,
            module=call_module,
        ))

    # --- Extract non-call dotted attribute references (outermost chain only) ---
    inner_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            inner_ids.add(id(node.func))
        elif isinstance(node, ast.Attribute):
            inner_ids.add(id(node.value))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or id(node) in inner_ids:
            continue
        if not isinstance(node.ctx, ast.Load):
            continue
        name = _get_dotted_name(node)
        if name is None:
            continue
        result.attributes.append(AttributeInfo(
            name=name,
            resolved=_resolve_call(name, alias_map),
            line=node.lineno,
            column=node.col_offset,
        ))

    return result
