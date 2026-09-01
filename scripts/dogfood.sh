#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export KRAFT_WORKSPACE_ROOT="${KRAFT_WORKSPACE_ROOT:-$ROOT}"
export KRAFT_HITL_MODE="${KRAFT_HITL_MODE:-review}"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

python - <<'PY'
from kraft.dogfood import DogfoodAuditLogger, build_dogfood_steps
logger = DogfoodAuditLogger()
logger.record(
    "workflow.started",
    phase="dogfood",
    steps=[step["id"] for step in build_dogfood_steps()],
)
print("[dogfood] workflow started")
print("[dogfood] steps:", ", ".join(step["id"] for step in build_dogfood_steps()))
PY

if command -v uv >/dev/null 2>&1; then
    uv run pytest -q test/test_tool_approval.py test/test_skill_search.py
    status=$?
elif python -c "import pytest" >/dev/null 2>&1; then
    python -m pytest -q test/test_tool_approval.py test/test_skill_search.py
    status=$?
else
    echo "[dogfood] pytest is not available. Run 'uv sync' or 'python -m pip install -e . pytest' first." >&2
    exit 1
fi

python - "$status" <<'PY'
import sys
from kraft.dogfood import DogfoodAuditLogger
logger = DogfoodAuditLogger()
status = "ok" if sys.argv[1] == "0" else "failed"
logger.record(
    "workflow.validation_complete",
    phase="dogfood",
    status=status,
)
print(f"[dogfood] validation status: {status}")
PY

if git diff --stat -- . ':(exclude)uv.lock' >/tmp/kraft_dogfood_diff.txt 2>/dev/null; then
    echo "[dogfood] diff summary:"
    cat /tmp/kraft_dogfood_diff.txt
else
    echo "[dogfood] no tracked diff summary available"
fi

echo "[dogfood] working tree status:"
git status --short || true

exit $status
