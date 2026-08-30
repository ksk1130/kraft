"""Grep 風テキスト検索ツール。

ファイルシステムから正規表現パターンに一致する行を検索します。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from kraft.tools.tool_logging import tool_logging_hook
from kraft.tools.file_read_safe import _normalize_path


# 検索から除外するディレクトリパターン
EXCLUDE_PATTERNS = {
    ".git",
    ".venv",
    ".vscode",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".gradle",
    "build",
    "dist",
    ".egg-info",
    ".mypy_cache",
    "target",  # Maven
}

# 検索対象ファイル拡張子（None = 全て、リスト = 制限）
ALLOWED_EXTENSIONS = None  # None で全拡張子対象（テキストファイルのみフィルター）

# バイナリファイルとして扱う拡張子
BINARY_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "bmp", "ico",
    "pdf", "zip", "tar", "gz", "rar", "7z",
    "exe", "dll", "so", "dylib",
    "pyc", "class", "o",
}


def _should_skip_dir(path: Path) -> bool:
    """ディレクトリをスキップすべきか判定（このディレクトリまたは祖先に除外パターンが含まれるか）。"""
    # このディレクトリの名前が除外パターンに該当するかチェック
    if path.name in EXCLUDE_PATTERNS or path.name.startswith("."):
        return True
    
    # 親ディレクトリにも除外パターンがないかチェック（ネストされたパスに対応）
    for parent in path.parents:
        if parent.name in EXCLUDE_PATTERNS or parent.name.startswith("."):
            return True
    
    return False


def _file_in_excluded_path(file_path: Path) -> bool:
    """ファイルが除外パターン内のディレクトリにあるかチェック。"""
    # ファイル自身のディレクトリと全ての祖先ディレクトリをチェック
    for part in file_path.parts:
        if part in EXCLUDE_PATTERNS or part.startswith("."):
            return True
    return False


def _should_skip_file(path: Path) -> bool:
    """ファイルをスキップすべきか判定。"""
    # バイナリファイル拡張子
    ext = path.suffix.lstrip(".").lower()
    if ext in BINARY_EXTENSIONS:
        return True
    
    # テキストライクな拡張子のみ対象
    text_extensions = {
        "txt", "md", "py", "js", "java", "go", "rs", "c", "h", "cpp",
        "cs", "ts", "tsx", "jsx", "html", "css", "json", "yaml", "yml",
        "xml", "sql", "sh", "bash", "ps1", "bat", "cmd", "gradle",
        "maven", "pom", "properties", "ini", "conf", "toml", "log",
        "error", "txt",
    }
    
    if ext:
        return ext not in text_extensions
    
    # 拡張子なしのテキストファイル（Dockerfile, Makefile など）
    return False


def _is_text_file(path: Path) -> bool:
    """ファイルがテキスト形式かどうかを判定。"""
    if _should_skip_file(path):
        return False
    
    try:
        # 最初の 512 バイトで判定
        with open(path, "rb") as f:
            chunk = f.read(512)
        return b"\x00" not in chunk  # null byte がなければテキスト
    except Exception:
        return False


def _log(message: str) -> None:
    """stdout キャプチャの影響を受けないよう直接出力する。"""
    try:
        sys.__stdout__.write(message + "\n")
        sys.__stdout__.flush()
    except Exception:
        print(message)


@tool_logging_hook(tool_name="grep_search", include_kwargs=("pattern", "path"))
def grep_search(
    pattern: str,
    path: str = ".",
    recursive: bool = True,
    case_sensitive: bool = False,
    max_results: int = 20,
) -> str:
    """
    ファイルシステムからパターンに一致する行を検索する。

    Args:
        pattern: 検索パターン（正規表現対応）
        path: 検索対象パス（ディレクトリまたはファイル）
        recursive: True で再帰検索
        case_sensitive: False で大文字小文字を区別しない
        max_results: 返す最大結果数

    Returns:
        マッチした行（ファイルパス:行番号 | テキスト 形式）
    """
    try:
        # パスを正規化
        normalized_path = _normalize_path(path)
        target_path = Path(normalized_path).resolve()

        _log(f"[TOOL EXECUTION] grep_search pattern={pattern} path={target_path}")

        if not target_path.exists():
            return f"Error: Path not found: {path}"

        # 正規表現をコンパイル
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return f"Error: Invalid regex pattern: {e}"

        results = []
        files_searched = 0
        matches_found = 0

        # ファイル検索
        if target_path.is_file():
            # 単一ファイルの場合
            files_to_search = [target_path]
        else:
            # ディレクトリの場合
            if recursive:
                files_to_search = [
                    f for f in target_path.rglob("*")
                    if f.is_file() and not _file_in_excluded_path(f)
                ]
            else:
                files_to_search = [
                    f for f in target_path.iterdir()
                    if f.is_file()
                ]

        # 各ファイルを検索
        for file_path in sorted(files_to_search):
            if matches_found >= max_results:
                break

            # バイナリファイルをスキップ
            if not _is_text_file(file_path):
                continue

            files_searched += 1

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                for line_num, line in enumerate(content.splitlines(), 1):
                    if regex.search(line):
                        # ファイルパスは相対パスで表示
                        try:
                            rel_path = file_path.relative_to(target_path.parent if target_path.is_file() else target_path)
                        except ValueError:
                            rel_path = file_path

                        result_line = f"{rel_path}:{line_num} | {line.strip()}"
                        results.append(result_line)
                        matches_found += 1

                        if matches_found >= max_results:
                            break
            except Exception as e:
                _log(f"[Warning] Failed to read {file_path}: {e}")
                continue

        # 結果を組み立て
        if not results:
            return f"No matches found for pattern: {pattern}"

        output_lines = [
            f"Pattern: {pattern}",
            f"Files searched: {files_searched}",
            f"Matches found: {matches_found}",
            "",
        ]
        output_lines.extend(results)

        if matches_found >= max_results:
            output_lines.append(f"... (truncated, max {max_results} results)")

        return "\n".join(output_lines)

    except Exception as e:
        error_msg = f"Error: Failed to search: {str(e)}"
        _log(error_msg)
        return error_msg

