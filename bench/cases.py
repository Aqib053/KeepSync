from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Case:
    name: str
    old: dict  # response fields before: {name: type}
    new: dict  # response fields after
    files: dict  # the consumer repo: {file name: source}
    expect: str  # what a correct tool should do: fixed, untouched or reverted
    check: Optional[Callable] = None  # extra check on the files after the run


R_CLASS = '''

class R:
    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data

'''


def tests(imports: str, body: str) -> str:
    return imports + R_CLASS + body


def custom(client_src: str, test_body: str, imports: str = "from client import get\n") -> dict:
    return {"client.py": client_src, "test_client.py": tests(imports, test_body)}


def simple(read: str, data: str, expected: str) -> dict:
    """One consumer that returns `read`; the test feeds it the NEW response shape."""
    body = f"\ndef test_get():\n    assert get(R({data})) == {expected}\n"
    return custom(f"def get(r):\n    return {read}\n", body)


OLD = {"id": "integer", "customer_name": "string"}
NEW = {"id": "integer", "customer": "string"}
NEW_DATA = '{"id": 1, "customer": "Asha"}'
GET_ASHA = f'\ndef test_get():\n    assert get(R({NEW_DATA})) == "Asha"\n'

TWO_FILES = {
    "client.py": 'def get(r):\n    return r.json()["customer_name"]\n',
    "report.py": 'def title(r):\n    return r.json()["customer_name"].upper()\n',
    "test_client.py": tests(
        "from client import get\nfrom report import title\n",
        f'\ndef test_both():\n    assert get(R({NEW_DATA})) == "Asha"\n'
        f'    assert title(R({NEW_DATA})) == "ASHA"\n',
    ),
}

KEY_VAR = custom(
    'KEY = "customer_name"\n\n\ndef get(r):\n    return r.json()[KEY]\n', GET_ASHA)

MODEL = custom(
    "from dataclasses import dataclass\n\n\n@dataclass\nclass Order:\n"
    "    id: int\n    customer_name: str\n\n\n"
    "def get(r):\n    return Order(**r.json()).customer_name\n",
    GET_ASHA)

FORMAT = custom(
    'def get(r):\n    return "{customer_name}".format(**r.json())\n', GET_ASHA)

TRAP = custom(
    'def get(r):\n    return r.json()["customer_name"]\n\n\n'
    'def local_label(user):\n    return user["customer_name"]\n',
    GET_ASHA
    + '\n\ndef test_local():\n    assert local_label({"customer_name": "Local"}) == "Local"\n',
    imports="from client import get, local_label\n")

NAME_ONLY = custom(
    '# customer_name used to be returned here\n\n\n'
    'def customer_name_label(r):\n    return r.json()["id"]\n',
    '\ndef test_get():\n    assert customer_name_label(R({"id": 1, "customer": "x"})) == 1\n',
    imports="from client import customer_name_label\n")


CASES = [
    Case("01_rename_string_subscript", OLD, NEW,
         simple('r.json()["customer_name"]', NEW_DATA, '"Asha"'), "fixed"),
    Case("02_rename_int",
         {"id": "integer", "qty": "integer"}, {"id": "integer", "quantity": "integer"},
         simple('r.json()["qty"]', '{"id": 1, "quantity": 3}', "3"), "fixed"),
    Case("03_rename_float",
         {"id": "integer", "total": "number"}, {"id": "integer", "amount": "number"},
         simple('r.json()["total"]', '{"id": 1, "amount": 499.0}', "499.0"), "fixed"),
    Case("04_rename_get", OLD, NEW,
         simple('r.json().get("customer_name")', NEW_DATA, '"Asha"'), "fixed"),
    Case("05_rename_get_default", OLD, NEW,
         simple('r.json().get("customer_name", "n/a")', NEW_DATA, '"Asha"'), "fixed"),
    Case("06_rename_two_files", OLD, NEW, TWO_FILES, "fixed"),
    Case("07_rename_two_reads_one_line", OLD, NEW,
         simple('r.json()["customer_name"] + r.json()["customer_name"]',
                NEW_DATA, '"AshaAsha"'), "fixed"),
    Case("08_rename_single_quotes", OLD, NEW,
         simple("r.json()['customer_name']", NEW_DATA, '"Asha"'), "fixed"),
    Case("09_similar_key_left_alone",
         {"id": "integer", "customer_name": "string", "customer_name_full": "string"},
         {"id": "integer", "customer": "string", "customer_name_full": "string"},
         simple('r.json()["customer_name"] + r.json()["customer_name_full"]',
                '{"id": 1, "customer": "Asha", "customer_name_full": " Rao"}',
                '"Asha Rao"'), "fixed"),
    Case("10_hard_key_in_variable", OLD, NEW, KEY_VAR, "fixed"),
    Case("11_hard_dataclass_attribute", OLD, NEW, MODEL, "fixed"),
    Case("12_hard_format_string", OLD, NEW, FORMAT, "fixed"),
    Case("13_trap_unrelated_same_key", OLD, NEW, TRAP, "fixed",
         check=lambda after: 'user["customer_name"]' in after["client.py"]),
    Case("14_field_removed", OLD, {"id": "integer"},
         simple('r.json()["customer_name"]', '{"id": 1}', '"Asha"'), "untouched"),
    Case("15_field_added_only", OLD,
         {"id": "integer", "customer_name": "string", "note": "string"},
         simple('r.json()["customer_name"]',
                '{"id": 1, "customer_name": "Asha", "note": "x"}', '"Asha"'), "untouched"),
    Case("16_type_changed",
         {"id": "integer", "total": "integer"}, {"id": "integer", "total": "string"},
         simple('r.json()["total"]', '{"id": 1, "total": "5"}', '"5"'), "untouched"),
    Case("17_two_renames_ambiguous",
         {"first_name": "string", "last_name": "string"},
         {"given": "string", "family": "string"},
         simple('r.json()["first_name"]', '{"given": "A", "family": "B"}', '"A"'),
         "untouched"),
    Case("18_no_change", OLD, OLD,
         simple('r.json()["customer_name"]', '{"id": 1, "customer_name": "Asha"}', '"Asha"'),
         "untouched"),
    Case("19_name_only_in_comment", OLD, NEW, NAME_ONLY, "untouched"),
    Case("20_rename_but_test_fails", OLD, NEW,
         simple('r.json()["customer_name"]', NEW_DATA, '"Wrong"'), "reverted"),
]
