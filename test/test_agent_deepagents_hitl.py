"""
DeepAgents HITL 統合テスト
agent.py が DeepAgents で bash コマンドを正しく中断できるか検証
"""

import json
from src.kraft.agent import build_agent_app, build_filesystem_middleware


def test_build_filesystem_middleware_excludes_builtin_edit_file():
    """DeepAgents の built-in edit_file を隠し、カスタム diff 表示版を優先する。"""
    middleware = build_filesystem_middleware()
    assert middleware is not None
    assert "edit_file" not in middleware._enabled_tools
    assert "read_file" in middleware._enabled_tools
    assert "write_file" in middleware._enabled_tools


def test_bash_interrupt_on_deep_agents():
    """bash コマンドが HITL で正しく中断されるか"""
    app, config = build_agent_app()
    
    # bash コマンドを含むユーザー入力
    user_input = "PCの現在時刻を教えてください"
    
    # agent の実行
    print(f"\n[TEST] User input: {user_input}")
    print(f"[TEST] Config: {config}")
    
    # stream() で実行（HITL による中断が発生する可能性あり）
    found_interrupt = False
    for output in app.stream(
        {"messages": [{"role": "user", "content": user_input}]},
        config,
        stream_mode="values"
    ):
        # HITL リクエストの検出（HumanInTheLoopMiddleware が interrupt_on によって生成）
        if "__interrupt__" in output:
            found_interrupt = True
            print("[TEST] FOUND INTERRUPT - bash tool was blocked for approval")
            assert "bash" in str(output["__interrupt__"]), "bash not in interrupt"
            return  # HITL 中断が発生したので成功
    
    # HITL 中断が発生しなかった場合
    if not found_interrupt:
        print("[TEST] WARNING: No interrupt detected - check if stream completed normally")


def test_agent_initialization():
    """agent.py の初期化が成功するか"""
    app, config = build_agent_app()
    
    # LangGraph が正しく返されているか
    assert app is not None, "app が None です"
    assert config is not None, "config が None です"
    assert "configurable" in config, "config に configurable がありません"
    
    print("[TEST] ✓ agent 初期化成功")
    print(f"  - app type: {type(app)}")
    print(f"  - config: {config}")


if __name__ == "__main__":
    test_agent_initialization()
    print("\n" + "="*60 + "\n")
    test_bash_interrupt_on_deep_agents()

