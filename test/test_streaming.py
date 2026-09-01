from types import SimpleNamespace

from kraft.streaming import LiveStreamRenderer, StreamEvent, iter_stream_events
from kraft.tui.app import _expand_paste_refs


def test_iter_stream_events_extracts_message_and_tool_events():
    stream = [
        (SimpleNamespace(type="ai", content="hello ", tool_calls=[]), {"event": "one"}),
        (SimpleNamespace(type="tool", name="bash", content="done", tool_calls=[]), {"event": "two"}),
    ]

    events = list(iter_stream_events(stream))

    assert any(event.kind == "assistant_delta" and event.text == "hello " for event in events)
    assert any(event.kind == "tool_result" and event.tool_name == "bash" for event in events)
    assert events[-1].kind == "done"


def test_live_stream_renderer_tracks_stream_progress():
    renderer = LiveStreamRenderer()
    try:
        renderer.handle_event(StreamEvent(kind="assistant_delta", text="hello"))
        renderer.handle_event(StreamEvent(kind="tool_start", tool_name="grep_search"))
        assert renderer.assistant_text == "hello"
        assert renderer.tool_rows[-1][0] == "grep_search"
    finally:
        renderer.close()


def test_iter_stream_events_keeps_newline_chunks():
    stream = [
        (SimpleNamespace(type="ai", content="line1", tool_calls=[]), {"event": "one"}),
        (SimpleNamespace(type="ai", content="\n", tool_calls=[]), {"event": "two"}),
        (SimpleNamespace(type="ai", content="line2", tool_calls=[]), {"event": "three"}),
    ]

    events = list(iter_stream_events(stream))
    deltas = [event.text for event in events if event.kind == "assistant_delta"]
    assert deltas == ["line1", "\n", "line2"]


def test_expand_paste_refs_reconstructs_collapsed_multiline_paste():
    pasted = {7: "alpha\nbeta\ngamma"}
    text = "before [Pasted text #7 +2 lines] after"

    assert _expand_paste_refs(text, pasted) == "before alpha\nbeta\ngamma after"
