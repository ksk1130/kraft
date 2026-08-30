#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Agent と file_editor の簡単な相互作用テスト"""
import sys
import os
sys.path.insert(0, 'src')

# Windows コンソールのエンコーディング対応
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    sys.stdout.reconfigure(encoding='utf-8')

os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'sk-test-dummy-key')

from kraft.agent import agent
from kraft.display_formatter import display_welcome, display_final_answer

def extract_response(result):
    """Agent result から応答テキストを抽出"""
    try:
        # result がそのまま dict
        if isinstance(result, dict):
            if "message" in result:
                msg = result["message"]
                if isinstance(msg, dict) and "content" in msg:
                    content = msg["content"]
                    if isinstance(content, list):
                        return "\n".join(str(item) for item in content)
                    return str(content)
            return str(result)
        
        # result が AgentResult オブジェクト
        if hasattr(result, 'message'):
            msg = result.message
            if isinstance(msg, dict):
                content = msg.get("content", "")
            elif hasattr(msg, 'content'):
                content = msg.content
            else:
                content = str(msg)
            
            if isinstance(content, list):
                return "\n".join(str(item) for item in content)
            return str(content)
        
        return str(result)
    except Exception as e:
        return f"[Error extracting response: {e}]"

def test_agent_interaction():
    """Agent とのインタラクション"""
    print("=" * 70)
    print("Agent インタラクションテスト")
    print("=" * 70)
    print()
    
    display_welcome()
    print()
    
    # テスト 1: ファイル作成を指示
    print("Test 1: ファイル作成テスト")
    print("-" * 70)
    test_file = "test_interaction_output.txt"
    message1 = f"Create a file called {test_file} with content: Hello from Agent!"
    print(f"Message: {message1}")
    print()
    
    try:
        result = agent(message1)
        response = extract_response(result)
        print(f"Response: {response[:300]}")
        print()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # テスト 2: ファイル読み取り
    print("Test 2: ファイル読み取りテスト")
    print("-" * 70)
    message2 = f"Read the file {test_file} and tell me its contents"
    print(f"Message: {message2}")
    print()
    
    try:
        result = agent(message2)
        response = extract_response(result)
        print(f"Response: {response[:300]}")
        print()
    except Exception as e:
        print(f"Error: {e}")
        print()
    
    # テスト 3: ファイル部分編集
    print("Test 3: ファイル部分編集テスト")
    print("-" * 70)
    message3 = f"Edit {test_file}: replace 'Hello' with 'Goodbye'"
    print(f"Message: {message3}")
    print()
    
    try:
        result = agent(message3)
        response = extract_response(result)
        print(f"Response: {response[:300]}")
        print()
    except Exception as e:
        print(f"Error: {e}")
        print()
    
    # クリーンアップ
    print("Cleanup: Delete test file")
    print("-" * 70)
    try:
        from kraft.tools.file_editor_wrapper import file_editor
        result = file_editor(f"delete {test_file}")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Cleanup error: {e}")
    
    print()
    print("=" * 70)
    print("Test completed")
    print("=" * 70)

if __name__ == "__main__":
    test_agent_interaction()

