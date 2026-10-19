import tempfile
from pathlib import Path

from bench.cases import FRESH
from bench.run import run_case


def cli() -> int:
    passed = 0
    print(f"{'case':<36}{'expected':<11}{'got':<11}result")
    with tempfile.TemporaryDirectory() as tmp:
        for case in FRESH:
            outcome, ok = run_case(case, Path(tmp))
            passed += ok
            print(f"{case.name:<36}{case.expect:<11}{outcome:<11}{'PASS' if ok else 'MISS'}")
    print(f"\nFresh score: {passed}/{len(FRESH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
