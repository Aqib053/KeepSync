import argparse
from pathlib import Path

from keepsync.contract import load_spec
from keepsync.fix import plan_fixes, run_tests


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="keepsync")
    p.add_argument("old", help="old OpenAPI spec (JSON)")
    p.add_argument("new", help="new OpenAPI spec (JSON)")
    p.add_argument("repo", help="consumer repo to fix")
    p.add_argument("--test-cmd", default="python -m pytest")
    p.add_argument("--env", action="append", default=[], metavar="KEY=VALUE")
    args = p.parse_args(argv)

    repo = Path(args.repo).expanduser().resolve()
    env = dict(e.split("=", 1) for e in args.env)
    changes, edits = plan_fixes(load_spec(args.old), load_spec(args.new), repo)

    print(f"Changes found: {len(changes)}")
    for c in changes:
        label = f"{c.field} -> {c.new_field}" if c.kind == "rename" else c.field
        print(f"  [{c.kind}] {c.method} {c.path}: {label}")
    if not edits:
        print("No fixes to apply.")
        return 0

    originals = {path: path.read_text() for path in edits}
    for path, text in edits.items():
        path.write_text(text)
        print(f"Fixed: {path.relative_to(repo)}")

    print("Running tests...")
    if run_tests(repo, args.test_cmd, env):
        print("Tests pass. Fix is verified.")
        return 0

    for path, text in originals.items():
        path.write_text(text)
    print("Tests failed. Fix reverted.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
