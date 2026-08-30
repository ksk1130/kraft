"""HITL ツール承認ゲート実装.

Tool Call を傍受して、ユーザーの承認を得てから実行する仕組み.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

from .tool_config import classify_tool, is_auto_approvable


class ToolApprovalStatus(Enum):
    """ツール承認ステータス."""
    PENDING = "pending"          # 待機中
    APPROVED = "approved"        # ユーザーが承認
    SKIPPED = "skipped"          # ユーザーがスキップ
    AUTO_APPROVED = "auto_approved"  # 自動承認（safe ツール）
    TIMED_OUT = "timed_out"      # タイムアウト


@dataclass
class ToolContext:
    """ツール実行のコンテキスト情報.
    
    Attributes:
        tool_name: ツール名（例："grep_search"）
        tool_args: ツール引数（例：{"query": "pattern", "isRegexp": True}）
        tool_description: ツール説明（システムプロンプトから取得）
        classification: ツール分類（"safe", "dangerous", "requires_confirmation"）
        status: 承認ステータス
    """
    tool_name: str
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_description: str = ""
    classification: str = field(default="")
    status: ToolApprovalStatus = field(default=ToolApprovalStatus.PENDING)
    user_choice: Optional[str] = None  # "y", "n", "?"
    
    def __post_init__(self):
        """初期化後の処理."""
        if not self.classification:
            self.classification = classify_tool(self.tool_name)
    
    def is_safe(self) -> bool:
        """安全なツール（自動承認可能）か判定."""
        return self.classification == "safe"
    
    def is_dangerous(self) -> bool:
        """危険なツール（常に確認要求）か判定."""
        return self.classification == "dangerous"
    
    def requires_confirmation(self) -> bool:
        """確認が必要か判定."""
        return self.classification in ("dangerous", "requires_confirmation")
    
    def auto_approve_if_safe(self) -> bool:
        """安全なら自動承認し、True を返す. 否なら False."""
        if is_auto_approvable(self.tool_name):
            self.status = ToolApprovalStatus.AUTO_APPROVED
            return True
        return False
    
    def approve(self) -> None:
        """ユーザーが承認した."""
        self.status = ToolApprovalStatus.APPROVED
        self.user_choice = "y"
    
    def skip(self) -> None:
        """ユーザーがスキップした."""
        self.status = ToolApprovalStatus.SKIPPED
        self.user_choice = "n"
    
    def timeout(self) -> None:
        """タイムアウト（安全側=スキップ）."""
        self.status = ToolApprovalStatus.TIMED_OUT
    
    def is_approved(self) -> bool:
        """ツール実行が許可されているか."""
        return self.status in (
            ToolApprovalStatus.APPROVED,
            ToolApprovalStatus.AUTO_APPROVED,
        )
    
    def format_args_display(self, max_value_len: int = 50) -> str:
        """ツール引数を表示用にフォーマット.
        
        Args:
            max_value_len: 値の最大表示文字数
            
        Returns:
            フォーマット済み文字列（複数行）
        """
        lines = []
        for key, value in self.tool_args.items():
            # 値の型に応じた表示
            if isinstance(value, str):
                if len(value) > max_value_len:
                    display_value = f'"{value[:max_value_len]}..."'
                else:
                    display_value = f'"{value}"'
            elif isinstance(value, bool):
                display_value = str(value)
            elif isinstance(value, (int, float)):
                display_value = str(value)
            else:
                display_value = str(value)
            
            lines.append(f"  {key}: {display_value}")
        
        return "\n".join(lines) if lines else "  (no arguments)"


class ToolApprovalGate:
    """ツール承認ゲートの管理クラス.
    
    Tool Call を傍受して、承認フロー（HITL）を制御.
    """
    
    def __init__(self, hitl_mode: str = "interactive"):
        """初期化.
        
        Args:
            hitl_mode: HITL モード
                - "interactive": 対話的（確認必要）
                - "auto": 自動実行（HITL なし）
                - "strict": 全て確認（デバッグ用）
        """
        self.hitl_mode = hitl_mode
        self.pending_tools: list[ToolContext] = []
        self.approval_history: dict[str, ToolApprovalStatus] = {}
    
    def create_context(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_description: str = "",
    ) -> ToolContext:
        """ツール実行コンテキストを作成.
        
        Args:
            tool_name: ツール名
            tool_args: ツール引数
            tool_description: ツール説明
            
        Returns:
            ToolContext インスタンス
        """
        return ToolContext(
            tool_name=tool_name,
            tool_args=tool_args,
            tool_description=tool_description,
        )
    
    def should_require_approval(self, tool_name: str | ToolContext) -> bool:
        """ツール実行前に承認が必要か判定.
        
        Args:
            tool_name: ツール名または ToolContext
            
        Returns:
            True なら承認が必要、False なら自動実行
        """
        resolved_name = tool_name.tool_name if isinstance(tool_name, ToolContext) else tool_name
        if self.hitl_mode == "auto":
            return False  # 自動実行モード
        elif self.hitl_mode == "strict":
            return True   # すべて確認
        else:  # "interactive" (デフォルト)
            return not is_auto_approvable(resolved_name)
    
    def evaluate(self, context: ToolContext) -> bool:
        """ツール実行可否を評価.
        
        Args:
            context: ToolContext インスタンス
            
        Returns:
            True なら実行許可、False なら実行スキップ
        """
        # 既に決定済みなら結果を返す
        if context.status != ToolApprovalStatus.PENDING:
            return context.is_approved()
        
        # HITL モード別の処理
        if self.hitl_mode == "auto":
            # 自動実行モード: すべて承認
            context.status = ToolApprovalStatus.AUTO_APPROVED
            return True
        
        if self.hitl_mode == "strict":
            # strict モード: すべて保留（要ユーザー入力）
            if context not in self.pending_tools:
                self.pending_tools.append(context)
            return False  # 一度は待機状態に
        
        # interactive モード（デフォルト）
        if context.auto_approve_if_safe():
            # 安全なツール → 自動承認
            return True
        
        # 危険 or 要確認 → ユーザー確認待機
        if context not in self.pending_tools:
            self.pending_tools.append(context)
        return False
    
    def get_pending_tools(self) -> list[ToolContext]:
        """承認待機中のツールリストを取得.
        
        Returns:
            ToolContext のリスト
        """
        return [t for t in self.pending_tools if t.status == ToolApprovalStatus.PENDING]
    
    def record_approval(self, tool_name: str, status: ToolApprovalStatus) -> None:
        """承認履歴を記録.
        
        Args:
            tool_name: ツール名
            status: 承認ステータス
        """
        # 同一ツール名の履歴は上書き
        self.approval_history[tool_name] = status
    
    def clear_pending(self) -> None:
        """待機中のツール一覧をクリア."""
        self.pending_tools.clear()
