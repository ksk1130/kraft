from rich.table import Table
from rich.panel import Panel

from .display_formatter import (
    console as rich_console,
    display_welcome,
    display_working,
    display_spinner,
    display_tool_execution_start,
    display_tool_execution_end,
    display_final_answer,
    display_error,
    display_goodbye,
    truncate_output,
)
from .dogfood import DogfoodAuditLogger, build_dogfood_steps


def extract_agent_response(messages: list[object]) -> str:
    """メッセージ列からユーザーに見せる最終応答を抽出する。

    `edit_file` の ToolMessage がある場合は、AI の要約よりもその
    生の結果を優先して返す。
    """
    for message in reversed(messages):
        if getattr(message, "name", None) != "edit_file":
            continue
        if hasattr(message, "content"):
            return str(message.content)
        if isinstance(message, dict) and "content" in message:
            return str(message["content"])
        return str(message)

    if not messages:
        return ""

    last_msg = messages[-1]
    if hasattr(last_msg, 'content'):
        return str(last_msg.content)
    if isinstance(last_msg, dict) and 'content' in last_msg:
        return str(last_msg['content'])
    return str(last_msg)


def main():
    """kraft CLI のエントリーポイント — 対話的チャットループ + セッション管理。"""
    # OpenTelemetry コンテキスト問題を Windows 環境で回避
    import os
    import sys
    import io
    import json
    os.environ["OTEL_SDK_DISABLED"] = "true"
    
    # HITL mode を初期化（デフォルト: interactive）
    hitl_mode = os.getenv("KRAFT_HITL_MODE", "interactive").lower()
    if hitl_mode not in ("auto", "interactive", "strict"):
        hitl_mode = "interactive"
    os.environ["KRAFT_HITL_MODE"] = hitl_mode
    
    # 循環インポートを避けるためここでインポート
    from .agent import build_agent_app, session_manager, discover_skills, search_skills, resolve_skills_dir
    from prompt_toolkit import prompt
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    
    # ウェルカムメッセージを表示
    display_welcome()
    rich_console.print()
    
    # セッション管理（新規 or 既存復元）
    sessions = session_manager.list_sessions()
    current_session_id = None
    messages_history = []
    
    if sessions:
        # Rich Table でセッション一覧を表示
        table = Table(title="[cyan bold]既存セッション[/cyan bold]", show_header=True, header_style="bold cyan")
        table.add_column("No", style="yellow bold")
        table.add_column("日付", style="cyan")
        table.add_column("タイトル")
        table.add_column("メッセージ数", justify="right", style="magenta")
        
        for idx, session in enumerate(sessions[:10], 1):
            session_id = session["session_id"]
            title = session_manager.get_session_title(session_id) or session.get("title", "Untitled")
            created = session.get("created_at", "")[:10]
            msg_count = len(session_manager.load_messages(session_id))
            table.add_row(str(idx), created, title, str(msg_count))
        
        table.add_row("0", "-", "[green bold]新規セッション作成[/green bold]", "-")
        rich_console.print(table)
        
        try:
            choice = input("セッションを選択 (0-{}, または Enter で新規): ".format(min(10, len(sessions)))).strip()
            
            # Enter キー（空入力）or "0" で新規作成
            if not choice or choice == "0":
                current_session_id = session_manager.create_session()
                messages_history = []
                print(f"\n[OK] 新規セッション作成: {current_session_id}")
            elif choice.isdigit():
                choice_num = int(choice)
                if 1 <= choice_num <= len(sessions):
                    current_session_id = sessions[choice_num - 1]["session_id"]
                    messages_history = session_manager.load_messages(current_session_id)
                    title = session_manager.get_session_title(current_session_id)
                    print(f"\n[OK] セッション復元: {title}")
                    if messages_history:
                        print(f"   (前回のメッセージ履歴 {len(messages_history)} 件)")
                else:
                    print(f"[!] 無効な選択: {choice}")
                    current_session_id = None
            else:
                print(f"[!] 無効な入力: {choice}")
                current_session_id = None
        except Exception as e:
            print(f"[!] セッション選択エラー: {e}")
            current_session_id = None
    
    # セッション ID が決まっていなければ新規作成
    if not current_session_id:
        current_session_id = session_manager.create_session()
        messages_history = []
        if sessions:  # 既存セッションがあった場合のみメッセージ出力
            print(f"[OK] 新規セッション作成: {current_session_id}\n")
        else:
            print(f"[OK] 新規セッション作成: {current_session_id}\n")
    
    session_title = session_manager.get_session_title(current_session_id)
    print(f"[Session] {session_title}")
    print()
    print("対話的チャットを開始します。")
    print("ユーザーメッセージを入力してください。")
    print("終了するには 'exit' または 'quit' と入力してください。")
    loaded_skills = discover_skills()
    skills_source = resolve_skills_dir()
    print(f"スキルソース: {skills_source}")
    print(f"ロード済みスキル数: {len(loaded_skills)}")
    if loaded_skills:
        preview_names = list(loaded_skills.keys())[:5]
        print(f"スキル: {', '.join(preview_names)}")
        if len(loaded_skills) > 5:
            print(f"... 他 {len(loaded_skills) - 5} 件")
    print()
    
    # DeepAgents app の初期化
    try:
        app, config = build_agent_app()
    except Exception as e:
        display_error(f"[red]Agent initialization error: {e}[/red]")
        return
    
    # ========================================
    # prompt_toolkit カスタマイズ設定
    # ========================================
    
    # スタイル定義（カラースキーム）
    custom_style = Style.from_dict({
        'prompt': 'bold #00d7ff',          # シアン色・太字（プロンプト部分）
        'prompt.arg': 'bold #ffff00',      # 黄色・太字（[You]:）
        'completion-menu': 'bg:#0087d7 #ffffff',      # 補完メニュー（青背景）
        'completion-menu.completion': 'bg:#0087d7 #ffffff',
        'completion-menu.completion.current': 'bg:#ffff00 #000000',  # 現在選択中（黄色背景）
        'scrollbar.background': 'bg:#222222',
        'scrollbar.button': 'bg:#00d7ff',
        'input': 'bg:#1e1e1e #ffffff',     # 入力欄（黒背景・白字）
        'toolbar': '#888888',               # ツールバー（グレー）
    })
    
    # スラッシュコマンド補完（メタ情報付き）
    slash_commands = [
        '/session list',
        '/session history',
        '/session delete',
        '/skills',
        '/clear',
        '/help',
    ]
    exit_commands = ['exit', 'quit', 'bye']
    all_commands = slash_commands + exit_commands
    
    # 補完候補の説明文
    command_meta = {
        '/session list': '既存セッション一覧を表示',
        '/session history': '現在のセッションの会話履歴を表示',
        '/session delete': 'セッションを削除',
        '/skills': 'ロード済みスキルを表示',
        '/clear': '会話履歴をクリア',
        '/help': 'コマンドヘルプを表示',
        'exit': 'チャットを終了',
        'quit': 'チャットを終了',
        'bye': 'チャットを終了',
    }
    
    # WordCompleter（メタテキスト付き）
    completer = WordCompleter(
        all_commands,
        sentence=True,
        ignore_case=True,
        meta_dict=command_meta,
    )
    
    # プロンプト表示テキスト（HTML フォーマット）
    prompt_text = HTML('<b fg="#ffff00">➜</b> <b fg="#00d7ff">[You]:</b> ')

    # 複数行入力対応: Enter で送信、Esc+Enter で改行
    # shift-enter は prompt_toolkit の key name として invalid なので使わない
    multiline_bindings = KeyBindings()

    @multiline_bindings.add('enter')
    def _(event):
        """Enter で入力確定（送信）。"""
        event.current_buffer.validate_and_handle()

    @multiline_bindings.add('escape', 'enter')
    def _(event):
        """Esc+Enter で改行。"""
        event.current_buffer.insert_text('\n')
    
    # ボトムツールバーテキスト（ヘルプ表示）
    def get_bottom_toolbar_text():
        return HTML(
            '<b fg="#ffff00">💡 Tip:</b> '
            '<b fg="#00d7ff">Tab</b> でコマンド補完 | '
            '<b fg="#00d7ff">Shift+Enter</b> で改行 | '
            '<b fg="#00d7ff">Enter</b> で送信 | '
            '<b fg="#00d7ff">Ctrl+C</b> で中断'
        )
    
    # 対話的チャットループ
    while True:
        try:
            # ユーザーからの入力を取得（複数行対応 or フォールバック）
            user_message = None
            try:
                # prompt_toolkit を試す
                user_message = prompt(
                    prompt_text,
                    completer=completer,
                    style=custom_style,
                    multiline=True,
                    key_bindings=multiline_bindings,
                    bottom_toolbar=get_bottom_toolbar_text,
                ).strip()
            except Exception as prompt_error:
                # PowerShell または stdin 検出エラーの場合は基本的な input() にフォールバック
                rich_console.print(f"[dim](prompt_toolkit エラー: {type(prompt_error).__name__}、通常入力に切り替え)[/dim]")
                user_message = input("➜ [You]: ").strip()
            
            # 空文字列はスキップ
            if not user_message:
                rich_console.print("[dim](メッセージが入力されていません)[/dim]")
                continue
            
            # セッション管理コマンド
            if user_message.lower() == "/session list":
                sessions = session_manager.list_sessions()
                table = Table(title="[cyan bold]セッション一覧[/cyan bold]", show_header=True, header_style="bold cyan")
                table.add_column("日付", style="cyan")
                table.add_column("タイトル")
                table.add_column("メッセージ数", justify="right", style="magenta")
                
                if sessions:
                    for session in sessions[:10]:
                        session_id = session["session_id"]
                        title = session_manager.get_session_title(session_id) or session.get("title", "Untitled")
                        created = session.get("created_at", "")[:10]
                        msg_count = len(session_manager.load_messages(session_id))
                        table.add_row(created, title, str(msg_count))
                    rich_console.print()
                    rich_console.print(table)
                else:
                    rich_console.print(Panel("[dim]セッションはありません[/dim]", title="セッション一覧"))
                rich_console.print()
                continue

            if user_message.lower() == "/session history":
                history = session_manager.load_messages(current_session_id)
                if not history:
                    rich_console.print(Panel("[dim]このセッションには履歴がありません[/dim]", title="会話履歴"))
                    rich_console.print()
                    continue

                preview = session_manager.format_history_preview(history, max_entries=20)
                rich_console.print(Panel(preview, title="[cyan bold]会話履歴[/cyan bold]", border_style="cyan"))
                rich_console.print()
                continue

            if user_message.isdigit() and 0 <= int(user_message) <= 10 and not user_message.startswith("/"):
                # セッション選択時の番号は通常メッセージとして扱わない
                rich_console.print("[dim](セッション選択番号は通常メッセージではありません。セッション一覧から選択してください。)[/dim]")
                continue
            
            if user_message.lower().startswith("/session delete"):
                confirm = input("  Delete this session? (yes/no): ").strip().lower()
                if confirm == "yes":
                    session_manager.delete_session(current_session_id)
                    print("  [OK] Session deleted.")
                    break
                continue
            
            # スキル表示コマンド
            if user_message.lower() == "/skills":
                table = Table(title="[cyan bold]ロード済みスキル[/cyan bold]", show_header=True, header_style="bold cyan")
                table.add_column("スキル名", style="yellow bold")
                table.add_column("説明")

                current_skills = discover_skills()
                if current_skills:
                    for name, skill in current_skills.items():
                        description = skill.get("description", "")[:60] if skill.get("description") else "(説明なし)"
                        table.add_row(name, description)
                    rich_console.print()
                    rich_console.print(table)
                else:
                    rich_console.print(Panel("[dim]スキルがロードされていません[/dim]", title="スキル一覧"))
                rich_console.print()
                continue
            
            # スキル検索コマンド
            if user_message.lower().startswith("/skill search "):
                keyword = user_message[len("/skill search "):].strip()
                if not keyword:
                    rich_console.print(Panel("[yellow]キーワードを指定してください: /skill search <keyword>[/yellow]", title="エラー"))
                    rich_console.print()
                    continue
                
                results = search_skills(keyword)
                if results:
                    table = Table(title=f"[cyan bold]スキル検索結果: '{keyword}'[/cyan bold]", show_header=True, header_style="bold cyan")
                    table.add_column("スキル名", style="yellow bold")
                    table.add_column("説明")
                    
                    for name, description in results:
                        description_preview = description[:70] if description else "(説明なし)"
                        table.add_row(name, description_preview)
                    
                    rich_console.print()
                    rich_console.print(table)
                else:
                    rich_console.print(Panel(f"[dim]キーワード '{keyword}' にマッチするスキルが見つかりません[/dim]", title="検索結果"))
                rich_console.print()
                continue
            
            # 会話履歴クリアコマンド
            if user_message.lower() == "/clear":
                confirm = input("  会話履歴をクリアしますか？ (yes/no): ").strip().lower()
                if confirm == "yes":
                    messages_history.clear()
                    print("  [OK] 会話履歴をクリアしました。")
                continue
            
            # ヘルプコマンド
            if user_message.lower() == "/help":
                help_text = """
[cyan bold]セッション管理:[/cyan bold]
  /session list     - セッション一覧を表示
  /session history  - 現在のセッションの履歴を表示
  /session delete   - 現在のセッションを削除

[cyan bold]スキル・ツール:[/cyan bold]
  /skills          - ロード済みスキルをすべて表示
  /skill search    - スキルをキーワード検索 (例: /skill search python)

[cyan bold]その他:[/cyan bold]
  /clear           - 会話履歴をクリア
  /help            - このヘルプを表示
  exit/quit/bye    - 対話を終了
                """
                rich_console.print()
                rich_console.print(Panel(help_text, title="[yellow bold]利用可能なコマンド[/yellow bold]", border_style="cyan"))
                rich_console.print()
                continue
            
            # 終了コマンドのチェック
            if user_message.lower() in ["exit", "quit", "bye"]:
                # 最後のメッセージ履歴を保存
                session_manager.save_messages(current_session_id, messages_history)
                display_goodbye()
                break
            
            # ユーザーメッセージを履歴に追加
            messages_history.append({
                "role": "user",
                "content": user_message
            })

            # DeepAgents にメッセージを送信して実行
            print()
            try:
                from langgraph.types import Command
                
                agent_response = ""
                last_output = None
                
                # ========================================
                # エージェント実行ループ（HITL ゲート付き）
                # ========================================
                processing_message = "LLM が応答を生成中です... しばらくお待ちください"
                with display_spinner(processing_message, spinner_style="dots"):
                    # ターン1: 初回実行
                    for output in app.stream(
                        {"messages": messages_history + [{"role": "user", "content": user_message}]},
                        config,
                        stream_mode="values"
                    ):
                        last_output = output
                
                # ========================================
                # HITL ゲートループ（複数ツール対応）
                # ========================================
                # HITL によって中断された場合、ユーザー承認を得て Resume
                # 複数ツール呼び出しの場合、Resume 後も別の中断が起きるので while でループ
                from langchain_core.messages import AIMessage
                
                # === DEBUG: 初回実行後の状態確認 ===
                state = app.get_state(config)
                print(f"\n[DEBUG] After initial stream: state.next = {state.next}")
                if hasattr(state, 'values') and 'messages' in state.values:
                    messages = state.values['messages']
                    if messages:
                        last_msg = messages[-1]
                        print(f"[DEBUG] Last message type: {type(last_msg).__name__}")
                        if isinstance(last_msg, AIMessage):
                            print(f"[DEBUG] Tool calls in last AIMessage: {len(last_msg.tool_calls) if hasattr(last_msg, 'tool_calls') else 0}")
                
                hitl_iterations = 0
                MAX_HITL_ITERATIONS = 10  # 無限ループ防止
                
                while hitl_iterations < MAX_HITL_ITERATIONS:
                    state = app.get_state(config)
                    if not state.next:
                        # 中断なし = 処理完了
                        break
                    
                    hitl_iterations += 1
                    print(f"\n⚠️  [HITL] ツール実行には承認が必要です（ラウンド {hitl_iterations}）")
                    
                    # ========================================
                    # 正しい情報源：state.messages の AIMessage.tool_calls
                    # ========================================
                    # StateSnapshot のアクセス方法
                    if hasattr(state, 'values'):
                        messages = state.values.get("messages", [])
                    else:
                        messages = getattr(state, 'messages', [])
                    
                    # 最後の AIMessage を探す
                    ai_msg = None
                    for msg in reversed(messages):
                        if isinstance(msg, AIMessage):
                            ai_msg = msg
                            break
                    
                    if ai_msg and hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
                        tool_calls = ai_msg.tool_calls
                        print(f"📋 承認待ちのツール: {len(tool_calls)} 件")

                        # 各ツール呼び出しについてユーザー確認
                        decisions_list = []
                        for idx, tool_call in enumerate(tool_calls, 1):
                            tool_name = tool_call.get('name', 'unknown_tool')
                            tool_args = tool_call.get('args', {})
                            tool_id = tool_call.get('id', 'unknown_id')

                            display_tool_execution_start(tool_name)
                            print(f"\n[ツール {idx}/{len(tool_calls)}]")
                            print(f"  📝 実行対象: {tool_name}")
                            print(f"  📦 引数: {tool_args}")

                            # ========================================
                            # ユーザーによる承認/却下
                            # ミドルウェア側で hitl_prompt.py のデザインを使う
                            # ========================================
                            from kraft.approval import ToolContext, get_user_approval
                            context = ToolContext(
                                tool_name=tool_name,
                                tool_args=tool_args,
                                tool_description=f"LangGraph HumanInTheLoop middleware approval for {tool_name}",
                            )
                            approved = get_user_approval(context, hitl_mode="interactive")

                            if approved:
                                decision_obj = {"type": "approve"}
                                user_decision = "承認"
                                display_tool_execution_end(tool_name, success=True)
                            else:
                                decision_obj = {"type": "reject", "message": "ユーザーがこのツール呼び出しを拒否しました"}
                                user_decision = "拒否"
                                display_tool_execution_end(tool_name, success=False)

                            print(f"  ✓ 決定: {user_decision}")
                            decisions_list.append(decision_obj)
                        
                        # ========================================
                        # Resume 実行（複数決定をまとめて送信）
                        # ========================================
                        resume_message = f"承認を反映して再開中です... ({len(decisions_list)} 件)"
                        decisions = {"decisions": decisions_list}

                        with display_spinner(resume_message, spinner_style="dots"):
                            for resume_output in app.stream(
                                Command(resume=decisions),
                                config,
                                stream_mode="values"
                            ):
                                last_output = resume_output
                    else:
                        print("[!] Could not retrieve pending tool calls from AIMessage")
                        break
                
                if hitl_iterations >= MAX_HITL_ITERATIONS:
                    print("[!] HITL iterations exceeded limit - stopping")
                
                # 最後の出力からメッセージを抽出
                if last_output and "messages" in last_output:
                    messages = last_output["messages"]
                    if messages:
                        agent_response = extract_agent_response(messages)
                
                # 応答がない場合のフォールバック
                if not agent_response:
                    agent_response = "[No response from agent]"
                
                # トークン制限エラー回避：長い出力を制限
                agent_response = truncate_output(agent_response, max_lines=100, max_chars=3000)
                
                # 最終回答をパネルで表示
                display_final_answer(agent_response)
                
                messages_history.append({
                    "role": "assistant",
                    "content": agent_response
                })
                
                # メッセージ履歴を定期的に保存（2メッセージごと）
                if len(messages_history) % 2 == 0:
                    session_manager.save_messages(current_session_id, messages_history)
                
            except Exception as e:
                display_error(f"[red]{e}[/red]")
        
        except KeyboardInterrupt:
            # 最後のメッセージ履歴を保存
            session_manager.save_messages(current_session_id, messages_history)
            display_error("[yellow]対話が中断されました。セッションを保存して終了します。[/yellow]")
            break
        except Exception as e:
            display_error(f"[red]予期しないエラー: {e}[/red]")


__all__ = ["main"]
