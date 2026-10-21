import ast
import re
from dataclasses import dataclass

HTTP_VERBS = {"get", "post", "put", "patch", "delete"}


@dataclass(frozen=True)
class Usage:
    line: int  # 1-based line number
    col: int  # where the string literal starts
    end_col: int  # where it ends


def _is_key(node, field: str) -> bool:
    return isinstance(node, ast.Constant) and node.value == field


def _is_json_call(node) -> bool:
    """`x.json()`, `await x.json()`, or `json.loads(x.text)` / `json.loads(x.content)`."""
    if isinstance(node, ast.Await):
        node = node.value
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return False
    if node.func.attr == "json":
        return True
    return (
        node.func.attr == "loads"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "json"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Attribute)
        and node.args[0].attr in ("text", "content")
    )


def _url_of(node):
    """The URL text of a string or f-string, with each {placeholder} replaced by 0."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            str(v.value) if isinstance(v, ast.Constant) else "0" for v in node.values
        )
    return None


def _request_url(node):
    """URL of the request behind `x.get(url).json()` when it is visible, else None."""
    if isinstance(node, ast.Await):
        node = node.value
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "json"
    ):
        return None
    inner = node.func.value
    if isinstance(inner, ast.Await):
        inner = inner.value
    if (
        isinstance(inner, ast.Call)
        and isinstance(inner.func, ast.Attribute)
        and inner.func.attr in HTTP_VERBS
        and inner.args
    ):
        return _url_of(inner.args[0])
    return None


def _path_regex(path: str):
    """'/orders/{order_id}' -> a regex matching URLs that end with that path."""
    parts = []
    for seg in path.strip("/").split("/"):
        if seg.startswith("{") and seg.endswith("}"):
            parts.append("[^/]+")
        else:
            parts.append(re.escape(seg))
    return re.compile("/" + "/".join(parts) + r"/?(?:\?.*)?$")


def _walk_scope(scope):
    """Walk a scope's nodes without going into nested functions or classes."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        nested = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
        if not isinstance(node, nested):
            stack.extend(ast.iter_child_nodes(node))


def _response_names(scope) -> dict:
    """{name: request URL or None} for names assigned from a response (or from such a name)."""
    assigns = [n for n in _walk_scope(scope) if isinstance(n, ast.Assign)]
    names = {}
    changed = True
    while changed:
        changed = False
        for node in assigns:
            value = node.value
            if _is_json_call(value):
                url = _request_url(value)
            elif isinstance(value, ast.Name) and value.id in names:
                url = names[value.id]
            else:
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id not in names:
                    names[target.id] = url
                    changed = True
                elif names[target.id] is not None and names[target.id] != url:
                    names[target.id] = None  # assigned from different requests: unknown
                    changed = True
    return names


class _Finder(ast.NodeVisitor):
    def __init__(self, field: str, module_names: dict, patterns: list):
        self.field = field
        self.scopes = [module_names]
        self.patterns = patterns
        self.usages = []

    def _url_ok(self, url) -> bool:
        return url is None or not self.patterns or any(p.search(url) for p in self.patterns)

    def _is_response(self, node) -> bool:
        if _is_json_call(node):
            return self._url_ok(_request_url(node))
        if isinstance(node, ast.Name) and node.id in self.scopes[-1]:
            return self._url_ok(self.scopes[-1][node.id])
        return False

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


def find_field_usages(source: str, field: str, paths=None) -> list:
    """Find reads of `field` on an API response: r.json()["field"], r.json().get("field"),
    json.loads(r.text)["field"], or the same on a name assigned from a response.
    If `paths` is given, a read whose request URL is visible and matches none of them is skipped."""
    tree = ast.parse(source)
    patterns = [_path_regex(p) for p in (paths or [])]
    finder = _Finder(field, _response_names(tree), patterns)
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
