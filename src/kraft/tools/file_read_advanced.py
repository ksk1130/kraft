"""高度なファイル操作のラッパー.

方針:
- 通常のファイル読み込みは file_read_safe.file_read を使う
- このツールはファイル検索・統計・履歴風の簡易機能だけを提供する
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from kraft.tools.tool_logging import tool_logging_hook

ALLOWED_MODES = {"find", "stats", "time_machine"}


def _log(message: str) -> None:
    """stdout キャプチャの影響を受けないよう直接出力する。"""
    try:
        sys.__stdout__.write(message + "\n")
        sys.__stdout__.flush()
    except Exception:
        print(message)


def _build_tool_result_text(result: Any) -> str:
    """ファイル操作結果を安全に文字列化する。"""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    return str(result)


@tool_logging_hook(tool_name="file_read_advanced", include_kwargs=("path", "mode"))
def file_read_advanced(
    path: str,
    mode: str = "find",
    recursive: bool = True,
    num_revisions: int = 5,
) -> str:
    """簡易なファイル検索・統計機能を提供するラッパー。

    Args:
        path: 対象パスまたはパターン.
        mode: 実行モード（find/stats/time_machine）.
        recursive: find 時の再帰探索.
        num_revisions: time_machine 取得件数.

    Returns:
        実行結果テキスト.
    """
    mode_value = (mode or "find").strip().lower()
    _log(f"[TOOL EXECUTION] file_read_advanced mode={mode_value} path={path}")

    if mode_value not in ALLOWED_MODES:
        return (
            "file_read_advanced は非読み込みの高度機能のみ許可しています。"
            "使用可能モード: find, stats, time_machine。"
            "通常の内容読取は file_read を使用してください。"
        )

    root = Path(path).expanduser()
    if not root.exists():
        return f"Error: Path not found: {path}"

    if mode_value == "find":
        matches: list[str] = []
        iterator = root.rglob("*") if recursive and root.is_dir() else [root]
        for candidate in iterator:
            if candidate.is_file():
                matches.append(str(candidate.resolve()))
        return "\n".join(matches[:50]) if matches else "No files found."

    if mode_value == "stats":
        if root.is_file():
            stat = root.stat()
            return f"path={root}\nsize={stat.st_size}\nmtime={stat.st_mtime}"
        return f"path={root}\nkind=directory\nchildren={len(list(root.iterdir()))}"

    if mode_value == "time_machine":
        return (
            f"time_machine is not available in the lightweight DeepAgents build. "
            f"Requested path={path}, revisions={num_revisions}."
        )

    return "Unsupported mode"

