#!/usr/bin/env python
"""file_editor の差分更新機能テスト"""
import sys
sys.path.insert(0, 'src')

from kraft.tools.file_editor_wrapper import file_editor

def test_diff_update():
    """差分更新機能（edit_line, edit_range, edit_regex）のテスト"""
    print("=" * 70)
    print("file_editor 差分更新機能テスト")
    print("=" * 70)
    print()
    
    test_file = "test_diff_update.txt"
    
    # Test 1: テストファイル作成
    print("Test 1: テストファイル作成")
    print("-" * 70)
    content = """Line 1: First line
Line 2: Second line
Line 3: Third line
Line 4: Fourth line
Line 5: Fifth line"""
    
    operation = f'create {test_file} with {content}'
    result = file_editor(operation)
    print(f"操作: create {test_file}")
    print(f"結果: {result}")
    assert "✓" in result
    print()
    
    # Test 2: 行単位編集（edit_line）
    print("Test 2: 行単位編集（edit_line）")
    print("-" * 70)
    operation = f'edit_line {test_file} 3 with Line 3: MODIFIED - Third line'
    result = file_editor(operation)
    print(f"操作: {operation}")
    print(f"結果: {result}")
    assert "✓" in result
    
    # 確認
    operation = f'view {test_file}'
    result = file_editor(operation)
    print(f"ファイル内容:\n{result}")
    assert "MODIFIED" in result
    print()
    
    # Test 3: 行範囲編集（edit_range）
    print("Test 3: 行範囲編集（edit_range）")
    print("-" * 70)
    operation = f'edit_range {test_file} 2-4 with [LINES 2-4 REPLACED]'
    result = file_editor(operation)
    print(f"操作: {operation}")
    print(f"結果: {result}")
    assert "✓" in result
    
    # 確認
    operation = f'view {test_file}'
    result = file_editor(operation)
    print(f"ファイル内容:\n{result}")
    assert "LINES 2-4 REPLACED" in result
    print()
    
    # Test 4: テストファイル再作成（正規表現テスト用）
    print("Test 4: テストファイル再作成（正規表現テスト用）")
    print("-" * 70)
    content = """ERROR: Something went wrong at 10:00
INFO: Process started at 10:01
ERROR: Another error at 10:02
DEBUG: Checking status at 10:03
ERROR: Critical error at 10:04"""
    
    operation = f'create {test_file} with {content}'
    result = file_editor(operation)
    print(f"操作: create {test_file}（ログファイル）")
    assert "✓" in result
    print()
    
    # Test 5: 正規表現置換（edit_regex）
    print("Test 5: 正規表現置換（edit_regex）")
    print("-" * 70)
    operation = f'edit_regex {test_file} with ERROR:.* -> ERROR: [REDACTED]'
    result = file_editor(operation)
    print(f"操作: {operation}")
    print(f"結果: {result}")
    assert "✓" in result
    
    # 確認
    operation = f'view {test_file}'
    result = file_editor(operation)
    print(f"ファイル内容:\n{result}")
    assert "[REDACTED]" in result
    print()
    
    # Test 6: クリーンアップ
    print("Test 6: クリーンアップ")
    print("-" * 70)
    operation = f'delete {test_file}'
    result = file_editor(operation)
    print(f"操作: delete {test_file}")
    print(f"結果: {result}")
    assert "✓" in result
    print()
    
    print("=" * 70)
    print("✓ すべてのテストが成功しました！")
    print("=" * 70)
    print()
    print("差分更新機能の利点:")
    print("  - edit_line: 特定行のみ更新 → トークン効率化")
    print("  - edit_range: 複数行一括更新 → 複雑な変更を効率化")
    print("  - edit_regex: パターンマッチング → 全体書き換え回避")
    print()

if __name__ == "__main__":
    try:
        test_diff_update()
    except AssertionError as e:
        print(f"✗ テスト失敗: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

