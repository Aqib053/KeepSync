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

**What you need**
- Python 3.10 or newer.
- Your API's OpenAPI description saved as **JSON**, from **before** and **after** the change. YAML is not supported yet.
- A Python project that calls your API and has tests.

**Steps**

1. Get KeepSync (once):

```
git clone https://github.com/Aqib053/KeepSync.git
cd KeepSync
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

2. Save your API description before you change the API. For FastAPI, run this inside your API project:

```
python -c "import json; from main import app; print(json.dumps(app.openapi(), indent=2))" > old.json
```

Change your API, then run it again and save the result as `new.json`.

3. Make a **copy** of the project that calls your API. KeepSync edits files in that copy.

4. From the KeepSync folder, run:

```
python -m keepsync old.json new.json /path/to/your-copy --test-cmd "python -m pytest"
```

If your tests need packages from your project's own virtual environment, use that Python's full path, like `/path/to/your-copy/.venv/bin/python -m pytest`.

5. Read the last line of the output:
- `Tests pass. Fix is verified.` means it fixed your code and your tests agree.
- `Tests failed. Fix reverted.` means it undid the change, and nothing is changed.
- `No fixes to apply.` means it found nothing it could fix safely.

6. Run `git diff` in your copy, check the change, and copy it to your real project.

**Safety**
- Use it only on projects you own.
- Don't add `--open-pr` in a fork of someone else's project, because the pull request may go to the original project.
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
