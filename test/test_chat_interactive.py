#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""対話型 Agent チャットの簡単なシミュレーション"""
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

def main():
    """対話型チャットシミュレーション"""
    print("=" * 70)
    print("対話型 Agent チャット - Guided Tour")
    print("=" * 70)
    print()
    
    display_welcome()
    print()
    
    # テスト用メッセージ（対話的に拡張可能）
    test_messages = [
        "What is the current time?",
        "Show me your skills",
    ]
    
    for i, msg in enumerate(test_messages, 1):
        print(f"\n[Message {i}/{len(test_messages)}]")
        print(f"User: {msg}")
        print("-" * 70)
        
        try:
            result = agent(msg)
            
            # Response processing
            if isinstance(result, dict):
                response_text = result.get("text", str(result))
            else:
                response_text = str(result)
            
            print(f"Agent: {response_text[:500]}")
            if len(response_text) > 500:
                print("  [... response truncated for display ...]")
            
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")
        
        print()
    
    print("=" * 70)
    print("Chat simulation completed")
    print("=" * 70)
    
    # Interactive mode (optional)
    print()
    print("Entering interactive mode (type 'exit' to quit):")
    print("-" * 70)
    
    try:
        while True:
            user_input = input("User: ").strip()
            if user_input.lower() in ('exit', 'quit'):
                break
            
            if not user_input:
                continue
            
            try:
                result = agent(user_input)
                
                if isinstance(result, dict):
                    response_text = result.get("text", str(result))
                else:
                    response_text = str(result)
                
                print(f"Agent: {response_text}")
                
            except KeyboardInterrupt:
                print("\n[Interrupted]")
                break
            except Exception as e:
                print(f"Error: {type(e).__name__}: {e}")
            
            print()
    
    except (EOFError, KeyboardInterrupt):
        print("\n[Chat ended]")

if __name__ == "__main__":
    main()

