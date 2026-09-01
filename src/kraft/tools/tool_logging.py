"""ツール実行ログの共通ヘルパー."""

from __future__ import annotations

from datetime import datetime
from functools import wraps
import sys
import traceback
import time
from typing import Any, Callable, Iterable

from rich.console import Console
from rich.text import Text


# stdout キャプチャの影響を受けないよう、raw stdout に出力する Rich Console
_console = Console(file=sys.__stdout__, force_terminal=True)

# ツール実行開始時刻を記録（実行時間計測用）
_tool_start_times: dict[str, float] = {}


def _get_timestamp() -> str:
    """現在時刻を ISO 8601 形式で取得."""
    return datetime.now().isoformat(timespec="milliseconds")


def log_tool_start(tool_name: str, kwargs_dict: dict[str, Any] | None = None) -> None:
    """ツール実行開始をログ出力.
    
    Args:
        tool_name: ツール名
        kwargs_dict: 重要なキーワード引数
    """
    # 開始時刻を記録（実行時間計測用）
    _tool_start_times[tool_name] = time.time()
    
    ts = _get_timestamp()
    msg = f"[{ts}] [assistant] 🔎 {tool_name} を実行中"
    if kwargs_dict:
        msg += f" (args: {kwargs_dict})"
    try:
        _console.print(Text(msg, style="dim cyan"))
    except Exception:
        try:
            sys.__stdout__.write(msg + "\n")
            sys.__stdout__.flush()
        except Exception:
            print(msg)


def log_tool_success(tool_name: str, result_type: str | None = None) -> None:
    """ツール実行成功をログ出力.
    
    Args:
        tool_name: ツール名
        result_type: 戻り値の型名（例: 'str', 'dict', 'list'）
    """
    ts = _get_timestamp()
    
    # 実行時間を計算
    duration_ms = None
    if tool_name in _tool_start_times:
        elapsed = (time.time() - _tool_start_times.pop(tool_name)) * 1000
        duration_ms = elapsed
    
    msg = f"[{ts}] [assistant] ✓ {tool_name} が完了"
    if result_type:
        msg += f" ({result_type})"
    if duration_ms is not None:
        msg += f" | {duration_ms:.1f}ms"
    
    try:
        _console.print(Text(msg, style="dim green"))
    except Exception:
        try:
            sys.__stdout__.write(msg + "\n")
            sys.__stdout__.flush()
        except Exception:
            print(msg)


def log_tool_error(tool_name: str, error: Exception, include_trace: bool = True) -> None:
    """ツール実行エラーをログ出力.
    
    Args:
        tool_name: ツール名
        error: 例外
        include_trace: トレース情報を含めるか（デバッグ用）
    """
    ts = _get_timestamp()
    
    # 実行時間を計算
    duration_ms = None
    if tool_name in _tool_start_times:
        elapsed = (time.time() - _tool_start_times.pop(tool_name)) * 1000
        duration_ms = elapsed
    
    msg = f"[{ts}] !!! {tool_name} (ERROR: {error.__class__.__name__}: {error}"
    if duration_ms is not None:
        msg += f" | {duration_ms:.1f}ms"
    msg += ")"
    
    try:
        _console.print(Text(msg, style="dim red"))
        if include_trace:
            trace = traceback.format_exc()
            _console.print(Text(trace, style="dim"))
    except Exception:
        try:
            sys.__stdout__.write(msg + "\n")
            if include_trace:
                sys.__stdout__.write(traceback.format_exc() + "\n")
            sys.__stdout__.flush()
        except Exception:
            print(msg)
            if include_trace:
                print(traceback.format_exc())


def log_tool_event(message: str) -> None:
    """stdout キャプチャの影響を受けないよう直接ログ出力する（Rich で dim スタイル）."""
    try:
        # Rich を使って dim（グレー）スタイルで出力
        _console.print(Text(message, style="dim"))
    except Exception:
        # フォールバック
        try:
            sys.__stdout__.write(message + "\n")
            sys.__stdout__.flush()
        except Exception:
            print(message)


def tool_logging_hook(
    tool_name: str | None = None,
    include_kwargs: Iterable[str] | None = None,
    include_trace: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """ツール関数に開始/終了/例外ログを付与するデコレータ.

    Args:
        tool_name: ログに表示するツール名（未指定時は関数名）.
        include_kwargs: 開始ログに含めるキーワード引数名.
        include_trace: エラー時にトレース情報を含めるか.
    """

    include_kwargs_set = set(include_kwargs or [])

    def _decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        name = tool_name or func.__name__

        @wraps(func)
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            # 開始ログ
            kwargs_to_log = {k: v for k, v in kwargs.items() if k in include_kwargs_set}
            log_tool_start(name, kwargs_to_log if kwargs_to_log else None)

            try:
                # 関数実行
                result = func(*args, **kwargs)

                # 成功ログ
                result_type = type(result).__name__
                log_tool_success(name, result_type)
                return result
            except Exception as e:
                # 例外ログ
                log_tool_error(name, e, include_trace=include_trace)
                raise

        return _wrapper

    return _decorate
