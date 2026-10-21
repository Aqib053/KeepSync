def _props(fields: dict) -> dict:
    """A field maps to a type name, or to a full schema dict (for nested fields)."""
    return {n: (t if isinstance(t, dict) else {"type": t}) for n, t in fields.items()}


def make_multi_spec(endpoints: dict) -> dict:
    """endpoints: {path: {field: type-or-schema}} -> a spec with one GET per path."""
    paths, schemas = {}, {}
    for i, (path, fields) in enumerate(endpoints.items()):
        name = f"Schema{i}"
        schemas[name] = {"properties": _props(fields)}
        schema = {"$ref": f"#/components/schemas/{name}"}
        response = {"200": {"content": {"application/json": {"schema": schema}}}}
        paths[path] = {"get": {"responses": response}}
    return {
        "openapi": "3.1.0",
        "info": {"title": "bench", "version": "1.0.0"},
        "paths": paths,
        "components": {"schemas": schemas},
    }


def make_spec(fields: dict) -> dict:
    """A minimal spec with one endpoint (/orders/{order_id}) that returns `fields`.
    A dict that is already a full spec (it has "paths") is returned unchanged."""
    if "paths" in fields:
        return fields
    return make_multi_spec({"/orders/{order_id}": fields})
