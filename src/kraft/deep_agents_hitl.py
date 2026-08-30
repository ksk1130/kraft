"""DeepAgents の HITL 用サンプル実装.

このモジュールは、次の2つを分離して管理しやすい形で定義する:
1. 危険な操作（承認が必要なツール）
2. モデルと状態保存（checkpoint）を持つ Deep Agent の生成

利用前に環境変数 GOOGLE_API_KEY を設定してください。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from deepagents import create_deep_agent
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command


@tool
def delete_file(filename: str) -> str:
    """指定したファイルを削除する危険操作。

    Args:
        filename: 削除対象のファイル名

    Returns:
        実行結果メッセージ
    """
    return f"ファイル {filename} を削除しました。"


@tool
def read_file(filename: str) -> str:
    """指定したファイルを読み込む安全な操作。

    Args:
        filename: 読み込むファイル名

    Returns:
        ダミーのファイル内容
    """
    return f"ファイル {filename} の中身: [ダミーテキスト]"


def build_deep_agent_app() -> tuple[Any, dict[str, Any]]:
    """Deep Agent を生成して、checkpoint を紐づけたアプリを返す.

    DeepAgents の `create_deep_agent()` はもう既に compiled graph を返すため、
    ここでは `compile()` を呼ばずにそのまま使用する。

    Returns:
        (app, config) のタプル
    """
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise RuntimeError("GOOGLE_API_KEY が未設定です。環境変数を設定してください。")

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=google_api_key)
    checkpointer = MemorySaver()

    app = create_deep_agent(
        model=llm,
        tools=[delete_file, read_file],
        interrupt_on={
            "delete_file": True,
            "read_file": False,
        },
        checkpointer=checkpointer,
    )

    config = {"configurable": {"thread_id": "user_session_123"}}
    return app, config


def _coerce_interrupt_value(raw: Any) -> Any:
    """HITL の interrupt 値を安全に取り出す."""
    if isinstance(raw, tuple):
        if not raw:
            return {}
        first = raw[0]
        return getattr(first, "value", first)
    if isinstance(raw, list):
        return raw[0] if raw else {}
    return raw


def _build_resume_payload(hitl_request: Any, *, approve: bool = True) -> dict[str, Any]:
    """HITL で実際に返す承認結果を作る."""
    request_payload = hitl_request or {}
    action_requests = request_payload.get("action_requests", []) if isinstance(request_payload, dict) else []

    decisions: list[dict[str, Any]] = []
    for _ in action_requests:
        if approve:
            decisions.append({"type": "approve"})
        else:
            decisions.append({"type": "reject", "message": "ユーザーが拒否しました。"})

    if not decisions:
        decisions.append({"type": "approve"})

    return {"decisions": decisions}


def run_hitl_demo(user_prompt: str | None = None, *, approve: bool = True) -> dict[str, Any]:
    """実際に `stream` → interrupt → `resume` の確認を行う."""
    user_prompt = user_prompt or "重要ファイルの secret.txt を削除してください。"
    app, config = build_deep_agent_app()

    print("Deep Agent HITL demo initialized.")
    print(f"ユーザー入力: {user_prompt}")

    events = list(app.stream({"messages": [("user", user_prompt)]}, config, stream_mode="values"))
    interrupt_event = next(
        (event for event in events if "__interrupt__" in event),
        None,
    )

    if interrupt_event is None:
        return {"status": "completed_without_interrupt", "events": events}

    interrupt_value = _coerce_interrupt_value(interrupt_event["__interrupt__"])
    print("HITL request captured:")
    print(json.dumps(interrupt_value, ensure_ascii=False, indent=2))

    resume_payload = _build_resume_payload(interrupt_value, approve=approve)
    print("Resume payload:")
    print(json.dumps(resume_payload, ensure_ascii=False, indent=2))

    resumed_events = list(app.stream(Command(resume=resume_payload), config, stream_mode="values"))
    print("Resume result:")
    for resumed_event in resumed_events:
        print(json.dumps(resumed_event, ensure_ascii=False, indent=2, default=str))

    return {
        "status": "resumed",
        "interrupt": interrupt_value,
        "resume": resume_payload,
        "events": resumed_events,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI エントリーポイント."""
    parser = argparse.ArgumentParser(description="DeepAgents HITL demo")
    parser.add_argument("--prompt", default="重要ファイルの secret.txt を削除してください。", help="ユーザー入力テキスト")
    parser.add_argument("--approve", action="store_true", help="承認して再開する")
    parser.add_argument("--reject", action="store_true", help="拒否して再開する")
    args = parser.parse_args(argv)

    if args.reject:
        approve = False
    else:
        approve = args.approve or True

    if not os.getenv("GOOGLE_API_KEY"):
        print("GOOGLE_API_KEY が未設定のため、ライブ実行はスキップします。", file=sys.stderr)
        print("設定後に以下を実行してください:")
        print("  set GOOGLE_API_KEY=... (Windows PowerShell)")
        print("  export GOOGLE_API_KEY=... (bash/zsh)")
        print("  または --help を使ってヘルプを確認してください。")
        return 0

    run_hitl_demo(args.prompt, approve=approve)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
