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


def test_follows_json_loads_on_text():
    src = (
        "import json\n\n"
        "def get(r):\n"
        '    return json.loads(r.text)["customer_name"]\n'
    )
    assert [u.line for u in find_field_usages(src, "customer_name")] == [4]


def test_follows_alias_of_response_name():
    src = (
        "def get(r):\n"
        "    data = r.json()\n"
        "    payload = data\n"
        '    return payload["customer_name"]\n'
    )
    assert [u.line for u in find_field_usages(src, "customer_name")] == [4]


def test_ignores_json_loads_of_other_values():
    src = (
        "import json\n\n"
        "def get(s):\n"
        '    return json.loads(s)["customer_name"]\n'
    )
    assert find_field_usages(src, "customer_name") == []


ORDERS = ["/orders/{order_id}"]


def test_skips_reads_from_a_different_endpoint():
    src = (
        "def a(c):\n"
        '    return c.get("/orders/1").json()["customer_name"]\n'
        "\n"
        "def b(c):\n"
        '    return c.get("/users/1").json()["customer_name"]\n'
    )
    assert [u.line for u in find_field_usages(src, "customer_name", ORDERS)] == [2]


def test_keeps_reads_when_the_url_is_not_visible():
    src = 'def a(c, url):\n    return c.get(url).json()["customer_name"]\n'
    assert len(find_field_usages(src, "customer_name", ORDERS)) == 1


def test_matches_f_string_urls():
    src = (
        "def a(c, order_id):\n"
        '    return c.get(f"/orders/{order_id}").json()["customer_name"]\n'
    )
    assert len(find_field_usages(src, "customer_name", ORDERS)) == 1


def test_matches_full_urls():
    src = (
        "def a(c):\n"
        '    return c.get("https://api.example.com/orders/7").json()["customer_name"]\n'
    )
    assert len(find_field_usages(src, "customer_name", ORDERS)) == 1


def test_does_not_match_a_longer_path():
    src = 'def a(c):\n    return c.get("/orders/7/lines").json()["customer_name"]\n'
    assert find_field_usages(src, "customer_name", ORDERS) == []
