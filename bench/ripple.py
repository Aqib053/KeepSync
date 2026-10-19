import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from bench.cases import CASES
from bench.run import snapshot


def run_ripple(ripple_dir: Path, work: Path):
    python = ripple_dir / ".venv" / "bin" / "python"
    # Never let Ripple see GitHub or GitLab tokens, so it cannot open PRs anywhere.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GITHUB", "GITLAB", "GH_"))}
    result = subprocess.run(
        [str(python), "-m", "app.cli", "run",
         str(work / "old.yaml"), str(work / "new.yaml"),
         "--repos", str(work / "repo")],
        cwd=ripple_dir, env=env, capture_output=True, text=True, timeout=120,
    )
    match = re.search(r"Fixes generated:\s+(\d+)", result.stdout)
    return int(match.group(1)) if match else None


def tests_pass(repo: Path) -> bool:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q"], cwd=repo,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def classify(before: dict, after: dict, passes: bool) -> str:
    if after == before:
        return "untouched"
    return "fixed" if passes else "broke"


def cli() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ripple-dir", required=True)
    p.add_argument("--cases-dir", required=True)
    args = p.parse_args()
    ripple_dir = Path(args.ripple_dir).expanduser()
    cases_dir = Path(args.cases_dir).expanduser()

    rows = []
    print(f"{'case':<36}{'needs':<11}{'got':<11}{'ripple says':<13}result")
    with tempfile.TemporaryDirectory() as tmp:
        for case in CASES:
            work = Path(tmp) / case.name
            shutil.copytree(cases_dir / case.name, work)
            for name in ("old", "new"):
                shutil.copy(work / f"{name}.json", work / f"{name}.yaml")
            repo = work / "repo"
            before = snapshot(repo)
            try:
                reported = run_ripple(ripple_dir, work)
            except subprocess.TimeoutExpired:
                reported = None
            after = snapshot(repo)
            outcome = classify(before, after, tests_pass(repo))
            if case.expect == "fixed":
                ok = outcome == "fixed" and (case.check is None or bool(case.check(after)))
                needs = "fix"
            else:
                ok = outcome == "untouched"
                needs = "no edit"
            rows.append((needs, outcome, ok))
            said = "?" if reported is None else f"{reported} fixes"
            print(f"{case.name:<36}{needs:<11}{outcome:<11}{said:<13}{'PASS' if ok else 'MISS'}")

    need_fix = [r for r in rows if r[0] == "fix"]
    no_edit = [r for r in rows if r[0] == "no edit"]
    print(f"\nCorrect fixes:        {sum(r[2] for r in need_fix)}/{len(need_fix)}")
    print(f"Left alone correctly: {sum(r[2] for r in no_edit)}/{len(no_edit)}")
    print(f"Unsafe edits:         {sum(r[1] == 'broke' for r in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
