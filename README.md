# KeepSync

When one service changes its API, KeepSync fixes the services that use it,
runs their tests, and opens a PR only if the tests pass.

## How it works
1. Reads the API contract from the code (FastAPI routes and Pydantic models)
2. Compares old and new, and lists what broke
3. Finds the code in other repos that uses the changed API
4. An AI agent writes the fix
5. Runs the repo's tests in Docker, retries up to 3 times
6. Opens a PR only if the tests pass. A human approves.

Status: early prototype.
