"""HITL 対話的プロンプト実装.

Rich ライブラリを使用した対話的なツール承認UI.
"""

import os
import sys
from typing import Literal, Optional
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.table import Table

from .tool_approval import ToolContext, ToolApprovalStatus
from kraft.tools.file_editor_wrapper import preview_edit_file_change


class HITLPrompt:
    """対話的なツール承認プロンプトの実装."""
    
    DEFAULT_TIMEOUT_SECONDS = 30
    
    def __init__(
        self,
        console: Optional[Console] = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ):
        """初期化.
        
        Args:
            console: Rich Console インスタンス（None なら新規作成）
            timeout_seconds: タイムアウト時間（秒）
        """
        self.console = console or Console()
        self.timeout_seconds = timeout_seconds
    
    def display_approval_prompt(self, context: ToolContext) -> str:
        """ツール承認プロンプトを表示して、ユーザー入力を受け取る.
        
        Args:
            context: ToolContext インスタンス
            
        Returns:
            ユーザーの選択: "y", "n", "?"
        """
        # ツール情報パネルを表示
        self._display_tool_info(context)
        
        # 選択肢を表示
        self._display_choices()

        # CI / pytest 実行時だけ自動承認。通常の対話実行では input() を使う。
        if _should_auto_approve_in_noninteractive():
            self.console.print("[green]✓ 自動実行環境のため自動承認されました[/green]")
            return "y"
        
        # ユーザー入力を受け取る
        while True:
            try:
                choice = input("> ").strip().lower()
                if choice in ("y", "yes"):
                    return "y"
                elif choice in ("n", "no"):
                    return "n"
                elif choice == "?":
                    return "?"
                else:
                    self.console.print(
                        "[yellow]❓ 選択肢は [Y]es, [n]o, [?] です[/yellow]"
                    )
                    self.console.print("[yellow]もう一度入力してください:[/yellow]")
                    continue
            except KeyboardInterrupt:
                self.console.print("\n[red]✗ キャンセルされました (Ctrl+C)[/red]")
                return "n"
            except (EOFError, OSError, ValueError):
                # stdin がパイプ、キャプチャ、または閉じられている場合
                self.console.print("\n[red]✗ 入力がありません。非対話環境のためスキップします[/red]")
                return "n"
    
    def _display_tool_info(self, context: ToolContext) -> None:
        """ツール情報をパネルで表示.
        
        Args:
            context: ToolContext インスタンス
        """
        # ツール名と分類
        tool_display = f"[bold cyan]{context.tool_name}[/bold cyan]"
        classification_text = self._get_classification_text(context.classification)
        
        title = f"🔧 実行承認待ち: {tool_display} {classification_text}"
        
        # パネルの内容
        content_lines = []
        
        if context.tool_description:
            content_lines.append(f"[dim]{context.tool_description}[/dim]")
            content_lines.append("")
        
        if context.tool_args:
            content_lines.append("[bold yellow]引数:[/bold yellow]")
            for key, value in context.tool_args.items():
                # 値の表示形式を調整
                if isinstance(value, str):
                    if len(value) > 60:
                        display_value = f'"{value[:60]}..."'
                    else:
                        display_value = f'"{value}"'
                elif isinstance(value, bool):
                    display_value = str(value)
                else:
                    display_value = str(value)
                
                content_lines.append(f"  [cyan]{key}[/cyan]: {display_value}")

        if context.tool_name == "edit_file":
            file_path = context.tool_args.get("file_path")
            old_string = context.tool_args.get("old_string")
            new_string = context.tool_args.get("new_string")
            replace_all = bool(context.tool_args.get("replace_all", False))

            if isinstance(file_path, str) and isinstance(old_string, str) and isinstance(new_string, str):
                content_lines.append("")
                content_lines.append("[bold yellow]変更プレビュー:[/bold yellow]")
                preview = preview_edit_file_change(file_path, old_string, new_string, replace_all=replace_all)
                content_lines.append(preview)
        
        content = "\n".join(content_lines)
        
        panel = Panel(
            content,
            title=title,
            border_style="cyan",
            expand=False,
        )
        self.console.print(panel)
    
    def _get_classification_text(self, classification: str) -> str:
        """分類に応じた表示テキストを返す.
        
        Args:
            classification: ツール分類
            
        Returns:
            表示テキスト
        """
        if classification == "safe":
            return "[green]✓ 安全[/green]"
        elif classification == "dangerous":
            return "[red]⚠️ 危険[/red]"
        elif classification == "requires_confirmation":
            return "[yellow]△ 要確認[/yellow]"
        else:
            return "[dim]?[/dim]"
    
    def _display_choices(self) -> None:
        """選択肢を表示.
        
        表示内容:
          [Y] 実行  [n] スキップ  [?] 詳細
        """
        choices_text = Text()
        choices_text.append("[Y] 実行  ", style="bold green")
        choices_text.append("[n] スキップ  ", style="bold red")
        choices_text.append("[?] 詳細", style="bold yellow")
        
        self.console.print(choices_text)
    
    def display_tool_details(self, context: ToolContext) -> None:
        """ツール詳細情報を表示.
        
        Args:
            context: ToolContext インスタンス
        """
        # 詳細パネル
        content_lines = []
        
        # 説明
        if context.tool_description:
            content_lines.append("[bold cyan]説明[/bold cyan]")
            content_lines.append(context.tool_description)
            content_lines.append("")
        
        # 分類情報
        content_lines.append("[bold cyan]分類[/bold cyan]")
        classification_text = self._get_classification_text(context.classification)
        content_lines.append(classification_text)
        content_lines.append("")
        
        # 引数詳細
        if context.tool_args:
            content_lines.append("[bold cyan]引数詳細[/bold cyan]")
            
            # テーブルで表示
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("名前", style="cyan")
            table.add_column("値", style="green")
            table.add_column("型", style="dim")
            
            for key, value in context.tool_args.items():
                type_name = type(value).__name__
                table.add_row(key, str(value), type_name)
            
            # テーブルを文字列に変換して内容に追加
            from io import StringIO
            string_io = StringIO()
            temp_console = Console(file=string_io, force_terminal=True)
            temp_console.print(table)
            content_lines.append(string_io.getvalue())
        
        content = "\n".join(content_lines)
        
        panel = Panel(
            content,
            title=f"📋 詳細: {context.tool_name}",
            border_style="magenta",
            expand=False,
        )
        self.console.print(panel)
    
    def prompt_for_approval_with_details(
        self,
        context: ToolContext,
    ) -> Literal["y", "n"]:
        """詳細表示を含むループで承認を受け取る.
        
        Args:
            context: ToolContext インスタンス
            
        Returns:
            "y" または "n"
        """
        while True:
            choice = self.display_approval_prompt(context)
            
            if choice == "?":
                # 詳細表示
                self.display_tool_details(context)
                self.console.print()  # 空行
                # ループして再度プロンプト表示
                continue
            else:
                # y or n で決定
                return choice
    
    def display_tool_approved(self, context: ToolContext) -> None:
        """ツール承認を通知.
        
        Args:
            context: ToolContext インスタンス
        """
        panel = Panel(
            f"[green]✓ 実行を承認しました: {context.tool_name}[/green]",
            border_style="green",
            expand=False,
        )
        self.console.print(panel)
    
    def display_tool_skipped(self, context: ToolContext) -> None:
        """ツールスキップを通知.
        
        Args:
            context: ToolContext インスタンス
        """
        panel = Panel(
            f"[yellow]⊘ スキップしました: {context.tool_name}[/yellow]",
            border_style="yellow",
            expand=False,
        )
        self.console.print(panel)
    
    def display_tool_timed_out(self, context: ToolContext) -> None:
        """ツールタイムアウトを通知.
        
        Args:
            context: ToolContext インスタンス
        """
        panel = Panel(
            f"[red]✗ タイムアウト: {context.tool_name} "
            f"({self.timeout_seconds}s) [/red]\n"
            "[dim]スキップされました[/dim]",
            border_style="red",
            expand=False,
        )
        self.console.print(panel)


def _should_auto_approve_in_noninteractive() -> bool:
    """CI / pytest 実行時だけ自動承認する.

    通常の対話型CLIでは、入力可能なstdinでなくても確認プロンプトを出し、
    実行前にユーザー判断を求める。自動実行環境のみ自動承認へフォールバックする。
    """
    return bool(os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("CI"))


def get_user_approval(
    context: ToolContext,
    hitl_mode: str = "interactive",
    timeout_seconds: int = HITLPrompt.DEFAULT_TIMEOUT_SECONDS,
) -> bool:
    """便利関数: ツール承認を取得.
    
    Args:
        context: ToolContext インスタンス
        hitl_mode: HITL モード（"interactive" 推奨）
        timeout_seconds: タイムアウト時間
        
    Returns:
        True なら実行許可、False なら実行スキップ
    """
    if hitl_mode == "auto":
        context.approve()
        return True

    if _should_auto_approve_in_noninteractive():
        context.approve()
        return True

    prompt = HITLPrompt(timeout_seconds=timeout_seconds)
    choice = prompt.prompt_for_approval_with_details(context)
    
    if choice == "y":
        context.approve()
        prompt.display_tool_approved(context)
        return True
    else:
        context.skip()
        prompt.display_tool_skipped(context)
        return False

