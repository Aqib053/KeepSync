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


def test_open_pr_adds_only_changed_files(tmp_path, monkeypatch):
    from keepsync import fix
    from keepsync.contract import Change

    calls = []

    class Done:
        stdout = "https://github.com/x/y/pull/1\n"

    monkeypatch.setattr(fix.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or Done())
    change = Change("rename", "GET", "/orders/{order_id}", "customer_name", new_field="customer")
    url = fix.open_pr(tmp_path, [change], [tmp_path / "billing" / "client.py"])

    assert url.endswith("/pull/1")
    assert calls[0][:3] == ["git", "checkout", "-b"]
    assert ["git", "add", "billing/client.py"] in calls


def test_dry_run_changes_nothing(tmp_path, capsys):
    repo = make_repo(tmp_path, "Asha")
    assert main([OLD, NEW, str(repo), "--dry-run"]) == 0
    assert (repo / "client.py").read_text() == CLIENT
    out = capsys.readouterr().out
    assert '-    return r.json()["customer_name"]' in out
    assert '+    return r.json()["customer"]' in out
    assert "Dry run" in out


def test_dry_run_and_open_pr_cannot_be_combined(tmp_path):
    import pytest

    repo = make_repo(tmp_path, "Asha")
    with pytest.raises(SystemExit):
        main([OLD, NEW, str(repo), "--dry-run", "--open-pr"])
