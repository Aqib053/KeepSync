import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Change:
    kind: str  # "rename", "removed", "added", "type_changed"
    method: str
    path: str
    field: str
    new_field: str | None = None
    old_type: str | None = None
    new_type: str | None = None


def load_spec(path) -> dict:
    with open(path) as f:
        text = f.read()
    if str(path).lower().endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError as exc:
            raise SystemExit(
                "YAML specs need PyYAML. Run: python -m pip install pyyaml"
            ) from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict) or "paths" not in data:
        raise SystemExit(f"{path} does not look like an OpenAPI spec (no 'paths').")
    return data


def _resolve(spec: dict, schema: dict) -> dict:
    ref = schema.get("$ref")
    if not ref:
        return schema
    return spec["components"]["schemas"][ref.split("/")[-1]]


def response_fields(spec: dict) -> dict:
    """Return {(METHOD, path): {field_name: type}} for 200 responses."""
    out = {}
    for path, methods in spec.get("paths", {}).items():
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            responses = op.get("responses", {})
            ok = responses.get("200") or responses.get(200) or {}
            content = ok.get("content", {})
            schema = content.get("application/json", {}).get("schema")
            if not schema:
                continue
            props = _resolve(spec, schema).get("properties", {})
            out[(method.upper(), path)] = {n: p.get("type") for n, p in props.items()}
    return out


def diff_specs(old: dict, new: dict) -> list:
    old_f, new_f = response_fields(old), response_fields(new)
    changes = []
    for key, old_fields in old_f.items():
        if key not in new_f:
            continue  # whole endpoint removed: handled later
        method, path = key
        new_fields = new_f[key]
        removed = {n: t for n, t in old_fields.items() if n not in new_fields}
        added = {n: t for n, t in new_fields.items() if n not in old_fields}

        for n, t in old_fields.items():
            if n in new_fields and new_fields[n] != t:
                changes.append(Change("type_changed", method, path, n,
                                      old_type=t, new_type=new_fields[n]))

        # A rename = one field gone and one new field with the same type,
        # and no other candidate. Anything unclear stays "removed" + "added".
        for r_name, r_type in list(removed.items()):
            candidates = [a for a, t in added.items() if t == r_type]
            same_type_gone = [n for n, t in removed.items() if t == r_type]
            if len(candidates) == 1 and len(same_type_gone) == 1:
                changes.append(Change("rename", method, path, r_name,
                                      new_field=candidates[0],
                                      old_type=r_type, new_type=r_type))
                del removed[r_name]
                del added[candidates[0]]

        for n, t in removed.items():
            changes.append(Change("removed", method, path, n, old_type=t))
        for n, t in added.items():
            changes.append(Change("added", method, path, n, new_type=t))
    return changes
