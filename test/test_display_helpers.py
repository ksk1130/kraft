#!/usr/bin/env python
"""TODO 4: 追加の表示ヘルパーのテスト."""

import sys
from pathlib import Path
import time

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from kraft.display_formatter import (
    console,
    display_tool_execution_start,
    display_tool_execution_end,
    display_spinner,
    display_progress_bar,
    display_results_table,
)


def test_tool_execution_display():
    """ツール実行開始・終了の表示テスト."""
    print("\n=== ツール実行表示テスト ===\n")
    
    # 成功パターン
    display_tool_execution_start("grep_search")
    time.sleep(0.5)
    display_tool_execution_end("grep_search", success=True, duration_ms=487.3)
    
    print()
    
    # 失敗パターン
    display_tool_execution_start("file_read")
    time.sleep(0.3)
    display_tool_execution_end("file_read", success=False, duration_ms=125.5)


def test_spinner_display():
    """スピナー表示テスト."""
    print("\n=== スピナー表示テスト ===\n")
    
    messages = [
        "ファイルを読み込み中",
        "データを処理中",
        "結果を保存中",
    ]
    
    for msg in messages:
        with display_spinner(msg):
            time.sleep(1.5)
    
    print("✓ スピナーテスト完了\n")


def test_progress_bar_display():
    """プログレスバー表示テスト."""
    print("\n=== プログレスバー表示テスト ===\n")
    
    files = ["file1.txt", "file2.txt", "file3.txt", "file4.txt", "file5.txt"]
    
    for file in display_progress_bar(files, "ファイル処理中"):
        time.sleep(0.3)
    
    print("✓ プログレスバーテスト完了\n")


def test_results_table_display():
    """結果テーブル表示テスト."""
    print("\n=== 結果テーブル表示テスト ===\n")
    
    # テスト用データ
    search_results = [
        {"ファイル": "config.json", "行番号": 42, "内容": 'api_key = "secret"'},
        {"ファイル": "settings.json", "行番号": 15, "内容": '"timeout": 30'},
        {"ファイル": "data.json", "行番号": 8, "内容": '"version": "1.0"'},
    ]
    
    display_results_table(
        search_results,
        columns=["ファイル", "行番号", "内容"],
        title="grep 検索結果",
        style="yellow"
    )
    
    # 空データのテスト
    print("空データのテスト:")
    display_results_table([], title="結果なし", style="red")


def test_all():
    """すべてのテストを実行."""
    print("\n" + "="*50)
    print("TODO 4: 追加の表示ヘルパー テストスイート")
    print("="*50)
    
    test_tool_execution_display()
    test_spinner_display()
    test_progress_bar_display()
    test_results_table_display()
    
    print("\n" + "="*50)
    print("✓ すべてのテストが完了しました")
    print("="*50 + "\n")


if __name__ == "__main__":
    test_all()

