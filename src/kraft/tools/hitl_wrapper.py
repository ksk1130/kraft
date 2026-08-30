"""Tool Call に HITL ゲートを追加するラッパー実装.

各ツール関数を HITL ゲートでラップし、実行前にユーザー承認を取得.
"""

import os
from typing import Any, Callable
from functools import wraps

from kraft.approval import (
    ToolContext,
    ToolApprovalGate,
    get_user_approval,
)


# グローバル HITL mode（環境変数から読み込み）
HITL_MODE = os.getenv("KRAFT_HITL_MODE", "interactive").lower()

# グローバル承認ゲート
_approval_gate = ToolApprovalGate(hitl_mode=HITL_MODE)


def apply_hitl_gate(
    tool_name: str,
    tool_description: str = "",
) -> Callable:
    """Tool 関数に HITL ゲートを適用するデコレータ.
    
    Args:
        tool_name: ツール名
        tool_description: ツール説明
        
    Returns:
        デコレータ関数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # auto モード: ゲートを通さず直接実行
            if HITL_MODE == "auto":
                return func(*args, **kwargs)
            
            # interactive/strict モード: ゲートを通す
            context = ToolContext(
                tool_name=tool_name,
                tool_args=_format_args(args, kwargs),
                tool_description=tool_description,
            )
            
            # 承認ゲートで分類・自動承認判定
            if not _approval_gate.should_require_approval(context):
                # SAFE ツール: 自動実行
                return func(*args, **kwargs)
            
            # 承認が必要: ユーザーに確認
            approved = get_user_approval(
                context,
                hitl_mode=HITL_MODE,
                timeout_seconds=30,
            )
            
            if approved:
                # 承認されたら実行
                return func(*args, **kwargs)
            else:
                # スキップされたら実行しない
                return f"[SKIPPED] {tool_name} 実行がスキップされました。"
        
        return wrapper
    return decorator


def _format_args(args: tuple, kwargs: dict) -> dict:
    """引数をフォーマットして辞書に変換.
    
    Args:
        args: 位置引数
        kwargs: キーワード引数
        
    Returns:
        フォーマット済みの引数辞書
    """
    result = {}
    
    # 位置引数をジェネリック名で記録
    for i, arg in enumerate(args):
        result[f"arg{i}"] = arg
    
    # キーワード引数を記録
    result.update(kwargs)
    
    return result


def set_hitl_mode(mode: str) -> None:
    """HITL モードを設定（動的に変更）.
    
    Args:
        mode: "auto", "interactive", "strict"
    """
    global HITL_MODE, _approval_gate
    HITL_MODE = mode.lower()
    _approval_gate = ToolApprovalGate(hitl_mode=HITL_MODE)


def get_hitl_mode() -> str:
    """現在の HITL モードを取得.
    
    Returns:
        HITL モード
    """
    return HITL_MODE


def get_approval_gate() -> ToolApprovalGate:
    """グローバル承認ゲートを取得.
    
    Returns:
        ToolApprovalGate インスタンス
    """
    return _approval_gate

