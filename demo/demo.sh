#!/usr/bin/env bash
# KeepSync demo: an orders API renames a field, billing breaks, KeepSync fixes it.
# Usage: demo/demo.sh [--open-pr]
# --open-pr opens a REAL pull request on Aqib053/billing-service (close it afterwards).
# Run it with the KeepSync virtualenv active (Python 3.10+).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${KEEPSYNC_DEMO_DIR:-$HOME/Desktop/keepsync-lab/demo}"
PAUSE="${DEMO_PAUSE:-2}"
OPEN_PR=""

case "${1:-}" in
  "") ;;
  --open-pr) OPEN_PR="--open-pr" ;;
  *) echo "Usage: demo/demo.sh [--open-pr]"; exit 1 ;;
esac

# The script deletes folders inside $WORK, so refuse any other location.
case "$WORK" in
  */demo|*/keepsync-demo) ;;
  *) echo "Refusing to use $WORK: the folder name must end in /demo or /keepsync-demo"; exit 1 ;;
esac

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; sleep "$PAUSE"; }

if [ -n "$OPEN_PR" ]; then
  printf 'This opens a REAL pull request on Aqib053/billing-service. Continue? [y/N] '
  read -r answer
  [ "$answer" = "y" ] || { echo "Cancelled."; exit 0; }
fi

mkdir -p "$WORK"
VENV="$WORK/.venv"
if [ ! -x "$VENV/bin/python" ]; then
  say "First run: setting up the demo environment"
  python3 -m venv "$VENV"
  "$VENV/bin/python" -m pip install -q fastapi httpx pytest
fi
PY="$VENV/bin/python"

export_spec() {
  (cd "$WORK/orders" && "$PY" -c 'import json; from main import app; print(json.dumps(app.openapi(), indent=2))') > "$1"
}

say "Fresh copies of the two services"
rm -rf "$WORK/orders" "$WORK/billing"
git clone -q https://github.com/Aqib053/orders-service.git "$WORK/orders"
git clone -q https://github.com/Aqib053/billing-service.git "$WORK/billing"

say "1. The orders API today"
export_spec "$WORK/old.json"
echo "Response fields: id, customer_name, total"

say "2. The orders team renames customer_name to customer"
sed -i.bak 's/customer_name/customer/g' "$WORK/orders/main.py" "$WORK/orders/test_main.py"
rm -f "$WORK"/orders/*.bak
export_spec "$WORK/new.json"
git -C "$WORK/orders" --no-pager diff --stat

say "3. Billing's tests break against the new API"
(cd "$WORK/billing" && ORDERS_SERVICE_PATH="$WORK/orders" "$PY" -m pytest -q -p no:warnings 2>&1 | tail -n 8) || true

say "4. KeepSync finds the rename, fixes billing and checks the tests"
cd "$ROOT"
python3 -m keepsync "$WORK/old.json" "$WORK/new.json" "$WORK/billing" \
  --test-cmd "\"$PY\" -m pytest -q -p no:warnings" \
  --env "ORDERS_SERVICE_PATH=$WORK/orders" $OPEN_PR

say "5. What changed in billing"
if [ -n "$OPEN_PR" ]; then
  git -C "$WORK/billing" --no-pager show HEAD --format='%s' --patch
else
  git -C "$WORK/billing" --no-pager diff
fi

say "6. Billing's tests again"
(cd "$WORK/billing" && ORDERS_SERVICE_PATH="$WORK/orders" "$PY" -m pytest -q -p no:warnings 2>&1 | tail -n 4)

echo
if [ -n "$OPEN_PR" ]; then
  echo "A real PR was opened. Close it when you are done (replace NUMBER):"
  echo "  gh pr close NUMBER --repo Aqib053/billing-service --delete-branch --comment 'Demo PR. Not merging.'"
else
  echo "No PR was opened. Run demo/demo.sh --open-pr to also open one."
fi
