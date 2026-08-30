"""Human in the Loop (HITL) ツール承認モジュール.

ツール実行前にユーザーの承認を得るための機能を提供.
"""

from .tool_approval import ToolApprovalGate, ToolContext, ToolApprovalStatus
from .tool_config import SAFE_TOOLS, DANGEROUS_TOOLS, REQUIRES_CONFIRMATION
from .hitl_prompt import HITLPrompt, get_user_approval

__all__ = [
    "ToolApprovalGate",
    "ToolContext",
    "ToolApprovalStatus",
    "SAFE_TOOLS",
    "DANGEROUS_TOOLS",
    "REQUIRES_CONFIRMATION",
    "HITLPrompt",
    "get_user_approval",
]
