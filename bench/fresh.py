import sys
import tempfile
from pathlib import Path

from bench.cases import FRESH, FRESH2
from bench.run import run_case

BATCHES = {"1": FRESH, "2": FRESH2}


def cli() -> int:
    batch = sys.argv[sys.argv.index("--batch") + 1] if "--batch" in sys.argv else "1"
    cases = BATCHES[batch]
    passed = 0
    print(f"{'case':<36}{'expected':<11}{'got':<11}result")
    with tempfile.TemporaryDirectory() as tmp:
        for case in cases:
            outcome, ok = run_case(case, Path(tmp))
            passed += ok
            print(f"{case.name:<36}{case.expect:<11}{outcome:<11}{'PASS' if ok else 'MISS'}")
    print(f"\nFresh batch {batch} score: {passed}/{len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
