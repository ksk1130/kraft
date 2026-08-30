#!/usr/bin/env python
"""HITL tool_approval モジュールのテスト."""
import sys
sys.path.insert(0, "src")

from kraft.approval import ToolApprovalGate, ToolContext, SAFE_TOOLS, DANGEROUS_TOOLS


def test_tool_context():
    """ToolContext のテスト."""
    print("=" * 70)
    print("Test: ToolContext")
    print("=" * 70)
    
    # Safe tool
    ctx = ToolContext(
        tool_name="calculator",
        tool_args={"a": 10, "b": 20, "operation": "add"},
        tool_description="Simple calculator"
    )
    assert ctx.is_safe()
    assert not ctx.is_dangerous()
    assert not ctx.requires_confirmation()
    print("✓ Safe tool classification OK")
    
    # Dangerous tool
    ctx2 = ToolContext(
        tool_name="bash",
        tool_args={"command": "rm -rf /"},
        tool_description="Execute bash command"
    )
    assert not ctx2.is_safe()
    assert ctx2.is_dangerous()
    assert ctx2.requires_confirmation()
    print("✓ Dangerous tool classification OK")
    
    # Requires confirmation
    ctx3 = ToolContext(
        tool_name="grep_search",
        tool_args={"query": "password", "isRegexp": True},
        tool_description="Search in workspace"
    )
    assert not ctx3.is_safe()
    assert not ctx3.is_dangerous()
    assert ctx3.requires_confirmation()
    print("✓ Requires confirmation tool classification OK")
    
    # Auto approve if safe
    assert ctx.auto_approve_if_safe()
    assert ctx.is_approved()
    print("✓ Auto approval for safe tools OK")
    
    # Manual approval
    ctx2.approve()
    assert ctx2.is_approved()
    assert ctx2.user_choice == "y"
    print("✓ Manual approval OK")
    
    # Skip
    ctx3.skip()
    assert not ctx3.is_approved()
    assert ctx3.user_choice == "n"
    print("✓ Skip OK")
    
    # Format args display
    display = ctx2.format_args_display()
    assert "command" in display
    assert "rm -rf /" in display
    print(f"✓ Format args display OK:\n{display}")
    print()


def test_tool_approval_gate_interactive():
    """ToolApprovalGate の対話モード テスト."""
    print("=" * 70)
    print("Test: ToolApprovalGate (interactive mode)")
    print("=" * 70)
    
    gate = ToolApprovalGate(hitl_mode="interactive")
    
    # Safe tool: should not require approval
    ctx1 = gate.create_context("calculator", {"a": 5, "b": 3})
    assert not gate.should_require_approval("calculator")
    assert gate.evaluate(ctx1)
    assert ctx1.is_approved()
    print("✓ Safe tool auto-approved in interactive mode")
    
    # Dangerous tool: should require approval
    ctx2 = gate.create_context("bash", {"command": "ls"})
    assert gate.should_require_approval("bash")
    assert not gate.evaluate(ctx2)
    assert not ctx2.is_approved()
    print("✓ Dangerous tool requires approval in interactive mode")
    
    # Pending tools
    pending = gate.get_pending_tools()
    assert len(pending) == 1
    assert pending[0].tool_name == "bash"
    print(f"✓ Pending tools count: {len(pending)}")
    
    # Approve pending tool
    ctx2.approve()
    assert gate.evaluate(ctx2)
    assert ctx2.is_approved()
    print("✓ Pending tool approved manually")
    print()


def test_tool_approval_gate_auto():
    """ToolApprovalGate の自動モード テスト."""
    print("=" * 70)
    print("Test: ToolApprovalGate (auto mode)")
    print("=" * 70)
    
    gate = ToolApprovalGate(hitl_mode="auto")
    
    # Dangerous tool: should still be approved in auto mode
    ctx = gate.create_context("bash", {"command": "rm -rf /"})
    assert not gate.should_require_approval("bash")
    assert gate.evaluate(ctx)
    assert ctx.is_approved()
    print("✓ Dangerous tool auto-approved in auto mode")
    
    # No pending tools
    assert len(gate.get_pending_tools()) == 0
    print("✓ No pending tools in auto mode")
    print()


def test_tool_approval_gate_strict():
    """ToolApprovalGate の strict モード テスト."""
    print("=" * 70)
    print("Test: ToolApprovalGate (strict mode)")
    print("=" * 70)
    
    gate = ToolApprovalGate(hitl_mode="strict")
    
    # Even safe tool: should require approval in strict mode
    ctx = gate.create_context("calculator", {"a": 5, "b": 3})
    assert gate.should_require_approval("calculator")
    assert not gate.evaluate(ctx)
    print("✓ Safe tool requires approval in strict mode")
    
    # Pending tools
    assert len(gate.get_pending_tools()) == 1
    print("✓ Safe tool added to pending in strict mode")
    print()


def test_approval_history():
    """承認履歴の記録テスト."""
    print("=" * 70)
    print("Test: Approval History")
    print("=" * 70)
    
    from kraft.approval import ToolApprovalStatus
    
    gate = ToolApprovalGate(hitl_mode="interactive")
    
    ctx = gate.create_context("bash", {"command": "pwd"})
    ctx.approve()
    
    gate.record_approval("bash", ctx.status)
    
    assert gate.approval_history["bash"] == ToolApprovalStatus.APPROVED
    print("✓ Approval history recorded")
    print()


def test_tool_config():
    """ツール分類設定のテスト."""
    print("=" * 70)
    print("Test: Tool Config Classification")
    print("=" * 70)
    
    from kraft.approval.tool_config import classify_tool, is_auto_approvable
    
    # Safe tools
    for tool in SAFE_TOOLS:
        assert classify_tool(tool) == "safe"
        assert is_auto_approvable(tool)
        print(f"✓ {tool}: safe (auto-approvable)")
    
    # Dangerous tools
    for tool in DANGEROUS_TOOLS:
        assert classify_tool(tool) == "dangerous"
        assert not is_auto_approvable(tool)
        print(f"✓ {tool}: dangerous")
    
    print()


if __name__ == "__main__":
    try:
        test_tool_context()
        test_tool_approval_gate_interactive()
        test_tool_approval_gate_auto()
        test_tool_approval_gate_strict()
        test_approval_history()
        test_tool_config()
        
        print("=" * 70)
        print("✓✓✓ All tests PASSED ✓✓✓")
        print("=" * 70)
    except AssertionError as e:
        print(f"✗ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

