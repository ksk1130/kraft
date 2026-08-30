"""UTF-8 デフォルトでのシンプルなファイル読み込みスキル.

このツールは、Windows 環境でのエンコーディング問題を解決したシンプルな
ファイル読み込みツールです。

複雑な機能（diff, search, time_machine など）が必要な場合は、
file_read_advanced を使用してください。
"""

import sys
from pathlib import Path
from langchain_core.tools import tool

from kraft.tools.tool_logging import tool_logging_hook


def _normalize_path(path_str: str) -> str:
    """
    UNIX形式のパス（/c/Users/...）をWindows形式に正規化する。
    
    Args:
        path_str: 入力パス（UNIX形式またはWindows形式）
    
    Returns:
        正規化されたWindows形式のパス
    """
    # /c/Users/... -> C:\Users\...
    # /d/Data/... -> D:\Data\...
    if path_str.startswith('/') and len(path_str) > 2 and path_str[2] == '/':
        drive_letter = path_str[1].upper()
        rest = path_str[3:].replace('/', '\\')
        return f"{drive_letter}:\\{rest}"
    
    # forward slash を backslash に変換（Windows形式）
    return path_str.replace('/', '\\')


@tool_logging_hook(tool_name="file_read", include_kwargs=("path",))
def file_read(
    path: str,
    mode: str = "read",
    search_pattern: str | None = None,
    max_chars: int = 4000,
) -> str:
    """
    ファイルを読み込みます。デフォルトエンコーディングは UTF-8 です。

    互換性のため、mode を受け取れるようにしており、以下の動作をサポートします。
    - read / view: ファイル全体を返す
    - preview: 先頭の簡易プレビューを返す
    - search: pattern に一致する行を返す

    Args:
        path: 読み込むファイルのパス（UNIX形式またはWindows形式）.
        mode: 読み込みモード.
        search_pattern: search モードで使う検索パターン.
        max_chars: preview の最大文字数.

    Returns:
        ファイルの内容.

    Raises:
        FileNotFoundError: ファイルが見つからない場合.
    """
    mode_name = (mode or "read").lower()

    # ツール実行ログ（stderr と stdout の両方に出力して確認性を確保）
    tool_log = "[TOOL EXECUTION] file_read (simple version)\n"
    tool_log += f"  File: {path}\n"
    tool_log += f"  Mode: {mode_name}\n"
    sys.stderr.write(tool_log)
    print(tool_log, end="")

    try:
        # パスを正規化（UNIX形式 -> Windows形式）
        normalized_path = _normalize_path(path)
        file_path = Path(normalized_path).resolve()

        # ファイルが存在するか確認
        if not file_path.exists():
            return f"Error: File not found: {path}"

        # ファイルが通常ファイルか確認
        if not file_path.is_file():
            return f"Error: Path is not a file: {path}"

        # 常に UTF-8 で読み込み
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # UTF-8 デコード失敗時は latin-1 にフォールバック
            content = file_path.read_text(encoding="latin-1")

        if mode_name in {"read", "view"}:
            status = f"  Status: Successfully read {len(content)} characters\n"
            sys.stderr.write(status)
            print(status, end="")
            return content

        if mode_name == "preview":
            preview = content[: max_chars]
            status = f"  Status: Preview returned {len(preview)} characters\n"
            sys.stderr.write(status)
            print(status, end="")
            return preview

        if mode_name == "search":
            pattern = search_pattern or ""
            if not pattern:
                return "Error: search_pattern is required when mode='search'"
            matches = [line for line in content.splitlines() if pattern in line]
            result = "\n".join(matches) if matches else f"No matches found for pattern: {pattern}"
            status = f"  Status: Search returned {len(matches)} matching lines\n"
            sys.stderr.write(status)
            print(status, end="")
            return result

        return content

    except Exception as e:
        error_msg = f"  Error: {e}\n"
        sys.stderr.write(error_msg)
        print(error_msg, end="")
        return f"Error: {str(e)}"

