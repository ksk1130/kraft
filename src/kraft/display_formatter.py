"""Rich ベースの表示フォーマッター.

SkillChord から移植。
起動、処理中、最終回答、警告、エラーを見栄え良く分離して表示する。
"""

from contextlib import contextmanager
import re
import sys
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# グローバル Console インスタンス
# PowerShell 環境での stdin 検出失敗を回避（force_interactive=False で check_unicode を無効化）
console = Console(
    force_terminal=True if sys.stdout.isatty() else None,
    force_interactive=False,
    width=100,
)

_live_working: Live | None = None


def _detect_java_code(text: str) -> tuple[bool, str, str]:
    """テキスト内の Java コードを検出して抽出.
    
    Args:
        text: 分析対象テキスト.
        
    Returns:
        (is_java_code, description, code) タプル。
        is_java_code: Java コードが含まれているか。
        description: コード前のテキスト（説明）。
        code: 抽出されたコード。
    """
    # Java クラス定義パターン
    java_class_pattern = re.compile(
        r'(.*?)(?:^|\n)((?:public\s+)?(?:class|interface)\s+\w+.*)',
        re.DOTALL | re.MULTILINE
    )
    
    match = java_class_pattern.search(text)
    if match:
        desc = match.group(1).strip()
        code_start = match.group(2)
        # クラス定義後のすべてのコードを抽出
        # 説明テキスト部分を除いた後のすべてを使用
        start_pos = text.find(code_start)
        if start_pos >= 0:
            code = text[start_pos:].strip()
        else:
            code = code_start.strip()
        return True, desc, code
    
    return False, "", ""


def _detect_python_code(text: str) -> tuple[bool, str, str]:
    """テキスト内の Python コードを検出して抽出.
    
    Args:
        text: 分析対象テキスト.
        
    Returns:
        (is_python_code, description, code) タプル。
    """
    # Python 関数定義パターン
    python_def_pattern = re.compile(
        r'(.*?)(?:^|\n)(def\s+\w+.*?(?=\ndef|\Z))',
        re.DOTALL | re.MULTILINE
    )
    
    match = python_def_pattern.search(text)
    if match:
        desc = match.group(1).strip()
        code = match.group(2).strip()
        return True, desc, code
    
    return False, "", ""


def _parse_and_render_answer(answer: str):
    """Markdown テキスト内のコードブロックをシンタックスハイライト対応で処理.
    
    ```language ... ``` 形式のコードブロックを検出して、
    言語別のシンタックスハイライトを適用。
    通常のテキストは Markdown としてレンダリング。
    
    Args:
        answer: 最終回答テキスト.
        
    Returns:
        Rich renderable (Syntax, Markdown, Text, または Group).
    """
    if not answer.strip():
        return Text("")
    
    # code block の開始・終了を検出するパターン
    code_block_pattern = re.compile(r'^```(\w*)\n(.*?)\n```', re.MULTILINE | re.DOTALL)
    
    # マッチしたブロックを収集（位置情報付き）
    matches = list(code_block_pattern.finditer(answer))
    
    if not matches:
        # Fallback: Java コード検出
        is_java, java_desc, java_code = _detect_java_code(answer)
        if is_java:
            elements = []
            if java_desc:
                try:
                    elements.append(Markdown(java_desc))
                except:
                    elements.append(Text(java_desc))
            try:
                elements.append(Syntax(
                    java_code,
                    "java",
                    theme="monokai",
                    line_numbers=False,
                    word_wrap=True,
                    background_color="default",
                ))
            except Exception:
                elements.append(Text(java_code, style="dim"))
            
            if len(elements) > 1:
                return Group(*elements)
            elif len(elements) == 1:
                return elements[0]
        
        # Fallback: Python コード検出
        is_python, py_desc, py_code = _detect_python_code(answer)
        if is_python:
            elements = []
            if py_desc:
                try:
                    elements.append(Markdown(py_desc))
                except:
                    elements.append(Text(py_desc))
            try:
                elements.append(Syntax(
                    py_code,
                    "python",
                    theme="monokai",
                    line_numbers=False,
                    word_wrap=True,
                    background_color="default",
                ))
            except Exception:
                elements.append(Text(py_code, style="dim"))
            
            if len(elements) > 1:
                return Group(*elements)
            elif len(elements) == 1:
                return elements[0]
        
        # コードブロックがない場合は Markdown で返す
        return Markdown(answer)
    
    # コードブロック前後のテキストとコードを交互に配置
    elements = []
    last_end = 0
    
    for match in matches:
        # コードブロック前のテキスト
        before_text = answer[last_end:match.start()].rstrip()
        if before_text:
            try:
                elements.append(Markdown(before_text))
            except:
                elements.append(Text(before_text))
        
        # コードブロック自体
        lang = match.group(1) or "text"
        code = match.group(2).strip()
        
        try:
            # 言語別のハイライト
            # Java, Python, JavaScript/TypeScript, C#, Go, Rust など対応
            syntax = Syntax(
                code,
                lang,
                theme="monokai",
                line_numbers=False,
                word_wrap=True,
                background_color="default",
            )
            elements.append(syntax)
        except Exception:
            # 言語が不明な場合は通常テキスト
            elements.append(Text(f"```{lang}\n{code}\n```", style="dim"))
        
        last_end = match.end()
    
    # 最後のコードブロック後のテキスト
    after_text = answer[last_end:].lstrip()
    if after_text:
        try:
            elements.append(Markdown(after_text))
        except:
            elements.append(Text(after_text))
    
    # 単一要素なら返す、複数なら Group
    if len(elements) == 1:
        return elements[0]
    elif len(elements) > 1:
        return Group(*elements)
    else:
        return Text("")


def display_welcome() -> None:
    """ウェルカムメッセージを表示.
    
    インタラクティブモード起動時に表示される。
    """
    title = Text("kraft - スキル統合チャット", style="bold cyan")
    welcome_panel = Panel(
        title,
        title="Welcome",
        border_style="cyan",
        expand=False,
    )
    console.print(welcome_panel)
    console.print(
        "Enter your queries below. Type [bold yellow]'exit'[/bold yellow] or [bold yellow]'quit'[/bold yellow] to quit.",
        style="dim"
    )


def display_working(message: str) -> None:
    """作業中メッセージを同じ行で更新して表示.
    
    Rich の Live を使うことで、長時間の処理中でも画面が固定せず
    進行状況が見えるようになる。
    
    Args:
        message: 表示するメッセージ.
    """
    global _live_working

    status = Text(f"[assistant] {message}", style="bold cyan")
    if _live_working is None:
        _live_working = Live(status, console=console, refresh_per_second=10, transient=False)
        _live_working.start()
    else:
        _live_working.update(status)


def stop_live_working() -> None:
    """作業中表示を停止して、次の通常表示に戻す。"""
    global _live_working
    if _live_working is not None:
        _live_working.stop()
        _live_working = None


def display_execution_mode(mode: str) -> None:
    """実行モードをユーザーに見える形で表示する.
    
    Args:
        mode: "single" または "multi".
    """
    normalized_mode = (mode or "single").strip().lower()
    label = "MULTI-STAGE" if normalized_mode == "multi" else "SINGLE"
    border_style = "magenta" if normalized_mode == "multi" else "cyan"
    mode_panel = Panel(
        Text(label, style="bold white"),
        title="Execution Mode",
        border_style=border_style,
        expand=False,
    )
    console.print(mode_panel)


def display_final_answer(answer: str) -> None:
    """最終回答を目立つパネルで表示.
    
    LLM からの最終結果を Green のパネルで表示し、
    作業途中のログと明確に区別する。
    コードブロック（```language ... ```）にはシンタックスハイライトを適用。
    
    Args:
        answer: 最終回答テキスト.
    """
    # コードブロック対応のレンダリング
    if answer.strip():
        rendered = _parse_and_render_answer(answer)
        answer_panel = Panel(
            rendered,
            title="[bold]Agent Response[/bold]",
            border_style="green",
            padding=(1, 1),
        )
    else:
        answer_panel = Panel(
            "[dim](no response)[/dim]",
            title="[bold]Agent Response[/bold]",
            border_style="green",
            padding=(1, 1),
        )
    stop_live_working()
    console.print()
    console.print(answer_panel)


def display_key_finding(message: str) -> None:
    """重要発見を警告パネルで表示.
    
    エラーや重要な情報を Yellow のパネルで表示。
    
    Args:
        message: 重要な情報メッセージ.
    """
    finding_panel = Panel(
        message,
        title="[bold yellow]Key Finding[/bold yellow]",
        border_style="yellow",
        padding=(1, 1),
    )
    console.print(finding_panel)


def display_error(error_message: str) -> None:
    """エラーメッセージを赤いパネルで表示.
    
    Args:
        error_message: エラー説明.
    """
    stop_live_working()
    error_panel = Panel(
        error_message,
        title="[bold red]ERROR[/bold red]",
        border_style="red",
        padding=(1, 1),
    )
    console.print(error_panel)


def display_goodbye() -> None:
    """終了メッセージを表示.
    
    セッション終了時に表示される。
    """
    goodbye_panel = Panel(
        "[bold green]さようなら！何かお手伝いできることがあれば、またお気軽にお声がけください。[/bold green]",
        title="[green bold]終了[/green bold]",
        border_style="green"
    )
    console.print()
    console.print(goodbye_panel)


# ============================================================================
# TODO 4: 追加の表示ヘルパー
# ============================================================================

def display_tool_execution_start(tool_name: str) -> None:
    """ツール実行開始を表示.
    
    Args:
        tool_name: ツール名（例: "grep_search", "file_read"）
    """
    msg = f"🔧 [bold cyan]{tool_name}[/bold cyan] を実行中..."
    console.print(f"[dim]{msg}[/dim]")


def display_tool_execution_end(tool_name: str, success: bool = True, duration_ms: float | None = None) -> None:
    """ツール実行終了を表示.
    
    Args:
        tool_name: ツール名
        success: 実行成功フラグ
        duration_ms: 実行時間（ミリ秒）
    """
    symbol = "✓" if success else "✗"
    color = "green" if success else "red"
    status = "完了" if success else "失敗"
    
    msg = f"{symbol} [bold {color}]{tool_name}[/bold {color}] {status}"
    if duration_ms is not None:
        msg += f" ({duration_ms:.1f}ms)"
    
    console.print(f"[dim]{msg}[/dim]")


@contextmanager
def display_spinner(message: str = "処理中", spinner_style: str = "dots"):
    """スピナー付きの状態表示コンテキストマネージャー.
    
    Usage:
        with display_spinner("ファイルを読み込み中"):
            # 処理...
    
    Args:
        message: スピナーに表示するメッセージ
        spinner_style: スピナーのスタイル（"dots", "line", "dots2" など）
    """
    with console.status(f"[bold cyan]{message}[/bold cyan]", spinner_style=spinner_style):
        yield


def display_progress_bar(items: list[str], description: str = "処理中", show_count: bool = True):
    """プログレスバー付きの反復処理.
    
    Usage:
        for item in display_progress_bar(file_list, "ファイル処理中"):
            # item を処理...
    
    Args:
        items: 処理対象リスト
        description: 説明文
        show_count: 件数表示の有無
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        expand=False
    ) as progress:
        task = progress.add_task(description, total=len(items))
        for item in items:
            yield item
            progress.advance(task)


def display_results_table(rows: list[dict], columns: list[str] | None = None, title: str = "結果", style: str = "cyan") -> None:
    """辞書のリストをテーブル形式で表示.
    
    Args:
        rows: {'column_name': 'value', ...} の形式でのリスト
        columns: 表示するカラム名のリスト（未指定時は rows[0].keys() を使用）
        title: テーブルのタイトル
        style: テーブルスタイル
    """
    if not rows:
        console.print(f"[dim]（{title}はありません）[/dim]")
        return
    
    # カラムを決定
    if columns is None:
        columns = list(rows[0].keys()) if rows else []
    
    # テーブルを作成
    table = Table(title=f"[bold {style}]{title}[/bold {style}]", show_header=True, header_style=f"bold {style}")
    
    for col in columns:
        table.add_column(col, style=style)
    
    # 行データを追加
    for row in rows:
        values = [str(row.get(col, "-")) for col in columns]
        table.add_row(*values)
    
    console.print()
    console.print(table)
    console.print()


def truncate_output(text: str, max_lines: int = 50, max_chars: int = 2000) -> str:
    """ツール出力を制限してトークン使用量を削減.
    
    エージェントループ内でツールからの長い出力がトークン制限エラーを
    引き起こすのを防ぐため、出力行数と文字数を制限する。
    
    Args:
        text: 元のテキスト（ツール出力）.
        max_lines: 最大行数（デフォルト: 50行）.
        max_chars: 最大文字数（デフォルト: 2000文字）.
        
    Returns:
        制限されたテキスト。超過分は「... [出力省略]」で示す。
    """
    if not text:
        return text
    
    lines = text.split('\n')
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines.append(f"\n... [残り {len(text.split(chr(10))) - max_lines} 行は省略されました]")
    
    result = '\n'.join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + f"\n... [残り {len(result) - max_chars} 文字は省略されました]"
    
    return result


__all__ = [
    "console",
    "display_welcome",
    "display_working",
    "stop_live_working",
    "display_execution_mode",
    "display_final_answer",
    "display_key_finding",
    "display_error",
    "display_goodbye",
    # TODO 4: 追加の表示ヘルパー
    "display_tool_execution_start",
    "display_tool_execution_end",
    "display_spinner",
    "display_progress_bar",
    "display_results_table",
    # トークン制限エラー回避
    "truncate_output",
]

