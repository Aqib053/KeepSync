# KeepSync

When one service renames an API field, KeepSync fixes the Python code that reads the old field, runs that repo's own tests, and opens a PR **only if the tests pass**. If the tests fail, the fix is reverted.

Status: early prototype. Built for internal service-to-service APIs, where you own both the API and the code that calls it.

## Demo

An orders API renamed `customer_name` to `customer`. A billing service reading the old field broke. KeepSync changed one line, billing's tests went from 1 failed to 2 passed, and it opened a PR: https://github.com/Aqib053/billing-service/pull/2 (closed, not merged: a demo only).

To watch the whole story on your machine, run `demo/demo.sh` from this repo.

## How it works

1. **Compare two OpenAPI specs** and list response-field changes. A rename means exactly one field is gone and one new field of the same type appeared. Anything unclear stays "removed" and "added" and is never auto-fixed.
2. **Find reads of the old field** in the consumer repo: `r.json()["x"]`, `.get("x")`, `json.loads(r.text)["x"]`, or a name assigned from one of those. This uses Python's `ast`, not AI, so results are repeatable. A read whose request URL is visible and belongs to a different endpoint is skipped.
3. **Rewrite only those exact spots.** Function names, comments and unrelated dictionaries are left alone.
4. **Run the repo's own tests.** Keep the fix only if they pass. Otherwise restore the original files.
5. **Optional:** `--open-pr` creates a branch, commits only the changed files, pushes, and opens a PR with the GitHub CLI.

## Use it on your own project

You need:
- Python 3.10 or newer
- The API's OpenAPI spec as a **JSON** file, from before and after the change (YAML is not supported yet)
- A Python repo that calls that API and has tests you can run on your machine

KeepSync is not on PyPI yet. You run it from a clone of this repo.

### 1. Set up KeepSync (once)

    git clone https://github.com/Aqib053/KeepSync.git
    cd KeepSync
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements.txt

### 2. Export the API spec before and after the change

A FastAPI example. Run it in the API repo, once on the old code and once on the new code:

    python -c "import json; from main import app; print(json.dumps(app.openapi(), indent=2))" > old.json
    # change the API, then:
    python -c "import json; from main import app; print(json.dumps(app.openapi(), indent=2))" > new.json

For other frameworks, export or download the spec as JSON.

### 3. Work on a copy

KeepSync edits files in place and restores them if the tests fail. Use a copy of the consumer repo, or a clean git branch, so `git diff` shows exactly what changed.

### 4. Run KeepSync on the consumer repo

From the KeepSync folder, with its virtualenv active:

    python -m keepsync /path/to/old.json /path/to/new.json /path/to/consumer-repo --test-cmd "/path/to/consumer-repo/.venv/bin/python -m pytest"

- `--test-cmd` is a shell command that runs the consumer repo's tests. It runs inside that repo, so use the repo's own Python to find its packages. Only run it on code you trust.
- `--env KEY=VALUE` passes an environment variable to the test command (repeat it for more).

### 5. Read the result

- `Changes found` lists what changed in the API.
- `Fixed: <file>` means it rewrote that file.
- `Tests pass. Fix is verified.` means the tests passed with the fix.
- `Tests failed. Fix reverted.` means it undid the edit. Nothing is left changed.
- `No fixes to apply.` means it found no safe fix.

Then run `git diff` in the repo, review it, and commit it yourself.

### Open a PR (optional)

Add `--open-pr`. After the tests pass, KeepSync creates a branch named `keepsync/<new field>`, commits only the changed files, pushes, and opens a PR with the GitHub CLI (`gh auth login` first). Use it only in a repo you own. In a fork, `gh` may point at the original project.

## Benchmark

Cases are written by the author, so they measure what the author imagined, not real-world code. Run them with `python -m bench.run`, `python -m bench.fresh` and `python -m bench.fresh --batch 2`.

| Set | First run | After fixes |
|---|---|---|
| Main (20 cases) | 16/20 | 17/20 |
| Fresh batch 1 (5 cases, written after the first fix) | 2/5 | 4/5 |
| Fresh batch 2 (5 cases) | 2/5 | 3/5 |

Across all runs no wrong edit was left behind: when a fix broke a test, it was reverted. "After fixes" numbers are on cases that were seen before the fix, so the first-run column is the one to trust.

## Limits

- **Python consumers only**, and **response-field renames only**. Request bodies, removed endpoints, type changes and added fields are detected but not fixed.
- **Not handled yet:** a key held in a variable or constant, a dataclass or model attribute, a format string, a helper that receives the data from another function, nested object fields, fields inside lists.
- The HTTP method is not checked, only the path.
- **A fix is only as safe as the repo's tests.** If no test reads the changed field, a wrong edit could be kept.
- Detection and edits use no AI, so KeepSync covers fewer patterns than an AI-based tool would.

## Related tools

- **Ripple** matches consumers by field name, and its README says fixes are syntax-checked. In our runs its local CLI detected the break but generated no fix. Its fix step appears to need an AI key, which we did not use, so we make no claim about what it can do with one.
- **depfix** targets vendor APIs and, per its README, runs tests before and after each fix. We read its page but did not run it.

## License

MIT. See [LICENSE](LICENSE).
