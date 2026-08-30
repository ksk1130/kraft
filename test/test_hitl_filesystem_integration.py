"""
FilesystemBackend と HITL 統合テスト
エージェントがファイル操作時に HITL で中断し、承認フロー完結を検証
"""

import os
import json
from pathlib import Path
from src.kraft.agent import build_agent_app, WORKSPACE_DIR
from langgraph.types import Command


def test_hitl_file_operation_detection():
    """ファイル操作が HITL で中断されるか検証"""
    
    app, config = build_agent_app()
    
    # テスト用メッセージ: ファイル作成を指示
    messages_history = [
        {"role": "user", "content": "config.txt というファイルを作成して、『今後のAIトレンド』について書いてください。"}
    ]
    
    print("\n=== HITL File Operation Test ===\n")
    print(f"[1] Sending instruction to agent...")
    print(f"    Workspace: {WORKSPACE_DIR}")
    print(f"    User: {messages_history[0]['content']}\n")
    
    # ターン1: エージェント実行（ファイル操作で中断予定）
    last_output = None
    for output in app.stream(
        {"messages": messages_history},
        config,
        stream_mode="values"
    ):
        last_output = output
    
    # HITL 中断確認
    state = app.get_state(config)
    
    if state.next:
        print(f"[✓] HITL Interrupt detected!")
        print(f"    Next step: {state.next}")
        
        # ペンディングタスク情報を取得
        if hasattr(state, 'tasks') and state.tasks:
            pending_task = state.tasks[0] if isinstance(state.tasks, list) else state.tasks
            tool_name = getattr(pending_task, 'name', 'unknown')
            tool_args = getattr(pending_task, 'args', {})
            tool_id = getattr(pending_task, 'id', 'unknown_id')
            
            print(f"\n[2] Pending tool info:")
            print(f"    Tool: {tool_name}")
            print(f"    Args: {tool_args}")
            print(f"    ID: {tool_id}")
            
            # ターン2: 承認決定を構成（LangChain HumanInTheLoopMiddleware フォーマット）
            print(f"\n[3] Constructing approval decision...")
            # decisions は配列で、各要素が { "type": "approve|reject|edit|respond", ... }
            decisions = [{"type": "approve"}]  # 承認
            print(f"    Decision: APPROVE")
            
            # ターン3: resume で再開（decisions キーで wrapped）
            print(f"\n[4] Resuming execution...\n")
            final_output = None
            for resume_output in app.stream(
                Command(resume={"decisions": decisions}),
                config,
                stream_mode="values"
            ):
                final_output = resume_output
            
            print(f"[✓] Resume completed!")
            
            # ファイルが実際に作成されたか確認
            target_file = Path(WORKSPACE_DIR) / "config.txt"
            if target_file.exists():
                print(f"\n[5] File creation verification:")
                print(f"    ✓ File exists: {target_file}")
                with open(target_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    print(f"    Content preview: {content[:100]}...")
                assert target_file.exists()
                return
            else:
                print(f"\n[!] File was not created at: {target_file}")
                assert False, f"File was not created at: {target_file}"
        else:
            print("[!] Could not retrieve pending task details")
            assert hasattr(state, 'tasks') and state.tasks, "Could not retrieve pending task details"
    else:
        print("[!] No HITL interrupt detected (state.next is empty)")
        print(f"    State: {state}")
        assert state.next, "No HITL interrupt detected"


def test_hitl_rejection():
    """ファイル操作を却下する HITL フロー"""
    
    app, config = build_agent_app()
    
    messages_history = [
        {"role": "user", "content": "reject_test.txt というファイルを作成してください。"}
    ]
    
    print("\n=== HITL Rejection Test ===\n")
    
    # ターン1: 実行
    for output in app.stream(
        {"messages": messages_history},
        config,
        stream_mode="values"
    ):
        pass
    
    # 中断確認
    state = app.get_state(config)
    
    if state.next and hasattr(state, 'tasks') and state.tasks:
        pending_task = state.tasks[0] if isinstance(state.tasks, list) else state.tasks
        tool_id = getattr(pending_task, 'id', 'unknown_id')
        
        print(f"[1] Pending tool: {getattr(pending_task, 'name', 'unknown')}")
        print(f"[2] Sending REJECT decision...\n")
        
        # 却下決定（LangChain HumanInTheLoopMiddleware フォーマット）
        decisions = [{"type": "reject", "message": "User rejected this operation"}]  # 却下
        
        # resume
        for resume_output in app.stream(
            Command(resume={"decisions": decisions}),
            config,
            stream_mode="values"
        ):
            pass
        
        # ファイルが作成されていないことを確認
        target_file = Path(WORKSPACE_DIR) / "reject_test.txt"
        if not target_file.exists():
            print(f"[✓] File was NOT created (as expected)")
            assert not target_file.exists()
            return
        else:
            print(f"[!] File was created despite rejection: {target_file}")
            assert not target_file.exists(), f"File was created despite rejection: {target_file}"
    else:
        print("[!] No HITL interrupt detected")
        assert state.next and hasattr(state, 'tasks') and state.tasks, "No HITL interrupt detected"


if __name__ == "__main__":
    try:
        # テスト1: 承認フロー
        result1 = test_hitl_file_operation_detection()
        
        # テスト2: 却下フロー
        result2 = test_hitl_rejection()
        
        print("\n" + "="*50)
        print(f"Test Results:")
        print(f"  Approval Flow: {'✓ PASS' if result1 else '✗ FAIL'}")
        print(f"  Rejection Flow: {'✓ PASS' if result2 else '✗ FAIL'}")
        print("="*50)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

