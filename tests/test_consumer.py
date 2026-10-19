from keepsync.consumer import find_field_usages, rewrite_field

SRC = '''import httpx


def get_customer_name(order_id, client):
    r = client.get(f"/orders/{order_id}")
    return r.json()["customer_name"]


def other(r):
    return r.json().get("customer_name")


def not_a_key():
    return "customer_name is just text"
'''


def test_finds_subscript_and_get():
    assert len(find_field_usages(SRC, "customer_name")) == 2


def test_rewrite_changes_only_the_keys():
    usages = find_field_usages(SRC, "customer_name")
    out = rewrite_field(SRC, usages, "customer_name", "customer")
    assert 'r.json()["customer"]' in out
    assert 'r.json().get("customer")' in out
    assert "def get_customer_name" in out  # function name untouched
    assert '"customer_name is just text"' in out  # plain text untouched


def test_ignores_dicts_that_are_not_api_responses():
    src = (
        "def a(r):\n"
        '    return r.json()["customer_name"]\n'
        "\n"
        "def b(user, settings):\n"
        '    return user["customer_name"], settings.get("customer_name")\n'
    )
    assert [u.line for u in find_field_usages(src, "customer_name")] == [2]


def test_follows_a_name_assigned_from_json():
    src = (
        "def get(r):\n"
        "    data = r.json()\n"
        '    return data["customer_name"]\n'
    )
    assert [u.line for u in find_field_usages(src, "customer_name")] == [3]


def test_name_tracking_is_per_function():
    src = (
        "def a(r):\n"
        "    data = r.json()\n"
        '    return data["customer_name"]\n'
        "\n"
        "def b(data):\n"
        '    return data["customer_name"]\n'
    )
    assert [u.line for u in find_field_usages(src, "customer_name")] == [3]


def test_follows_awaited_json():
    src = (
        "async def get(r):\n"
        "    data = await r.json()\n"
        '    return data["customer_name"]\n'
    )
    assert [u.line for u in find_field_usages(src, "customer_name")] == [3]
