from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Any, Iterable, Iterator

from langchain_core.messages import AIMessageChunk, BaseMessage
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from .display_formatter import console as default_console


@dataclass
class StreamEvent:
    """UI に転送するための正規化済みイベント."""

    kind: str
    text: str = ""
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def _coerce_text(value: Any) -> str:
    """様々なメッセージ表現を安全に文字列へ変換する。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "".join(_coerce_text(item) for item in value)
    if isinstance(value, dict):
        for key in ("text", "content", "delta", "value"):
            if key in value:
                return _coerce_text(value[key])
        if "type" in value and value.get("type") == "text":
            return _coerce_text(value.get("text", ""))
        parts: list[str] = []
        for item in value.values():
            if isinstance(item, (str, int, float, bool)):
                parts.append(str(item))
            elif isinstance(item, (list, dict)):
                parts.append(_coerce_text(item))
        return "".join(parts)
    if hasattr(value, "content"):
        return _coerce_text(getattr(value, "content"))
    return str(value)


def _message_to_events(message: Any) -> Iterator[StreamEvent]:
    """LangChain / LangGraph のメッセージを UI イベントへ変換する。"""
    if message is None:
        return

    if isinstance(message, AIMessageChunk):
        content = _coerce_text(message.content)
        if content != "":
            yield StreamEvent(kind="assistant_delta", text=content)
        return

    if isinstance(message, BaseMessage):
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            for call in tool_calls or []:
                name = getattr(call, "name", None) or (call.get("name") if isinstance(call, dict) else None)
                args = getattr(call, "args", None) or (call.get("args") if isinstance(call, dict) else {})
                yield StreamEvent(
                    kind="tool_start",
                    tool_name=str(name) if name else "unknown_tool",
                    tool_args=args if isinstance(args, dict) else {"value": args},
                    text=str(name) if name else "tool call",
                )
        message_name = getattr(message, "name", None)
        content = _coerce_text(getattr(message, "content", ""))
        if content != "":
            if message_name and getattr(message, "type", "") == "tool":
                yield StreamEvent(kind="tool_result", tool_name=str(message_name), content=content)
            else:
                yield StreamEvent(kind="assistant_delta", text=content)
        return

    if isinstance(message, dict):
        if "tool_calls" in message:
            for call in message.get("tool_calls", []) or []:
                name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
                args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
                yield StreamEvent(
                    kind="tool_start",
                    tool_name=str(name) if name else "unknown_tool",
                    tool_args=args if isinstance(args, dict) else {"value": args},
                    text=str(name) if name else "tool call",
                )
        if "content" in message:
            content = _coerce_text(message.get("content"))
            if content != "":
                yield StreamEvent(kind="assistant_delta", text=content)
        if "name" in message and "content" in message:
            name = message.get("name")
            content = _coerce_text(message.get("content"))
            if name and content and not isinstance(message.get("content"), (list, dict)):
                yield StreamEvent(kind="tool_result", tool_name=str(name), content=content)
        return

    if hasattr(message, "tool_calls"):
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            for call in tool_calls or []:
                name = getattr(call, "name", None) or (call.get("name") if isinstance(call, dict) else None)
                args = getattr(call, "args", None) or (call.get("args") if isinstance(call, dict) else {})
                yield StreamEvent(
                    kind="tool_start",
                    tool_name=str(name) if name else "unknown_tool",
                    tool_args=args if isinstance(args, dict) else {"value": args},
                    text=str(name) if name else "tool call",
                )

    message_name = getattr(message, "name", None)
    content = _coerce_text(getattr(message, "content", ""))
    if content != "":
        if message_name and (getattr(message, "type", "") == "tool" or message_name == "bash"):
            yield StreamEvent(kind="tool_result", tool_name=str(message_name), content=content)
        else:
            yield StreamEvent(kind="assistant_delta", text=content)


def iter_stream_events(stream_output: Iterable[Any]) -> Iterator[StreamEvent]:
    """LangGraph の stream 結果から UI に流すイベントを生成する。"""
    for chunk in stream_output:
        if chunk is None:
            continue

        if isinstance(chunk, tuple):
            if len(chunk) == 2 and isinstance(chunk[1], dict):
                message, metadata = chunk
                if isinstance(message, dict) and "messages" in message:
                    for item in message["messages"]:
                        yield from _message_to_events(item)
                    continue
                if isinstance(message, (BaseMessage, AIMessageChunk)) or hasattr(message, "content"):
                    yield from _message_to_events(message)
                    continue
                if message:
                    yield from _message_to_events(message)
                    continue
                if "__interrupt__" in metadata:
                    yield StreamEvent(kind="interrupt", text=_coerce_text(metadata.get("__interrupt__")))
                    continue
            if len(chunk) >= 2 and chunk[0] is not None:
                chunk = chunk[0]

        if isinstance(chunk, dict):
            if "__interrupt__" in chunk:
                yield StreamEvent(kind="interrupt", text=_coerce_text(chunk.get("__interrupt__")))
                continue
            if "messages" in chunk:
                messages = chunk.get("messages") or []
                for message in messages:
                    yield from _message_to_events(message)
                continue
            if "output" in chunk and isinstance(chunk.get("output"), list):
                for message in chunk["output"]:
                    yield from _message_to_events(message)
                continue
            if "content" in chunk or "type" in chunk:
                yield from _message_to_events(chunk)
                continue

        yield from _message_to_events(chunk)

    yield StreamEvent(kind="done")


class LiveStreamRenderer:
    """Claude Code 風の逐次表示を行うシンプルな renderer."""

    def __init__(self, console: Any | None = None) -> None:
        self.console = console or default_console
        self.assistant_text = ""
        self.tool_rows: list[tuple[str, str]] = []
        self._thinking_frames = ("⠋", "⠙", "⠸", "⠴", "⠦", "⠇")
        self._thinking_index = 0
        self._stop_thinking = threading.Event()
        self.live = Live(self._render(), console=self.console, refresh_per_second=30, transient=False)
        self.live.start()
        self._thinking_thread = threading.Thread(target=self._thinking_loop, daemon=True)
        self._thinking_thread.start()

    def _append_chunked(self, text: str) -> None:
        """1チャンクが大きい場合でも段階的に描画する。"""
        if not self.assistant_text and text:
            self._stop_thinking.set()
        if len(text) <= 120:
            self.assistant_text += text
            self.live.update(self._render(), refresh=True)
            return

        step = 18
        for index in range(0, len(text), step):
            self.assistant_text += text[index:index + step]
            self.live.update(self._render(), refresh=True)
            time.sleep(0.008)

    def _thinking_loop(self) -> None:
        while not self._stop_thinking.wait(0.1):
            self._thinking_index = (self._thinking_index + 1) % len(self._thinking_frames)
            if self.assistant_text:
                self._stop_thinking.set()
                break
            self.live.update(self._render(), refresh=True)

    def _render(self) -> Panel:
        body: list[Any] = []
        if self.assistant_text:
            body.append(Text(self.assistant_text, style="bold cyan"))
        else:
            frame = self._thinking_frames[self._thinking_index]
            body.append(Text(f"{frame} AI が応答を構築しています...", style="dim"))

        if self.tool_rows:
            tool_lines = [Text("", style="dim")]
            for name, status in self.tool_rows:
                color = "yellow" if status == "running" else "green" if status == "success" else "red"
                icon = "●" if status == "running" else "✓" if status == "success" else "✗"
                tool_lines.append(Text(f"{icon} {name}: {status}", style=f"bold {color}"))
            body.extend(tool_lines)

        return Panel(
            Group(*body),
            title="[bold]Live Agent Stream[/bold]",
            border_style="cyan",
            padding=(1, 1),
        )

    def handle_event(self, event: StreamEvent) -> None:
        if event.kind == "assistant_delta":
            self._append_chunked(event.text)
        elif event.kind == "tool_start":
            self.tool_rows.append((event.tool_name or "tool", "running"))
        elif event.kind == "tool_result":
            if self.tool_rows:
                name = event.tool_name or self.tool_rows[-1][0]
                self.tool_rows = [(n, "success" if n == name and "error" not in str(event.content).lower() else "error") for n, _ in self.tool_rows]
                for idx, (n, _) in enumerate(self.tool_rows):
                    if n == name:
                        self.tool_rows[idx] = (n, "success" if "error" not in str(event.content).lower() else "error")
                        break
        elif event.kind == "interrupt":
            self.assistant_text += "\n[HITL approval required]"
        self.live.update(self._render(), refresh=True)

    def close(self) -> None:
        self._stop_thinking.set()
        if hasattr(self, "_thinking_thread") and self._thinking_thread.is_alive():
            self._thinking_thread.join(timeout=0.3)
        if self.live is not None:
            self.live.stop()
            self.live = None


__all__ = [
    "LiveStreamRenderer",
    "StreamEvent",
    "iter_stream_events",
]
