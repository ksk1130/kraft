from kraft.agent import SessionManager


def test_session_history_preview_formats_user_and_ai_messages():
    """セッション履歴のプレビューが、ユーザーと AI の発話を区別して表示できることを確認する。"""
    messages = [
        {"role": "user", "content": "この修正を進めて"},
        {"role": "assistant", "content": "了解しました。まずは確認します。"},
    ]

    preview = SessionManager.format_history_preview(messages, max_entries=10)

    assert "ユーザー" in preview
    assert "AI" in preview
    assert "この修正を進めて" in preview
    assert "了解しました。まずは確認します。" in preview

