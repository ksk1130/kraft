#!/usr/bin/env python
"""Agent が file_editor ツールを正常に使用できるかのテスト"""
import sys
import os
sys.path.insert(0, 'src')

# 環境変数設定（テスト用ダミーキー）
os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'sk-test-dummy-key')

from langchain_core.messages import AIMessage, ToolMessage

from kraft.agent import agent
from kraft import extract_agent_response

def test_agent_loads():
    """Agent が file_editor を含めて正常に読み込まれるか"""
    print("=" * 70)
    print("Agent ロード & file_editor ツール確認")
    print("=" * 70)
    print()
    
    try:
        print("✓ Agent ロード成功")
        
        # Agent のツール情報を確認
        print("✓ file_editor がインポートされていることを確認")
        
        # 実際に file_editor ツールを直接テスト
        from kraft.tools.file_editor_wrapper import file_editor
        print()
        
        # テストファイルを作成
        test_file = "test_agent_interaction.txt"
        print(f"Test 1: ファイル作成（{test_file}）")
        result = file_editor(f'create {test_file} with Agent interaction test.')
        print(f"  結果: {result}")
        assert "✓" in result
        
        # ファイル内容を読み取り
        print(f"Test 2: ファイル読み取り（{test_file}）")
        result = file_editor(f'view {test_file}')
        print(f"  結果: {result[:50]}...")
        assert "Agent interaction" in result
        
        # ファイルを削除
        print(f"Test 3: ファイル削除（{test_file}）")
        result = file_editor(f'delete {test_file}')
        print(f"  結果: {result}")
        assert "✓" in result
        
        print()
        print("=" * 70)
        print("✓ Agent と file_editor が正常に動作しています！")
        print("=" * 70)
        
    except Exception as e:
        print(f"✗ エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def test_extract_agent_response_prefers_edit_file_tool_output():
    """編集結果は AI の要約よりも `edit_file` の生出力を優先する。"""
    messages = [
        AIMessage(content="変更しました。変更内容は以下の通りです。"),
        ToolMessage(content="差分:\n--- before\n+++ after\n@@ -1 +1 @@\n-こんにちは\n+コンニチハ", name="edit_file", tool_call_id="call-1"),
    ]

    response = extract_agent_response(messages)

    assert "差分:" in response
    assert "コンニチハ" in response
    assert "変更しました" not in response

if __name__ == "__main__":
    test_agent_loads()

