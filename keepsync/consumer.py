import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Usage:
    line: int  # 1-based line number
    col: int  # where the string literal starts
    end_col: int  # where it ends


def _is_key(node, field: str) -> bool:
    return isinstance(node, ast.Constant) and node.value == field


def _is_json_call(node) -> bool:
    """True for `something.json()` and `await something.json()`."""
    if isinstance(node, ast.Await):
        node = node.value
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "json"
    )


def _walk_scope(scope):
    """Walk a scope's nodes without going into nested functions or classes."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        nested = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
        if not isinstance(node, nested):
            stack.extend(ast.iter_child_nodes(node))


def _response_names(scope) -> set:
    """Names assigned from `<x>.json()` directly inside this scope."""
    names = set()
    for node in _walk_scope(scope):
        if isinstance(node, ast.Assign) and _is_json_call(node.value):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


class _Finder(ast.NodeVisitor):
    def __init__(self, field: str, module_names: set):
        self.field = field
        self.scopes = [module_names]
        self.usages = []

    def _is_response(self, node) -> bool:
        if _is_json_call(node):
            return True
        return isinstance(node, ast.Name) and node.id in self.scopes[-1]

    def _add(self, target):
        self.usages.append(Usage(target.lineno, target.col_offset, target.end_col_offset))

    def _enter_function(self, node):
        self.scopes.append(_response_names(node))
        self.generic_visit(node)
        self.scopes.pop()

    visit_FunctionDef = _enter_function
    visit_AsyncFunctionDef = _enter_function

    def visit_Subscript(self, node):
        if _is_key(node.slice, self.field) and self._is_response(node.value):
            self._add(node.slice)
        self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and node.args
            and _is_key(node.args[0], self.field)
            and self._is_response(func.value)
        ):
            self._add(node.args[0])
        self.generic_visit(node)


def find_field_usages(source: str, field: str) -> list:
    """Find reads of `field` on an API response: r.json()["field"],
    r.json().get("field"), or the same on a name assigned from `.json()`."""
    tree = ast.parse(source)
    finder = _Finder(field, _response_names(tree))
    finder.visit(tree)
    return sorted(finder.usages, key=lambda u: (u.line, u.col))


def rewrite_field(source: str, usages: list, old: str, new: str) -> str:
    """Replace `old` with `new` inside each usage. Positions are byte offsets, fine for ASCII."""
    lines = source.splitlines(keepends=True)
    for u in sorted(usages, key=lambda u: (u.line, u.col), reverse=True):
        line = lines[u.line - 1]
        piece = line[u.col:u.end_col].replace(old, new)
        lines[u.line - 1] = line[:u.col] + piece + line[u.end_col:]
    return "".join(lines)
