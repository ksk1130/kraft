#!/usr/bin/env python
"""file_editor_wrapper のテスト - 直接実装版（Windows パス対応）"""
import sys
import os
sys.path.insert(0, 'src')

from pathlib import Path
from kraft.tools.file_editor_wrapper import file_editor

def test_file_editor():
    """file_editor ツールの動作テスト"""
    print("=" * 70)
    print("file_editor 直接実装版テスト")
    print("=" * 70)
    print()
    
    test_file = "test_editor_file.md"
    
    # Test 1: create
    print("Test 1: create コマンド")
    print("-" * 70)
    operation = f'create {test_file} with # Test File\n\nThis is a test file.'
    print(f"操作: {operation}")
    result = file_editor(operation)
    print(f"結果: {result}")
    assert "✓" in result, "create に失敗"
    print()
    
    # Test 2: view
    print("Test 2: view コマンド")
    print("-" * 70)
    operation = f'view {test_file}'
    print(f"操作: {operation}")
    result = file_editor(operation)
    print(f"結果: {result}")
    assert "Test File" in result, "view に失敗"
    print()
    
    # Test 3: edit
    print("Test 3: edit コマンド")
    print("-" * 70)
    operation = f'edit {test_file} with This is a test file. -> This is a modified file.'
    print(f"操作: {operation}")
    result = file_editor(operation)
    print(f"結果: {result}")
    assert "✓" in result, "edit に失敗"
    assert "差分" in result, "差分表示が含まれていない"
    assert "---" in result and "+++" in result and "@@" in result, "unified diff 形式になっていない"
    assert "\x1b[31m" in result and "\x1b[32m" in result, "差分の色付けがされていない"
    assert "side-by-side preview" not in result, "side-by-side プレビューが残っている"
    
    # 編集結果を確認
    operation = f'view {test_file}'
    result = file_editor(operation)
    assert "modified" in result, "edit 結果が反映されていない"
    print()
    
    # Test 4: delete
    print("Test 4: delete コマンド")
    print("-" * 70)
    operation = f'delete {test_file}'
    print(f"操作: {operation}")
    result = file_editor(operation)
    print(f"結果: {result}")
    assert "✓" in result, "delete に失敗"
    print()
    
    # Test 5: 先頭スラッシュのワークスペース相対パス
    print("Test 5: 先頭スラッシュのワークスペース相対パス")
    print("-" * 70)
    os.environ["KRAFT_WORKSPACE_ROOT"] = str(Path.cwd())
    workspace_relative = "/test_workspace_relative.txt"
    operation = f'create {workspace_relative} with workspace relative path test'
    print(f"操作: {operation}")
    result = file_editor(operation)
    print(f"結果: {result}")
    assert "✓" in result, "先頭スラッシュの create に失敗"
    assert str(Path.cwd() / "test_workspace_relative.txt") in result, "ワークスペース配下に解決されていない"

    operation = f'delete {workspace_relative}'
    result = file_editor(operation)
    assert "✓" in result, "先頭スラッシュの delete に失敗"
    print()

    # Test 6: Windows パスでのテスト
    print("Test 6: Windows パスでのテスト")
    print("-" * 70)
    # 相対パスを絶対パスに変換
    abs_path = os.path.abspath("test_win_path.txt")
    operation = f'create {abs_path} with Windows path test'
    print(f"操作: {operation}")
    result = file_editor(operation)
    print(f"結果: {result}")
    assert "✓" in result, "Windows パス create に失敗"
    
    # クリーンアップ
    operation = f'delete {abs_path}'
    result = file_editor(operation)
    assert "✓" in result, "Windows パス delete に失敗"
    print()
    
    print("=" * 70)
    print("✓ すべてのテストが成功しました！")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_file_editor()
    except AssertionError as e:
        print(f"✗ テスト失敗: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

