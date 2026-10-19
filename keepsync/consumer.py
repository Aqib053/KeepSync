import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Usage:
    line: int  # 1-based line number
    col: int  # where the string literal starts
    end_col: int  # where it ends


def _is_key(node, field: str) -> bool:
    return isinstance(node, ast.Constant) and node.value == field


def find_field_usages(source: str, field: str) -> list:
    """Find places where `field` is used as a dict key: x["field"] or x.get("field")."""
    usages = []
    for node in ast.walk(ast.parse(source)):
        target = None
        if isinstance(node, ast.Subscript) and _is_key(node.slice, field):
            target = node.slice
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and _is_key(node.args[0], field)
        ):
            target = node.args[0]
        if target is not None:
            usages.append(Usage(target.lineno, target.col_offset, target.end_col_offset))
    return sorted(usages, key=lambda u: (u.line, u.col))


def rewrite_field(source: str, usages: list, old: str, new: str) -> str:
    """Replace `old` with `new` inside each usage. Positions are byte offsets, fine for ASCII."""
    lines = source.splitlines(keepends=True)
    for u in sorted(usages, key=lambda u: (u.line, u.col), reverse=True):
        line = lines[u.line - 1]
        piece = line[u.col:u.end_col].replace(old, new)
        lines[u.line - 1] = line[:u.col] + piece + line[u.end_col:]
    return "".join(lines)
