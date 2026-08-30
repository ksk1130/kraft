"""HITL ツール分類設定.

ツールを「安全」「危険」「要確認」に分類して、承認フローを制御.
"""

# 読み取り専用・副作用なし → 自動承認
SAFE_TOOLS = {
    "current_time",      # 現在時刻取得
    "calculator",        # 計算のみ
    "letter_counter",    # 文字数カウント
}

# ファイル削除・コマンド実行など危険な操作 → 常に確認
DANGEROUS_TOOLS = {
    "bash",              # 任意コマンド実行
    "file_editor",       # ファイル作成・編集・削除
}

# 結果によっては機密情報を返す可能性 → 常に確認
REQUIRES_CONFIRMATION = {
    "grep_search",       # ワークスペース検索
    "read_skill",        # スキルファイル読込
    "file_read",         # ファイル読込
    "file_read_advanced", # ファイル読込（高度）
}


def classify_tool(tool_name: str) -> str:
    """ツール名から分類を返す.
    
    Args:
        tool_name: ツール名
        
    Returns:
        分類: "safe", "dangerous", "requires_confirmation" のいずれか
        
    例:
        >>> classify_tool("calculator")
        'safe'
        >>> classify_tool("file_editor")
        'dangerous'
        >>> classify_tool("grep_search")
        'requires_confirmation'
    """
    if not isinstance(tool_name, str):
        return "requires_confirmation"

    normalized_name = tool_name.strip()
    if normalized_name in SAFE_TOOLS:
        return "safe"
    elif normalized_name in DANGEROUS_TOOLS:
        return "dangerous"
    elif normalized_name in REQUIRES_CONFIRMATION:
        return "requires_confirmation"
    else:
        # 未知のツール → 確認要求（安全側）
        return "requires_confirmation"


def is_auto_approvable(tool_name: str) -> bool:
    """ツールを自動承認可能か判定.
    
    Args:
        tool_name: ツール名
        
    Returns:
        True なら自動実行、False なら確認必要
    """
    if not isinstance(tool_name, str):
        return False
    return classify_tool(tool_name) == "safe"
