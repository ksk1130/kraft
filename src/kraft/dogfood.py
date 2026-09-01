from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DOGFOOD_LOG_DIR = Path.home() / ".kraft" / "dogfood"


def build_dogfood_steps() -> list[dict[str, str]]:
    """標準 dogfood workflow の段階を返す."""
    return [
        {
            "id": "inspect",
            "name": "read-only inspection",
            "description": "Search and read only the files relevant to the task.",
        },
        {
            "id": "patch",
            "name": "targeted patch",
            "description": "Apply the smallest change that fixes the root cause.",
        },
        {
            "id": "verify",
            "name": "targeted validation",
            "description": "Run the smallest validation command that checks the change.",
        },
        {
            "id": "review",
            "name": "diff review",
            "description": "Inspect the diff and confirm no unintended changes slipped in.",
        },
        {
            "id": "report",
            "name": "summary report",
            "description": "Record the outcome and summarize the result for follow-up review.",
        },
    ]


class DogfoodAuditLogger:
    """dogfood 実行ログを JSON Lines 形式で記録する簡易ロガー."""

    def __init__(self, log_dir: str | os.PathLike[str] | None = None):
        configured = log_dir if log_dir is not None else os.environ.get(
            "KRAFT_DOGFOOD_LOG_DIR",
            str(DEFAULT_DOGFOOD_LOG_DIR),
        )
        self.log_dir = Path(configured).expanduser().resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.audit_path = self.log_dir / "dogfood_audit.jsonl"

    def record(self, event: str, **details: Any) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
        }
        if details:
            entry.update(details)
        with self.audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
        return entry

    def read_events(self) -> list[dict[str, Any]]:
        if not self.audit_path.exists():
            return []
        events: list[dict[str, Any]] = []
        with self.audit_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events
