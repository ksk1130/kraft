"""ファイル編集ツール - 直接実装版（Windows パス対応・差分更新対応）.

直接的にファイル操作を行うツールを実装します。

差分更新機能：
  - 行番号ベース編集
  - 行範囲ベース編集
  - 正規表現ベース置換
  - 従来の全文置換
"""

from __future__ import annotations

import os
import re
from difflib import unified_diff
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from kraft.tools.tool_logging import tool_logging_hook


def _workspace_root() -> Path:
    """ワークスペースの基準ルートを返す。"""
    configured = os.environ.get("KRAFT_WORKSPACE_ROOT")
    return Path(configured).expanduser().resolve() if configured else Path.cwd().resolve()


def _resolve_path(path_str: str) -> Path:
    """パス文字列を Path オブジェクトに変換し、絶対パスに正規化.
    
    Args:
        path_str: パス文字列（Windows/Unix いずれでも対応）.
        
    Returns:
        正規化された Path オブジェクト.
    """
    candidate = Path(path_str)
    if candidate.is_absolute():
        if os.name == "nt" and candidate.drive == "" and path_str.startswith(("/", "\\")):
            relative_path = path_str.lstrip("/\\")
            return (_workspace_root() / relative_path).resolve()
        return candidate.resolve()

    normalized = path_str.lstrip("/\\")
    return (_workspace_root() / normalized).resolve()


def _format_unified_diff(old_text: str, new_text: str) -> str:
    """編集前後の差分を unified diff 形式で整形し、行種別ごとに色付けする。"""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff_lines = list(unified_diff(
        old_lines,
        new_lines,
        fromfile="before",
        tofile="after",
        n=3,
    ))

    if not diff_lines:
        return "(差分なし)"

    colorized_lines: list[str] = []
    for line in diff_lines:
        if line.startswith("---") or line.startswith("+++"):
            colorized_lines.append(f"\x1b[36m{line}\x1b[0m")
        elif line.startswith("@@"):
            colorized_lines.append(f"\x1b[33m{line}\x1b[0m")
        elif line.startswith("-"):
            colorized_lines.append(f"\x1b[31m{line}\x1b[0m")
        elif line.startswith("+"):
            colorized_lines.append(f"\x1b[32m{line}\x1b[0m")
        else:
            colorized_lines.append(line)

    return "".join(colorized_lines).rstrip()


def preview_edit_file_change(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> str:
    """編集前に差分プレビューを作成する.

    実際の書き込みは行わず、承認画面に表示するための結果だけ返す。
    """
    path = _resolve_path(file_path)
    if not path.exists():
        return f"Error: file not found: {path}"

    try:
        original = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - read path errors
        return f"Error: failed to read {path}: {exc}"

    if old_string not in original:
        return f"Error: old_string not found in '{path}'"

    if replace_all:
        updated = original.replace(old_string, new_string)
    else:
        updated = original.replace(old_string, new_string, 1)

    return _format_unified_diff(original, updated)


@tool_logging_hook(tool_name="edit_file", include_kwargs=("file_path", "old_string", "new_string", "replace_all"))
def edit_file(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> str:
    """DeepAgents の built-in edit_file と同じ署名で差分付きの結果を返す。"""
    path = _resolve_path(file_path)
    if not path.exists():
        return f"Error: file not found: {path}"

    try:
        original = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - read path errors
        return f"Error: failed to read {path}: {exc}"

    if old_string not in original:
        return f"Error: old_string not found in '{path}'"

    if replace_all:
        occurrences = original.count(old_string)
        updated = original.replace(old_string, new_string)
    else:
        occurrences = 1
        updated = original.replace(old_string, new_string, 1)

    try:
        path.write_text(updated, encoding="utf-8")
    except Exception as exc:  # pragma: no cover - write path errors
        return f"Error: failed to write {path}: {exc}"

    return (
        f"Successfully replaced {occurrences} instance(s) of the string in '{path}'\n\n"
        f"差分:\n{_format_unified_diff(original, updated)}"
    )


@tool_logging_hook(tool_name="file_editor", include_kwargs=("operation",))
def file_editor(operation: str) -> str:
    """ファイル読み書きツール（Windows パス対応版・差分更新対応）.
    
    使用方法:
      1. view <path>
         -> ファイルの内容を表示
         
      2. create <path> with <contents>
         -> 新規ファイルを作成（既存ファイルは上書き）
         
      3. edit <path> with <old_string> -> <new_string>
         -> 既存ファイルを編集（old_string を new_string に置換）
         
      4. edit_line <path> <line_number> with <new_content>
         -> 特定の行を置換（トークン効率的な部分更新）
         例: edit_line README.md 5 with # New Title
         
      5. edit_range <path> <start_line>-<end_line> with <new_content>
         -> 行範囲を置換（複数行一括更新）
         例: edit_range config.py 10-15 with def new_function():...
         
      6. edit_regex <path> with <pattern> -> <replacement>
         -> 正規表現で置換（複雑なパターン置換）
         例: edit_regex log.txt with ERROR.* -> [REDACTED]
         
      7. delete <path>
         -> ファイルを削除
    
    Args:
        operation: 実行する操作（view/create/edit/edit_line/edit_range/edit_regex/delete）.
        
    Returns:
        実行結果.
    """
    try:
        parts = operation.split(None, 1)  # 最初のスペースで分割
        if not parts:
            return "エラー: 操作を指定してください（view/create/edit/edit_line/edit_range/edit_regex/delete）"
        
        verb = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        
        if verb == "view":
            # view <path>
            path_str = rest.strip()
            if not path_str:
                return "エラー: パスを指定してください"
            
            path = _resolve_path(path_str)
            if not path.exists():
                return f"エラー: ファイルが見つかりません: {path}"
            
            try:
                content = path.read_text(encoding='utf-8')
                return content
            except Exception as e:
                return f"エラー: ファイル読み込み失敗: {e}"
        
        elif verb == "create":
            # create <path> with <contents>
            path_str, _, content = rest.partition(" with ")
            path_str = path_str.strip()
            
            if not path_str:
                return "エラー: パスを指定してください"
            if not content:
                return "エラー: 'with' の後にファイル内容を指定してください"
            
            path = _resolve_path(path_str)
            
            # 親ディレクトリを作成
            path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                path.write_text(content, encoding='utf-8')
                return f"✓ ファイルを作成しました: {path}"
            except Exception as e:
                return f"エラー: ファイル作成失敗: {e}"
        
        elif verb == "edit":
            # edit <path> with <old_string> -> <new_string>
            path_str, _, rest_part = rest.partition(" with ")
            path_str = path_str.strip()
            
            if not path_str:
                return "エラー: パスを指定してください"
            if not rest_part:
                return "エラー: 'with' の後に置換内容を指定してください"
            
            # old -> new の形式を解析
            if " -> " in rest_part:
                old_str, _, new_str = rest_part.partition(" -> ")
            else:
                return "エラー: 置換形式が不正です（'old_string -> new_string' の形式を使用してください）"
            
            path = _resolve_path(path_str)
            
            if not path.exists():
                return f"エラー: ファイルが見つかりません: {path}"
            
            try:
                content = path.read_text(encoding='utf-8')
                
                # old_str が含まれているかチェック
                if old_str not in content:
                    return f"エラー: 置換対象の文字列が見つかりません: {old_str}"
                
                # 置換（最初のマッチのみ）
                new_content = content.replace(old_str, new_str, 1)
                path.write_text(new_content, encoding='utf-8')
                diff = _format_unified_diff(content, new_content)
                return f"✓ ファイルを編集しました: {path}\n\n差分:\n{diff}"
            except Exception as e:
                return f"エラー: ファイル編集失敗: {e}"
        
        elif verb == "edit_line":
            # edit_line <path> <line_number> with <new_content>
            # 形式: edit_line config.py 5 with new line content
            parts_line = rest.split(None, 2)  # パス、行番号、残り
            if len(parts_line) < 3:
                return "エラー: edit_line の形式が不正です（edit_line <path> <line_number> with <content>）"
            
            path_str = parts_line[0]
            line_str = parts_line[1]
            
            # "with" 以降を抽出
            if " with " not in rest:
                return "エラー: 'with' キーワードが見つかりません"
            
            _, _, new_line_content = rest.partition(" with ")
            
            try:
                line_num = int(line_str)
            except ValueError:
                return f"エラー: 行番号が無効です: {line_str}"
            
            if line_num < 1:
                return "エラー: 行番号は 1 以上である必要があります"
            
            path = _resolve_path(path_str)
            
            if not path.exists():
                return f"エラー: ファイルが見つかりません: {path}"
            
            try:
                content = path.read_text(encoding='utf-8')
                lines = content.splitlines(keepends=True)
                
                if line_num > len(lines):
                    return f"エラー: ファイルには {len(lines)} 行しかありません（行 {line_num} は存在しません）"
                
                original_line = lines[line_num - 1]
                # 行を置換（元の改行は保持）
                if lines[line_num - 1].endswith('\n'):
                    lines[line_num - 1] = new_line_content + '\n'
                elif lines[line_num - 1].endswith('\r\n'):
                    lines[line_num - 1] = new_line_content + '\r\n'
                else:
                    lines[line_num - 1] = new_line_content
                
                new_content = ''.join(lines)
                path.write_text(new_content, encoding='utf-8')
                diff = _format_unified_diff(content, new_content)
                return f"✓ ファイルの行 {line_num} を編集しました: {path}\n\n差分:\n{diff}"
            except Exception as e:
                return f"エラー: ファイル編集失敗: {e}"
        
        elif verb == "edit_range":
            # edit_range <path> <start>-<end> with <new_content>
            # 形式: edit_range config.py 10-15 with new content lines
            parts_range = rest.split(None, 2)  # パス、範囲、残り
            if len(parts_range) < 3:
                return "エラー: edit_range の形式が不正です（edit_range <path> <start>-<end> with <content>）"
            
            path_str = parts_range[0]
            range_str = parts_range[1]
            
            # "with" 以降を抽出
            if " with " not in rest:
                return "エラー: 'with' キーワードが見つかりません"
            
            _, _, new_range_content = rest.partition(" with ")
            
            # 範囲を解析
            if '-' not in range_str:
                return "エラー: 範囲の形式が無効です（start-end の形式を使用してください）"
            
            try:
                start_str, end_str = range_str.split('-', 1)
                start_line = int(start_str)
                end_line = int(end_str)
            except ValueError:
                return f"エラー: 行番号が無効です: {range_str}"
            
            if start_line < 1 or end_line < 1:
                return "エラー: 行番号は 1 以上である必要があります"
            
            if start_line > end_line:
                return f"エラー: 開始行 ({start_line}) は終了行 ({end_line}) より小さい必要があります"
            
            path = _resolve_path(path_str)
            
            if not path.exists():
                return f"エラー: ファイルが見つかりません: {path}"
            
            try:
                content = path.read_text(encoding='utf-8')
                lines = content.splitlines(keepends=True)
                
                if end_line > len(lines):
                    return f"エラー: ファイルには {len(lines)} 行しかありません（行 {end_line} は存在しません）"
                
                # 範囲を置換
                # 末尾の改行を保持するか判定
                last_newline = ''
                if end_line <= len(lines) and lines[end_line - 1].endswith(('\n', '\r\n')):
                    last_newline = '\n' if lines[end_line - 1].endswith('\n') else '\r\n'
                
                # start_line - 1 から end_line - 1 までの行を置換
                new_lines = lines[:start_line - 1] + [new_range_content + last_newline] + lines[end_line:]
                new_content = ''.join(new_lines)
                path.write_text(new_content, encoding='utf-8')
                diff = _format_unified_diff(content, new_content)
                return f"✓ ファイルの行 {start_line}-{end_line} を編集しました: {path}\n\n差分:\n{diff}"
            except Exception as e:
                return f"エラー: ファイル編集失敗: {e}"
        
        elif verb == "edit_regex":
            # edit_regex <path> with <pattern> -> <replacement>
            path_str, _, rest_part = rest.partition(" with ")
            path_str = path_str.strip()
            
            if not path_str:
                return "エラー: パスを指定してください"
            if not rest_part:
                return "エラー: 'with' の後に置換内容を指定してください"
            
            # pattern -> replacement の形式を解析
            if " -> " not in rest_part:
                return "エラー: 置換形式が不正です（'pattern -> replacement' の形式を使用してください）"
            
            pattern_str, _, replacement_str = rest_part.partition(" -> ")
            
            path = _resolve_path(path_str)
            
            if not path.exists():
                return f"エラー: ファイルが見つかりません: {path}"
            
            try:
                content = path.read_text(encoding='utf-8')
                
                # 正規表現をコンパイル
                try:
                    regex = re.compile(pattern_str)
                except re.error as e:
                    return f"エラー: 正規表現が無効です: {e}"
                
                # マッチ件数をチェック
                matches = list(regex.finditer(content))
                if not matches:
                    return f"エラー: パターンにマッチする文字列が見つかりません: {pattern_str}"
                
                # 置換（全件）
                new_content = regex.sub(replacement_str, content)
                path.write_text(new_content, encoding='utf-8')
                diff = _format_unified_diff(content, new_content)
                return f"✓ ファイルを編集しました（{len(matches)} 件マッチ）: {path}\n\n差分:\n{diff}"
            except Exception as e:
                return f"エラー: ファイル編集失敗: {e}"
        
        elif verb == "delete":
            # delete <path>
            path_str = rest.strip()
            
            if not path_str:
                return "エラー: パスを指定してください"
            
            path = _resolve_path(path_str)
            
            if not path.exists():
                return f"エラー: ファイルが見つかりません: {path}"
            
            try:
                path.unlink()  # ファイル削除
                return f"✓ ファイルを削除しました: {path}"
            except Exception as e:
                return f"エラー: ファイル削除失敗: {e}"
        
        else:
            return f"エラー: 不明な操作: {verb}（view/create/edit/delete のいずれかを使用してください）"
    
    except Exception as e:
        return f"予期しないエラー: {e}"
