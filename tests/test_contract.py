from pathlib import Path

from keepsync.contract import diff_specs, load_spec

FIX = Path(__file__).parent / "fixtures"


def make_spec(fields):
    schema = {"$ref": "#/components/schemas/Order"}
    response = {"200": {"content": {"application/json": {"schema": schema}}}}
    return {
        "paths": {"/orders/{order_id}": {"get": {"responses": response}}},
        "components": {"schemas": {"Order": {
            "properties": {n: {"type": t} for n, t in fields.items()}}}},
    }


def test_detects_rename_on_demo_specs():
    changes = diff_specs(load_spec(FIX / "old.json"), load_spec(FIX / "new.json"))
    assert len(changes) == 1
    c = changes[0]
    assert (c.kind, c.field, c.new_field) == ("rename", "customer_name", "customer")
    assert c.path == "/orders/{order_id}"


def test_removed_without_replacement():
    old = make_spec({"id": "integer", "customer_name": "string"})
    new = make_spec({"id": "integer"})
    assert [c.kind for c in diff_specs(old, new)] == ["removed"]


def test_ambiguous_is_not_a_rename():
    old = make_spec({"first_name": "string", "last_name": "string"})
    new = make_spec({"given": "string", "family": "string"})
    kinds = sorted(c.kind for c in diff_specs(old, new))
    assert kinds == ["added", "added", "removed", "removed"]


def test_loads_yaml_spec_with_unquoted_status_codes(tmp_path):
    template = """openapi: 3.1.0
info: {title: t, version: '1'}
paths:
  /orders/{order_id}:
    get:
      responses:
        200:
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Order'
components:
  schemas:
    Order:
      properties:
        id: {type: integer}
        FIELD: {type: string}
"""
    old = tmp_path / "old.yaml"
    new = tmp_path / "new.yaml"
    old.write_text(template.replace("FIELD", "customer_name"))
    new.write_text(template.replace("FIELD", "customer"))
    changes = diff_specs(load_spec(old), load_spec(new))
    assert [(c.kind, c.field, c.new_field) for c in changes] == [
        ("rename", "customer_name", "customer")
    ]
