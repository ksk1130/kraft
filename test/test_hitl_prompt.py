#!/usr/bin/env python
"""HITL hitl_prompt モジュールのテスト."""
import sys
sys.path.insert(0, "src")

from kraft.approval import ToolContext, HITLPrompt, get_user_approval
from rich.console import Console
from io import StringIO


def test_hitl_prompt_initialization():
    """HITLPrompt の初期化テスト."""
    print("=" * 70)
    print("Test: HITLPrompt Initialization")
    print("=" * 70)
    
    # デフォルト設定
    prompt = HITLPrompt()
    assert prompt.timeout_seconds == 30
    assert prompt.console is not None
    print("✓ Default initialization OK")
    
    # カスタム設定
    console = Console()
    prompt2 = HITLPrompt(console=console, timeout_seconds=60)
    assert prompt2.timeout_seconds == 60
    assert prompt2.console is console
    print("✓ Custom initialization OK")
    print()


def test_classification_text():
    """分類テキスト表示テスト."""
    print("=" * 70)
    print("Test: Classification Text Display")
    print("=" * 70)
    
    prompt = HITLPrompt()
    
    # Safe
    text = prompt._get_classification_text("safe")
    assert "SAFE" in text or "✓" in text
    print(f"✓ Safe classification text: {text}")
    
    # Dangerous
    text = prompt._get_classification_text("dangerous")
    assert "DANGEROUS" in text or "⚠️" in text
    print(f"✓ Dangerous classification text: {text}")
    
    # Requires confirmation
    text = prompt._get_classification_text("requires_confirmation")
    assert "CONFIRMATION" in text or "△" in text
    print(f"✓ Requires confirmation text: {text}")
    
    print()


def test_tool_info_display():
    """ツール情報表示テスト（ユーザー入力なし）."""
    print("=" * 70)
    print("Test: Tool Info Display (non-interactive)")
    print("=" * 70)
    
    # StringIO で出力をキャプチャ
    string_io = StringIO()
    console = Console(file=string_io, width=80, force_terminal=True)
    prompt = HITLPrompt(console=console)
    
    # ツールコンテキスト
    ctx = ToolContext(
        tool_name="grep_search",
        tool_args={
            "query": "password",
            "isRegexp": True,
            "includePattern": "src/**/*.py",
        },
        tool_description="Search in workspace",
    )
    
    # 表示テスト（ユーザー入力は行わない）
    prompt._display_tool_info(ctx)
    
    output = string_io.getvalue()
    assert "grep_search" in output
    assert "Arguments" in output or "query" in output
    print("✓ Tool info display OK")
    print(f"Output length: {len(output)} chars")
    print()


def test_edit_file_preview_display(tmp_path):
    """edit_file の承認画面に変更プレビューが表示される."""
    target_file = tmp_path / "hello.txt"
    target_file.write_text("こんにちは\n", encoding="utf-8")

    string_io = StringIO()
    console = Console(file=string_io, width=80, force_terminal=True)
    prompt = HITLPrompt(console=console)

    ctx = ToolContext(
        tool_name="edit_file",
        tool_args={
            "file_path": str(target_file),
            "old_string": "こんにちは",
            "new_string": "コンニチハ",
            "replace_all": True,
        },
        tool_description="Edit file contents",
    )

    prompt._display_tool_info(ctx)

    output = string_io.getvalue()
    assert "変更プレビュー" in output
    assert "コンニチハ" in output
    assert "OLD" in output or "before" in output
    print("✓ Edit file preview display OK")
    print()


def test_tool_details_display():
    """ツール詳細表示テスト."""
    print("=" * 70)
    print("Test: Tool Details Display")
    print("=" * 70)
    
    string_io = StringIO()
    console = Console(file=string_io, width=80, force_terminal=True)
    prompt = HITLPrompt(console=console)
    
    ctx = ToolContext(
        tool_name="bash",
        tool_args={"command": "ls -la /home", "shell": "powershell"},
        tool_description="Execute bash command",
    )
    
    # 詳細表示テスト
    prompt.display_tool_details(ctx)
    
    output = string_io.getvalue()
    assert "bash" in output
    assert "詳細" in output or "説明" in output
    print("✓ Tool details display OK")
    print()


def test_approval_notification():
    """承認通知テスト."""
    print("=" * 70)
    print("Test: Approval Notification")
    print("=" * 70)
    
    string_io = StringIO()
    console = Console(file=string_io, width=80, force_terminal=True)
    prompt = HITLPrompt(console=console)
    
    ctx = ToolContext(tool_name="calculator", tool_args={"a": 5, "b": 3})
    
    # 承認通知
    prompt.display_tool_approved(ctx)
    output = string_io.getvalue()
    assert "Executing" in output or "calculator" in output
    print("✓ Approval notification OK")
    
    # スキップ通知
    string_io2 = StringIO()
    console2 = Console(file=string_io2, width=80, force_terminal=True)
    prompt2 = HITLPrompt(console=console2)
    prompt2.display_tool_skipped(ctx)
    output2 = string_io2.getvalue()
    assert "Skipped" in output2 or "calculator" in output2
    print("✓ Skip notification OK")
    
    # タイムアウト通知
    string_io3 = StringIO()
    console3 = Console(file=string_io3, width=80, force_terminal=True)
    prompt3 = HITLPrompt(console=console3, timeout_seconds=30)
    prompt3.display_tool_timed_out(ctx)
    output3 = string_io3.getvalue()
    assert "Timed out" in output3 or "calculator" in output3
    print("✓ Timeout notification OK")
    
    print()


def test_get_user_approval_auto_mode():
    """get_user_approval の auto モード テスト."""
    print("=" * 70)
    print("Test: get_user_approval (auto mode)")
    print("=" * 70)
    
    ctx = ToolContext(tool_name="bash", tool_args={"command": "rm -rf /"})
    
    # auto モードではユーザー入力なしで承認
    result = get_user_approval(ctx, hitl_mode="auto")
    assert result is True
    assert ctx.is_approved()
    print("✓ Auto mode approval OK (no user input)")
    
    print()


def test_get_user_approval_interactive_prompts_in_terminal_mode(monkeypatch):
    """interactive モードでは、CI 判定が無効なら確認プロンプトを出すべき."""
    ctx = ToolContext(tool_name="bash", tool_args={"command": "echo hello"})

    class FakeStdin:
        @staticmethod
        def isatty():
            return False

    entered = []

    def fake_input(prompt_text=""):
        entered.append(prompt_text)
        return "y"

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "")
    monkeypatch.setenv("CI", "")
    monkeypatch.setattr(sys, "stdin", FakeStdin())
    monkeypatch.setattr("builtins.input", fake_input)

    result = get_user_approval(ctx, hitl_mode="interactive")

    assert result is True
    assert ctx.is_approved()
    assert entered, "interactive モードでは input() が呼ばれるべき"


if __name__ == "__main__":
    try:
        test_hitl_prompt_initialization()
        test_classification_text()
        test_tool_info_display()
        test_tool_details_display()
        test_approval_notification()
        test_get_user_approval_auto_mode()
        
        print("=" * 70)
        print("✓✓✓ All tests PASSED ✓✓✓")
        print("=" * 70)
        print()
        print("Note: Interactive tests (input prompts) require manual testing:")
        print("  - display_approval_prompt() with [Y/n/?] input")
        print("  - prompt_for_approval_with_details() with ? details loop")
    except AssertionError as e:
        print(f"✗ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

