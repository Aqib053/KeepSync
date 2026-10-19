import os
import subprocess
from pathlib import Path

from keepsync.consumer import find_field_usages, rewrite_field
from keepsync.contract import diff_specs

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache"}


def python_files(repo: Path):
    for p in repo.rglob("*.py"):
        if not any(part in SKIP_DIRS for part in p.relative_to(repo).parts):
            yield p


def plan_fixes(old_spec: dict, new_spec: dict, repo: Path):
    """Return (changes, edits). edits = {file_path: new_source} for detected renames."""
    changes = diff_specs(old_spec, new_spec)
    renames = [c for c in changes if c.kind == "rename"]
    edits = {}
    for path in python_files(repo):
        source = path.read_text()
        new_source = source
        for c in renames:
            try:
                usages = find_field_usages(new_source, c.field)
            except SyntaxError:
                break
            if usages:
                new_source = rewrite_field(new_source, usages, c.field, c.new_field)
        if new_source != source:
            edits[path] = new_source
    return changes, edits


def run_tests(repo: Path, test_cmd: str, env_extra: dict) -> bool:
    env = {**os.environ, **env_extra}
    return subprocess.run(test_cmd, shell=True, cwd=repo, env=env).returncode == 0
