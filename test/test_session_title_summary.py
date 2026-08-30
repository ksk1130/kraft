from kraft.agent import SessionManager


def test_session_title_is_generated_from_first_user_message(tmp_path):
    """最初のユーザーメッセージからセッションタイトルが自動生成されることを確認する。"""
    manager = SessionManager(str(tmp_path))
    session_id = manager.create_session()

    manager.save_messages(session_id, [
        {"role": "user", "content": "このPythonのバグを直して"},
        {"role": "assistant", "content": "了解しました。まず原因を確認します。"},
    ])

    title = manager.get_session_title(session_id)
    assert title is not None
    assert "このPythonのバグを直して" in title
    assert len(title) <= 40


def test_existing_session_title_is_regenerated_from_message_history(tmp_path):
    """既存の自動タイトルも、起動時にメッセージ履歴から再生成されることを確認する。"""
    manager = SessionManager(str(tmp_path))
    session_id = manager.create_session(title="Session 2026-08-30 17:22")
    manager.save_messages(session_id, [
        {"role": "user", "content": "このセッションのタイトルを要約してほしい"},
        {"role": "assistant", "content": "いいですね。"},
    ])

    metadata = manager._load_metadata(session_id)
    metadata["title"] = "Session 2026-08-30 17:22"
    manager._save_metadata(session_id, metadata)

    title = manager.get_session_title(session_id)
    assert "このセッションのタイトルを要約してほしい" in title

