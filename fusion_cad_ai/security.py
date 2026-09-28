"""AST sandbox for execute(). The same allowlist lives in fca_rt/sandbox.py."""

from __future__ import annotations

import ast

from fusion_cad_ai.errors import FcaError

ALLOWED_IMPORT_ROOTS = frozenset(
    {
        "adsk",
        "math",
        "json",
        "re",
        "dataclasses",
        "typing",
        "itertools",
        "functools",
        "collections",
        "fca_rt",
    }
)
BLOCKED_CALLS = frozenset(
    {
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "breakpoint",
        "input",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
    }
)
BLOCKED_NAMES = frozenset({"os", "sys", "pathlib", "subprocess", "socket", "shutil", "ctypes"})


def check_ast(code: str) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise FcaError("FUSION_API_ERROR", f"Синтаксическая ошибка: {exc}") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_module(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                _check_module(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_CALLS:
                raise FcaError(
                    "SANDBOX_VIOLATION",
                    f"Вызов {node.func.id}() запрещён в execute()",
                    hint="Разрешены adsk и чистая математика. Файлы пишет только export().",
                )
        elif isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            raise FcaError("SANDBOX_VIOLATION", f"Имя {node.id} запрещено в execute()")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr not in {
            "__name__",
            "__doc__",
        }:
            raise FcaError("SANDBOX_VIOLATION", f"Атрибут {node.attr} запрещён")


def _check_module(dotted: str) -> None:
    root = dotted.split(".", 1)[0]
    if root not in ALLOWED_IMPORT_ROOTS:
        raise FcaError(
            "SANDBOX_VIOLATION",
            f"Импорт {dotted!r} запрещён",
            hint="Разрешены: " + ", ".join(sorted(ALLOWED_IMPORT_ROOTS)),
        )
