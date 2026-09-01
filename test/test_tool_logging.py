#!/usr/bin/env python
"""tool_logging の強化版をテストするスクリプト."""

import subprocess
import sys
from pathlib import Path
import time

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from kraft.agent import bash
from kraft.tools.tool_logging import (
    log_tool_start,
    log_tool_success,
    log_tool_error,
    tool_logging_hook,
)


def test_basic_logging():
    """基本的なログ関数をテスト."""
    print("\n=== 基本ログ関数テスト ===\n")
    
    log_tool_start("test_tool", {"query": "example"})
    time.sleep(0.5)  # 実行時間をシミュレート
    log_tool_success("test_tool", "dict")
    
    log_tool_start("error_tool")
    time.sleep(0.3)
    try:
        raise ValueError("テストエラー")
    except ValueError as e:
        log_tool_error("error_tool", e, include_trace=False)


@tool_logging_hook(tool_name="decorated_func", include_kwargs=("value",))
def decorated_example(value: str) -> str:
    """デコレータでラップされた関数の例."""
    time.sleep(0.4)  # 実行時間をシミュレート
    return f"Result: {value}"


@tool_logging_hook(tool_name="error_func")
def error_example() -> None:
    """エラーを発生させる関数の例."""
    time.sleep(0.2)
    raise RuntimeError("デコレータ経由のエラー")


def test_decorator():
    """tool_logging_hook デコレータをテスト."""
    print("\n=== デコレータテスト ===\n")
    
    # 成功する関数
    result = decorated_example(value="test123")
    print(f"  戻り値: {result}\n")
    
    # エラーが発生する関数
    try:
        error_example()
    except RuntimeError:
        pass


def test_bash_streams_output_to_terminal(monkeypatch, capsys):
    """bash は実行中の出力を表示し、最終結果も返す。"""

    class FakeStdout:
        def __init__(self, lines):
            self._lines = iter(lines)

        def readline(self):
            try:
                return next(self._lines)
            except StopIteration:
                return ""

    class FakeProcess:
        def __init__(self, *args, **kwargs):
            self.stdout = FakeStdout(["hello\n", "world\n"])

        def poll(self):
            return 0

        def wait(self):
            return 0

        def kill(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    result = bash("echo hello && echo world", shell="powershell")
    captured = capsys.readouterr()

    assert "echo hello && echo world" in captured.out
    assert "hello" in captured.out
    assert "world" in captured.out
    assert result == "hello\nworld"


def test_bash_streams_output_in_chat_style(monkeypatch, capsys):
    """bash は chat 形式でも実行ログを会話っぽく出力できる。"""

    class FakeStdout:
        def __init__(self, lines):
            self._lines = iter(lines)

        def readline(self):
            try:
                return next(self._lines)
            except StopIteration:
                return ""

    class FakeProcess:
        def __init__(self, *args, **kwargs):
            self.stdout = FakeStdout(["first\n", "second\n"])

        def poll(self):
            return 0

        def wait(self):
            return 0

        def kill(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    result = bash("echo first && echo second", shell="powershell", stream_mode="chat")
    captured = capsys.readouterr()

    assert "echo first && echo second" in captured.out
    assert "first" in captured.out
    assert "second" in captured.out
    assert "assistant" in captured.out.lower() or "command" in captured.out.lower()
    assert result == "first\nsecond"


if __name__ == "__main__":
    test_basic_logging()
    test_decorator()
    print("\n✓ すべてのテストが完了しました")


