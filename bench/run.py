import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

from bench.cases import CASES
from bench.specs import make_spec
from keepsync.__main__ import main


def build(case, root: Path) -> Path:
    case_dir = root / case.name
    repo = case_dir / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (case_dir / "old.json").write_text(json.dumps(make_spec(case.old), indent=2))
    (case_dir / "new.json").write_text(json.dumps(make_spec(case.new), indent=2))
    for name, source in case.files.items():
        (repo / name).write_text(source)
    return case_dir


def snapshot(repo: Path) -> dict:
    return {p.name: p.read_text() for p in repo.glob("*.py")}


def run_case(case, root: Path):
    case_dir = build(case, root)
    repo = case_dir / "repo"
    before = snapshot(repo)
    cmd = f'"{sys.executable}" -m pytest -q >/dev/null 2>&1'
    argv = [str(case_dir / "old.json"), str(case_dir / "new.json"), str(repo),
            "--test-cmd", cmd]
    with contextlib.redirect_stdout(io.StringIO()):
        code = main(argv)
    after = snapshot(repo)
    if code != 0:
        outcome = "reverted"
    elif after != before:
        outcome = "fixed"
    else:
        outcome = "untouched"
    ok = outcome == case.expect
    if ok and case.check is not None:
        ok = bool(case.check(after))
    return outcome, ok


def cli() -> int:
    if "--export" in sys.argv:
        export = Path(sys.argv[sys.argv.index("--export") + 1]).expanduser()
        for case in CASES:
            build(case, export)
        print(f"Exported {len(CASES)} untouched cases to {export}\n")
    passed = 0
    print(f"{'case':<36}{'expected':<11}{'got':<11}result")
    with tempfile.TemporaryDirectory() as tmp:
        for case in CASES:
            outcome, ok = run_case(case, Path(tmp))
            passed += ok
            print(f"{case.name:<36}{case.expect:<11}{outcome:<11}{'PASS' if ok else 'MISS'}")
    print(f"\nScore: {passed}/{len(CASES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
