import sys
from pathlib import Path

from keepsync.__main__ import main

FIX = Path(__file__).parent / "fixtures"
OLD, NEW = str(FIX / "old.json"), str(FIX / "new.json")
CMD = f"{sys.executable} -m pytest -q"

CLIENT = 'def name(r):\n    return r.json()["customer_name"]\n'


def build_test_source(expected):
    return (
        "from client import name\n\n\n"
        "class R:\n    def json(self):\n"
        '        return {"customer": "Asha"}\n\n\n'
        f'def test_name():\n    assert name(R()) == "{expected}"\n'
    )


def make_repo(tmp_path, expected):
    (tmp_path / "client.py").write_text(CLIENT)
    (tmp_path / "test_client.py").write_text(build_test_source(expected))
    return tmp_path


def test_fix_kept_when_tests_pass(tmp_path):
    repo = make_repo(tmp_path, "Asha")
    assert main([OLD, NEW, str(repo), "--test-cmd", CMD]) == 0
    assert '["customer"]' in (repo / "client.py").read_text()


def test_fix_reverted_when_tests_fail(tmp_path):
    repo = make_repo(tmp_path, "Wrong")
    assert main([OLD, NEW, str(repo), "--test-cmd", CMD]) == 1
    assert (repo / "client.py").read_text() == CLIENT
