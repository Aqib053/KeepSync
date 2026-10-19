def make_spec(fields: dict) -> dict:
    """A minimal OpenAPI spec with one endpoint that returns `fields`."""
    schema = {"$ref": "#/components/schemas/Order"}
    response = {"200": {"content": {"application/json": {"schema": schema}}}}
    return {
        "openapi": "3.1.0",
        "info": {"title": "bench", "version": "1.0.0"},
        "paths": {"/orders/{order_id}": {"get": {"responses": response}}},
        "components": {"schemas": {"Order": {
            "properties": {n: {"type": t} for n, t in fields.items()}}}},
    }
