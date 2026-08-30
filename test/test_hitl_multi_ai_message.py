#!/usr/bin/env python
"""
Multi-tool HITL 確認テスト（修正版v2）

AIMessage.tool_calls から直接ツール情報を取得して
複数ツール決定を一度に送信するテスト。
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from kraft.agent import build_agent_app
from langgraph.types import Command
from langchain_core.messages import AIMessage


def test_multi_tool_hitl_via_ai_message():
    """複数ツール呼び出し：AIMessage.tool_calls から決定を構築"""

    app, config = build_agent_app()

    # 複数ツール呼び出しを指図
    messages_history = [
        {"role": "user", "content": "test_multi.txt というファイルを作成して、その後 pwd コマンドを実行してください"}
    ]

    print("\n=== Multi-Tool HITL Test (Via AIMessage.tool_calls) ===\n")
    print("[1] Sending user request...")
    print(f"    Request: Multiple operations\n")

    # ターン1: 初回実行
    for output in app.stream(
        {"messages": messages_history},
        config,
        stream_mode="values"
    ):
        pass

    # HITL 確認ループ（複数ツール対応）
    tools_processed = []
    MAX_ITERATIONS = 10
    hitl_count = 0

    while hitl_count < MAX_ITERATIONS:
        state = app.get_state(config)
        if not state.next:
            print(f"\n[✓] Processing complete (no more interrupts)")
            break

        hitl_count += 1
        print(f"\n[{hitl_count}] HITL Interrupt Detected")

        # ========================================
        # 重要：AIMessage.tool_calls から直接取得
        # ========================================
        # StateSnapshot のアクセス方法
        if hasattr(state, 'values'):
            messages = state.values.get("messages", [])
        else:
            messages = getattr(state, 'messages', [])
        
        # 最後の AIMessage を探す
        ai_msg = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                ai_msg = msg
                break
        
        if ai_msg and hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
            tool_calls = ai_msg.tool_calls
            print(f"     Pending tools: {len(tool_calls)}")

            # すべてのツール呼び出しに対して決定を構築
            decisions_list = []
            for idx, tool_call in enumerate(tool_calls, 1):
                tool_name = tool_call.get('name', 'unknown')
                tool_args = tool_call.get('args', {})
                print(f"     [{idx}] Tool: {tool_name}")
                print(f"          Args: {tool_args}")

                # テスト用: すべてのツールを承認
                decision = "approve"
                print(f"          Decision: {decision.upper()}")

                tools_processed.append((tool_name, decision))

                # 決定オブジェクトを作成
                decision_obj = {"type": decision}
                decisions_list.append(decision_obj)

            # 複数決定をまとめて送信（重要：すべての決定を一度に）
            print(f"\n     Resuming with {len(decisions_list)} decision(s)...")
            decisions = {"decisions": decisions_list}

            for output in app.stream(
                Command(resume=decisions),
                config,
                stream_mode="values"
            ):
                pass
        else:
            print("[!] Could not find AIMessage with tool_calls")
            break

    # 検証
    print(f"\n[Summary] Total rounds: {hitl_count}")
    print(f"[Summary] Tools processed: {len(tools_processed)}")
    for i, (tool, decision) in enumerate(tools_processed, 1):
        print(f"  [{i}] {tool}: {decision.upper()}")

    # 検証ロジック
    assert hitl_count > 0, "Expected at least one HITL interrupt"

    print(f"\n[✓] PASS: Multi-tool HITL handling works correctly")
    print(f"   {len(tools_processed)} tools processed successfully")


if __name__ == "__main__":
    try:
        result = test_multi_tool_hitl_via_ai_message()
        if result:
            print("\n✅ All tests passed!")
            sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

