from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import Command
from rich.panel import Panel
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static, TextArea

from kraft.streaming import StreamEvent, iter_stream_events

PASTE_PLACEHOLDER_PATTERN = re.compile(r"\[Pasted text #(\d+)(?: \+(\d+) lines)?\]")


def _expand_paste_refs(text: str, pasted_contents: dict[int, str]) -> str:
    """Expand collapsed paste placeholders back to their original text."""

    def _replace(match: re.Match[str]) -> str:
        paste_id = int(match.group(1))
        return pasted_contents.get(paste_id, match.group(0))

    return PASTE_PLACEHOLDER_PATTERN.sub(_replace, text)


class ComposerTextArea(TextArea):
    """TextArea-based chat composer with multi-line support and paste collapsing."""

    MIN_HEIGHT = 3
    MAX_HEIGHT = 15

    BINDINGS = [
        Binding("enter", "submit", "Send", show=False, priority=True),
        Binding("tab", "complete_command", "Complete", show=False, priority=True),
        Binding("shift+enter,alt+enter,ctrl+enter,ctrl+j", "insert_newline", "New Line", show=False, priority=True),
    ]

    class Submitted(Message):
        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def on_mount(self) -> None:
        self.styles.height = "auto"
        self.styles.min_height = self.MIN_HEIGHT
        self.styles.max_height = self.MAX_HEIGHT
        self.refresh(layout=True)

    def action_submit(self) -> None:
        value = self.text.strip()
        if value:
            self.post_message(self.Submitted(value))
            self.load_text("")

    def action_insert_newline(self) -> None:
        self.insert("\n")
        self.refresh(layout=True)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:  # noqa: ARG002
        self.refresh(layout=True)
        if hasattr(self.app, "_update_command_suggestions"):
            self.app._update_command_suggestions(self.text)

    def action_complete_command(self) -> None:
        if hasattr(self.app, "_complete_slash_command"):
            self.app._complete_slash_command(self.text)

    def on_paste(self, event: events.Paste) -> None:
        text = event.text
        if not text:
            return
        if len(text) > 800 or text.count("\n") > 2:
            event.stop()
            paste_id = len(self.app.pasted_contents) + 1
            num_lines = text.count("\n")
            placeholder = f"[Pasted text #{paste_id} +{num_lines} lines]"
            self.app.pasted_contents[paste_id] = text
            self.insert(placeholder)
            return
        self.insert(text)
        event.stop()


class MessageTextArea(TextArea):
    """Read-only timeline message that supports mouse selection and copy."""

    MIN_HEIGHT = 3
    MAX_HEIGHT = 20

    def __init__(self, message: str, *, row_class: str, row_id: str | None = None) -> None:
        super().__init__(
            text=message,
            id=row_id,
            classes=f"row message-row {row_class}",
            read_only=True,
            show_line_numbers=False,
            soft_wrap=True,
        )

    def on_mount(self) -> None:
        self._sync_height()

    def set_message(self, message: str) -> None:
        self.load_text(message)
        self._sync_height()

    def _sync_height(self) -> None:
        line_count = max(1, self.document.line_count)
        height = min(max(self.MIN_HEIGHT, line_count + 2), self.MAX_HEIGHT)
        self.styles.height = height
        self.styles.min_height = self.MIN_HEIGHT
        self.styles.max_height = self.MAX_HEIGHT
        self.refresh(layout=True)


class ApprovalModal(ModalScreen[bool]):
    """Simple yes/no approval modal for HITL tool execution."""

    BINDINGS = [
        ("y", "approve", "Approve"),
        ("n", "reject", "Reject"),
        ("escape", "reject", "Reject"),
        ("enter", "approve", "Approve"),
    ]

    def __init__(self, tool_name: str, tool_args: dict[str, Any]) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.tool_args = tool_args

    def compose(self) -> ComposeResult:
        lines = [f"Tool: {self.tool_name}", ""]
        if self.tool_args:
            lines.append("Args:")
            for key, value in self.tool_args.items():
                lines.append(f"  - {key}: {value}")
        else:
            lines.append("Args: (none)")
        lines.append("")
        lines.append("[Y] approve / [N] reject")
        yield Static(
            Panel(
                "\n".join(lines),
                title="HITL Approval",
                border_style="yellow",
                padding=(1, 1),
            ),
            id="approval-modal",
        )

    def action_approve(self) -> None:
        self.dismiss(True)

    def action_reject(self) -> None:
        self.dismiss(False)


class KraftTextualApp(App[None]):
    """Textual-based kraft chat UI."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #timeline {
        height: 1fr;
        min-height: 0;
        border: round $primary;
        padding: 0 1;
        margin: 0;
    }
    ComposerTextArea {
        min-height: 3;
        height: auto;
        max-height: 15;
        margin-top: 0;
        margin-bottom: 1;
    }
    Footer {
        height: 1;
        dock: bottom;
        layer: above;
    }
    .row {
        margin: 0 0 1 0;
    }
    .message-row {
        border: round $panel;
        padding: 0 1;
        background: $surface;
    }
    .row-user {
        border: round green;
    }
    .row-system {
        border: round blue;
    }
    .row-error {
        border: round red;
    }
    .row-assistant {
        border: round cyan;
    }
    #completion-hint {
        display: none;
        min-height: 1;
        height: auto;
        max-height: 5;
        color: $text-muted;
        background: $surface;
        border: round $primary;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    """

    BINDINGS = [
        ("ctrl+c", "copy_selection", "Copy selection"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        os.environ["OTEL_SDK_DISABLED"] = "true"
        self.hitl_mode = os.getenv("KRAFT_HITL_MODE", "interactive").lower()
        if self.hitl_mode not in ("auto", "interactive", "strict"):
            self.hitl_mode = "interactive"
        os.environ["KRAFT_HITL_MODE"] = self.hitl_mode

        self.agent_app: Any | None = None
        self.agent_config: dict[str, Any] = {}
        self.session_manager: Any | None = None
        self.discover_skills: Any | None = None
        self.resolve_skills_dir: Any | None = None
        self.ToolContext: Any | None = None
        self.messages_history: list[dict[str, str]] = []
        self.current_session_id: str = ""
        self.turn_states: dict[str, dict[str, Any]] = {}
        self.pasted_contents: dict[int, str] = {}
        self._slash_commands = [
            "/help",
            "/pwd",
            "/cwd",
            "/cd",
            "/workspace",
            "/skills",
            "/session list",
            "/session history",
            "/copy",
            "/copy selection",
        ]
        self._assistant_counter = 0
        self._spinner_frames = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧")
        self._spinner_index = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(id="timeline")
        yield Static("", id="completion-hint")
        composer = ComposerTextArea(placeholder="メッセージを入力してください... (/help)", id="composer", soft_wrap=True)
        yield composer
        yield Footer()

    def on_mount(self) -> None:
        composer = self.query_one("#composer", ComposerTextArea)
        composer.load_text("")
        self._update_command_suggestions("")
        composer.focus()
        self._toggle_timeline_visibility()
        self.set_interval(0.1, self._refresh_thinking_rows)
        self._append_system("kraft Textual UI を起動しました。")

        try:
            from kraft.agent import build_agent_app, discover_skills, resolve_skills_dir, session_manager
            from kraft.approval import ToolContext
        except Exception as exc:
            self._append_error(f"初期化に失敗しました: {exc}")
            return

        self.session_manager = session_manager
        self.discover_skills = discover_skills
        self.resolve_skills_dir = resolve_skills_dir
        self.ToolContext = ToolContext

        sessions = self.session_manager.list_sessions()
        if sessions:
            latest_session = sessions[0]
            self.current_session_id = latest_session["session_id"]
            self.messages_history = self.session_manager.load_messages(self.current_session_id)
            title = self.session_manager.get_session_title(self.current_session_id) or latest_session.get("title", "Untitled")
            self._append_system(f"セッション復元: {title}")
        else:
            self.current_session_id = self.session_manager.create_session()
            self._append_system(f"新規セッション: {self.current_session_id}")

        skills = self.discover_skills()
        self._append_system(f"スキルソース: {self.resolve_skills_dir()}")
        self._append_system(f"ロード済みスキル数: {len(skills)}")

        try:
            self.agent_app, self.agent_config = build_agent_app()
        except Exception as exc:
            self._append_error(f"Agent initialization error: {exc}")

    def on_composer_text_area_submitted(self, event: ComposerTextArea.Submitted) -> None:
        message = _expand_paste_refs(event.value.strip(), self.pasted_contents)
        if not message:
            return

        if message.lower() in {"exit", "quit", "bye"}:
            self.action_quit()
            return

        if message.startswith("/"):
            self._handle_command(message)
            return

        if self.agent_app is None:
            self._append_error("Agent is not initialized.")
            return

        self._append_user(message)
        assistant_id = self._new_assistant_row()
        self.turn_states[assistant_id] = {"text": "", "tools": [], "thinking": True}
        self._update_assistant_row(assistant_id)
        self._run_agent_turn(message, assistant_id)

    def action_quit(self) -> None:
        if self.current_session_id and self.session_manager is not None:
            self.session_manager.save_messages(self.current_session_id, self._serialize_messages_for_session())
        self.exit()

    def _update_command_suggestions(self, value: str) -> None:
        hint_widget = self.query_one("#completion-hint", Static)
        draft = value.strip()
        if not draft or not draft.startswith("/"):
            hint_widget.update("")
            hint_widget.styles.display = "none"
            return

        matches = [cmd for cmd in self._slash_commands if cmd.lower().startswith(draft.lower())]
        if not matches:
            hint_widget.update("")
            hint_widget.styles.display = "none"
            return

        preview = "  ".join(matches[:5])
        hint_widget.update(f"候補: {preview}")
        hint_widget.styles.display = "block"

    def _complete_slash_command(self, value: str) -> None:
        draft = value.strip()
        if not draft.startswith("/"):
            return
        matches = [cmd for cmd in self._slash_commands if cmd.lower().startswith(draft.lower())]
        if not matches:
            return
        composer = self.query_one("#composer", ComposerTextArea)
        composer.load_text(matches[0])
        composer.cursor_position = len(matches[0])
        self._update_command_suggestions(matches[0])

    def _handle_command(self, command: str) -> None:
        lower = command.lower()
        if lower in {"/help", "/?"}:
            self._append_system(
                "Commands: /help, /pwd, /cwd, /cd <path>, /workspace [path], /skills, /session list, /session history, /copy, /copy selection"
            )
            return
        if lower in {"/pwd", "/cwd"}:
            self._append_system(str(Path.cwd()))
            return
        if lower == "/skills":
            skills = self.discover_skills() if self.discover_skills is not None else {}
            if not skills:
                self._append_system("スキルが見つかりません。")
                return
            names = ", ".join(list(skills.keys())[:10])
            self._append_system(f"スキル: {names}")
            return
        if lower == "/session list":
            if self.session_manager is None:
                self._append_system("(履歴なし)")
                return
            sessions = self.session_manager.list_sessions()
            if not sessions:
                self._append_system("セッションはありません。")
                return
            entries = [f"{idx + 1}. {session.get('session_id', 'unknown')}" for idx, session in enumerate(sessions[:10])]
            self._append_system("; ".join(entries))
            return
        if lower == "/session history":
            preview = (
                self.session_manager.format_history_preview(self._serialize_messages_for_session(), max_entries=20)
                if self.session_manager is not None
                else "(履歴なし)"
            )
            self._append_system(preview)
            return
        if lower == "/copy":
            assistant_text = ""
            for item in reversed(self.messages_history):
                if item.get("role") == "assistant" and item.get("content"):
                    assistant_text = str(item["content"])
                    break
            if assistant_text:
                try:
                    import tkinter as tk
                    root = tk.Tk()
                    root.withdraw()
                    root.clipboard_clear()
                    root.clipboard_append(assistant_text)
                    root.update()
                    root.destroy()
                    self._append_system("最新の応答をクリップボードにコピーしました。")
                except Exception as exc:  # pragma: no cover - environment dependent
                    self._append_error(f"クリップボードへのコピーに失敗しました: {exc}")
            else:
                self._append_system("コピーする応答がありません。")
            return
        if lower == "/copy selection":
            self.action_copy_selection()
            return
        if lower.startswith("/cd "):
            self._change_dir(command[4:].strip())
            return
        if lower == "/workspace":
            self._append_system(os.environ.get("KRAFT_WORKSPACE_ROOT", str(Path.cwd())))
            return
        if lower.startswith("/workspace "):
            self._change_dir(command[len("/workspace "):].strip())
            return
        self._append_system(f"Unknown command: {command}")

    def _change_dir(self, target: str) -> None:
        if not target:
            self._append_error("パスを指定してください。")
            return
        target_path = Path(target).expanduser()
        if not target_path.is_absolute():
            target_path = (Path.cwd() / target_path).resolve()
        else:
            target_path = target_path.resolve()
        if not target_path.exists() or not target_path.is_dir():
            self._append_error(f"無効なディレクトリ: {target_path}")
            return
        os.chdir(target_path)
        os.environ["KRAFT_WORKSPACE_ROOT"] = str(target_path)
        self._append_system(f"作業ディレクトリを変更しました: {target_path}")

    @work(thread=True, exclusive=True)
    def _run_agent_turn(self, user_message: str, assistant_id: str) -> None:
        self.messages_history.append({"role": "user", "content": user_message})
        agent_response = ""
        last_output: Any = None

        stream_input = {"messages": self._serialize_messages_for_session()}
        for raw_chunk in self.agent_app.stream(stream_input, self.agent_config, stream_mode="messages"):
            last_output = raw_chunk
            for event in iter_stream_events([raw_chunk]):
                self.call_from_thread(self._apply_stream_event, assistant_id, event)

        hitl_iterations = 0
        while hitl_iterations < 10:
            state = self.agent_app.get_state(self.agent_config)
            if not state.next:
                break
            hitl_iterations += 1
            messages = state.values.get("messages", []) if hasattr(state, "values") else getattr(state, "messages", [])
            ai_msg = next((msg for msg in reversed(messages) if isinstance(msg, AIMessage)), None)
            if ai_msg is None or not getattr(ai_msg, "tool_calls", None):
                break
            decisions_list: list[dict[str, Any]] = []
            for tool_call in ai_msg.tool_calls:
                tool_name = tool_call.get("name", "unknown_tool")
                tool_args = tool_call.get("args", {})
                approved = self._request_tool_approval(tool_name, tool_args)
                decisions_list.append(
                    {"type": "approve"} if approved else {"type": "reject", "message": "ユーザーが拒否しました"}
                )
            decisions = {"decisions": decisions_list}
            for raw_chunk in self.agent_app.stream(Command(resume=decisions), self.agent_config, stream_mode="messages"):
                last_output = raw_chunk
                for event in iter_stream_events([raw_chunk]):
                    self.call_from_thread(self._apply_stream_event, assistant_id, event)

        if isinstance(last_output, dict) and "messages" in last_output and last_output["messages"]:
            content = getattr(last_output["messages"][-1], "content", "")
            if content:
                agent_response = str(content)

        self.call_from_thread(self._finalize_assistant_row, assistant_id, agent_response)

    def _request_tool_approval(self, tool_name: str, tool_args: dict[str, Any]) -> bool:
        if self.hitl_mode == "auto":
            return True
        if self.hitl_mode == "strict":
            return self._request_tool_approval_modal(tool_name, tool_args)
        if self.ToolContext is None:
            return self._request_tool_approval_modal(tool_name, tool_args)
        context = self.ToolContext(
            tool_name=tool_name,
            tool_args=tool_args,
            tool_description=f"Approval required for {tool_name}",
        )
        if context.auto_approve_if_safe():
            return True
        return self._request_tool_approval_modal(tool_name, tool_args)

    def _request_tool_approval_modal(self, tool_name: str, tool_args: dict[str, Any]) -> bool:
        done = threading.Event()
        result: dict[str, bool] = {"approved": False}

        def _open_modal() -> None:
            self.push_screen(
                ApprovalModal(tool_name, tool_args),
                callback=lambda approved: self._on_approval_decided(approved, result, done),
            )

        self.call_from_thread(_open_modal)
        done.wait()
        return result["approved"]

    def _on_approval_decided(self, approved: bool | None, result: dict[str, bool], done: threading.Event) -> None:
        result["approved"] = bool(approved)
        done.set()

    def _apply_stream_event(self, assistant_id: str, event: StreamEvent) -> None:
        state = self.turn_states.get(assistant_id)
        if state is None:
            return
        if event.kind == "assistant_delta":
            state["thinking"] = False
            state["text"] += event.text
        elif event.kind == "tool_start":
            state["tools"].append((event.tool_name or "tool", "running"))
        elif event.kind == "tool_result":
            name = event.tool_name or "tool"
            tools: list[tuple[str, str]] = state["tools"]
            for index, (tool_name, _) in enumerate(tools):
                if tool_name == name:
                    tools[index] = (name, "success")
                    break
        elif event.kind == "interrupt":
            state["thinking"] = False
            state["text"] += "\n[HITL approval required]"
        elif event.kind == "done":
            state["thinking"] = False
        self._update_assistant_row(assistant_id)

    def _finalize_assistant_row(self, assistant_id: str, fallback_text: str) -> None:
        state = self.turn_states.get(assistant_id)
        if state is None:
            return
        state["thinking"] = False
        if not state["text"]:
            state["text"] = fallback_text or "[No response from agent]"
        final_text = state["text"]
        self._update_assistant_row(assistant_id)
        self.messages_history.append({"role": "assistant", "content": final_text})
        if self.current_session_id and self.session_manager is not None:
            self.session_manager.save_messages(self.current_session_id, self._serialize_messages_for_session())

    def _serialize_messages_for_session(self) -> list[dict[str, str]]:
        serialized: list[dict[str, str]] = []
        for message in self.messages_history:
            if isinstance(message, dict):
                role = str(message.get("role", "assistant"))
                content = str(message.get("content", ""))
                serialized.append({"role": role, "content": content})
                continue
            role = str(getattr(message, "type", "assistant"))
            if role == "human":
                role = "user"
            elif role in {"ai", "assistant"}:
                role = "assistant"
            content = str(getattr(message, "content", ""))
            serialized.append({"role": role, "content": content})
        return serialized

    def _refresh_thinking_rows(self) -> None:
        self._spinner_index = (self._spinner_index + 1) % len(self._spinner_frames)
        for assistant_id, state in self.turn_states.items():
            if state.get("thinking"):
                self._update_assistant_row(assistant_id)

    def _update_assistant_row(self, assistant_id: str) -> None:
        state = self.turn_states.get(assistant_id)
        if state is None:
            return
        widget = self.query_one(f"#{assistant_id}", MessageTextArea)
        text = state["text"]
        if not text and state.get("thinking"):
            frame = self._spinner_frames[self._spinner_index]
            text = f"{frame} AI が応答を構築しています..."
        elif not text:
            text = "[No response from agent]"

        render_lines = [text]
        if state["tools"]:
            render_lines.append("")
            for tool_name, status in state["tools"]:
                icon = "●" if status == "running" else "✓" if status == "success" else "✗"
                render_lines.append(f"{icon} {tool_name}: {status}")

        widget.set_message("\n".join(render_lines))
        self.query_one("#timeline", VerticalScroll).scroll_end(animate=False)

    def _new_assistant_row(self) -> str:
        self._assistant_counter += 1
        row_id = f"assistant-{self._assistant_counter}"
        row = MessageTextArea("", row_class="row-assistant", row_id=row_id)
        self.query_one("#timeline", VerticalScroll).mount(row)
        return row_id

    def _toggle_timeline_visibility(self) -> None:
        timeline = self.query_one("#timeline", VerticalScroll)
        has_content = bool(self.messages_history) or bool(self.turn_states)
        timeline.display = has_content
        if has_content:
            timeline.styles.height = "1fr"
            timeline.styles.min_height = 0
            timeline.styles.max_height = "100%"
        else:
            timeline.styles.height = 0
            timeline.styles.min_height = 0
            timeline.styles.max_height = 0

    def _append_user(self, message: str) -> None:
        widget = MessageTextArea(f"You: {message}", row_class="row-user")
        timeline = self.query_one("#timeline", VerticalScroll)
        timeline.display = True
        timeline.mount(widget)
        timeline.scroll_end(animate=False)
        self._toggle_timeline_visibility()

    def _append_system(self, message: str) -> None:
        widget = MessageTextArea(f"System: {message}", row_class="row-system")
        timeline = self.query_one("#timeline", VerticalScroll)
        timeline.display = True
        timeline.mount(widget)
        timeline.scroll_end(animate=False)
        self._toggle_timeline_visibility()

    def _append_error(self, message: str) -> None:
        widget = MessageTextArea(f"Error: {message}", row_class="row-error")
        timeline = self.query_one("#timeline", VerticalScroll)
        timeline.mount(widget)
        timeline.scroll_end(animate=False)

    def _copy_text_to_clipboard(self, text: str) -> bool:
        try:
            import pyperclip

            pyperclip.copy(text)
            return True
        except Exception:
            pass
        try:
            self.copy_to_clipboard(text)
            return True
        except Exception:
            return False

    def action_copy_selection(self) -> None:
        focused = self.focused
        if not isinstance(focused, TextArea):
            self.notify("コピーする選択範囲がありません。", severity="warning", markup=False)
            return
        selected_text = focused.selected_text
        if not selected_text.strip():
            self.notify("コピーする選択範囲がありません。", severity="warning", markup=False)
            return
        if self._copy_text_to_clipboard(selected_text):
            self.notify("選択範囲をコピーしました。", severity="information", markup=False)
            return
        self.notify("コピーに失敗しました。", severity="warning", markup=False)


def run() -> None:
    KraftTextualApp().run()
