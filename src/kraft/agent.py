# OpenTelemetry コンテキスト問題を Windows 環境で回避
import os
os.environ["OTEL_SDK_DISABLED"] = "true"

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from deepagents import create_deep_agent
from deepagents.backends import StateBackend, CompositeBackend
from deepagents.backends.filesystem import FilesystemBackend
from deepagents.middleware import MemoryMiddleware, SkillsMiddleware, FilesystemMiddleware
from kraft.tools import file_read, file_read_advanced, grep_search
from kraft.tools.file_editor_wrapper import edit_file  # DeepAgents の edit_file と同名で差分表示を強制
import subprocess
import sys
from pathlib import Path
from typing import Optional, Any
import json
from datetime import datetime
import time
import uuid


DEFAULT_SKILLS_DIR = Path.home() / ".claude" / "skills"


def repo_local_skill_dirs() -> list[Path]:
    """repo-local なスキルディレクトリを優先順で返す。

    優先順位は次の通り:
    1. .kraft/skills
    2. skills
    3. ~/.claude/skills（グローバル既定値）
    """
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        repo_root / ".kraft" / "skills",
        repo_root / "skills",
        DEFAULT_SKILLS_DIR,
    ]
    return [candidate.resolve() for candidate in candidates]


def normalize_text(text: str) -> str:
    """サロゲートペアを正規化して、安全な UTF-8 文字列に変換。"""
    try:
        return text.encode("utf-8", errors="replace").decode("utf-8")
    except Exception:
        return text


def extract_skill_description(content: str) -> str:
    """SKILL.md の冒頭から説明文を抽出する。"""
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    for line in lines:
        if line.startswith("#"):
            continue
        if line.startswith("-") or line.startswith("*"):
            continue
        if line.startswith("##") or line.startswith("###"):
            continue
        if not line:
            continue
        return line[:200]
    return "スキル説明なし"


def resolve_skills_dir() -> Path:
    """スキルソースディレクトリを解決する。

    環境変数が明示されている場合はその値を最優先し、
    未設定時は repo-local の .kraft/skills / skills を優先して探索する。
    """
    configured = os.environ.get("KRAFT_SKILLS_DIR")
    if configured:
        return Path(configured).expanduser().resolve()

    for candidate in repo_local_skill_dirs():
        if candidate.exists():
            return candidate.resolve()
    return DEFAULT_SKILLS_DIR.resolve()


def discover_skills(skills_dir: Optional[Path] = None) -> dict[str, dict[str, str]]:
    """SKILL.md を持つスキルを走査して返す。

    repo-local の skill を既定の user-global skill より優先し、
    競合名がある場合は repo-local 側で上書きする。
    """
    if skills_dir is not None:
        target_dirs = [skills_dir.resolve()]
    else:
        configured = os.environ.get("KRAFT_SKILLS_DIR")
        if configured:
            target_dirs = [Path(configured).expanduser().resolve()]
        else:
            repo_local_candidates = [
                candidate.resolve()
                for candidate in repo_local_skill_dirs()[:-1]
                if candidate.exists()
            ]
            target_dirs = [DEFAULT_SKILLS_DIR.resolve(), *repo_local_candidates]

    discovered: dict[str, dict[str, str]] = {}
    for target_dir in target_dirs:
        if not target_dir.exists():
            continue
        for skill_dir in sorted(target_dir.iterdir(), key=lambda p: p.name):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            try:
                content = skill_file.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
            discovered[skill_dir.name] = {
                "description": normalize_text(extract_skill_description(content)),
                "instructions": normalize_text(content),
            }
    return discovered


def list_all_skills() -> list[tuple[str, str]]:
    """全スキルを (name, description) で返す。"""
    return [(name, data["description"]) for name, data in discover_skills().items()]


def search_skills(keyword: str) -> list[tuple[str, str]]:
    """キーワードでスキルを検索し、スコア順で返す。"""
    keyword_lower = keyword.lower()
    results: dict[str, tuple[int, str]] = {}
    for name, data in discover_skills().items():
        score = 0
        description = data["description"]
        if keyword_lower in name.lower():
            score += 3
        if keyword_lower in description.lower():
            score += 1
        if score > 0:
            results[name] = (score, description)
    sorted_results = sorted(results.items(), key=lambda x: x[1][0], reverse=True)
    return [(name, desc) for name, (_, desc) in sorted_results]


def get_skill_instructions(skill_name: str) -> Optional[str]:
    """指定したスキルの全文を取得する。"""
    skill = discover_skills().get(skill_name)
    return skill["instructions"] if skill else None


# ============================================================================
# セッション管理エンジン（チャット履歴の保存・復元）
# ============================================================================

class SessionManager:
    """
    チャット履歴をファイルに保存・復元するセッション管理。
    
    ディレクトリ構造:
      ~/.kraft/sessions/
        {session_id}/
          metadata.json  (セッション名、作成日時など)
          messages.json  (チャット履歴)
    """

    @staticmethod
    def summarize_title_from_messages(messages: list[dict]) -> str:
        """メッセージ一覧からセッションタイトル候補を生成する。

        最初のユーザーメッセージを優先し、改行・重複空白を整理して
        32〜40 文字程度に収める。
        """
        for message in messages:
            role = str(message.get("role", "")).lower()
            content = message.get("content", "")
            if role != "user" or not content:
                continue

            text = str(content).strip()
            text = " ".join(text.replace("\r", "\n").split())
            text = text.replace("\n", " ")
            text = text.strip(" \t\n\r-_|[](){}<>[]")
            if not text:
                continue

            if len(text) > 32:
                text = text[:31].rstrip() + "…"
            return text

        return "新規セッション"
    
    def __init__(self, sessions_dir: Optional[str] = None):
        """
        セッションディレクトリを初期化。
        
        Args:
            sessions_dir: セッションディレクトリのパス。
                         省略時は %USERPROFILE%\.kraft\sessions を使用。
                         ただし環境変数 KRAFT_SESSION_DIR があればそれを優先する。
        """
        if sessions_dir is None:
            sessions_dir = os.environ.get(
                "KRAFT_SESSION_DIR",
                str(Path.home() / ".kraft" / "sessions"),
            )
        sessions_dir = Path(sessions_dir)
        
        self.sessions_dir = sessions_dir.resolve()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
    
    def create_session(self, title: Optional[str] = None) -> str:
        """
        新しいセッションを作成。
        
        Args:
            title: セッションタイトル。省略時は自動生成。
        
        Returns:
            セッションID
        """
        session_id = str(uuid.uuid4())[:8]  # 短い ID（最初の8文字）
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # メタデータを保存
        metadata = {
            "session_id": session_id,
            "title": title or f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self._save_metadata(session_id, metadata)
        
        # 空のメッセージ履歴を作成
        self._save_messages(session_id, [])
        
        return session_id
    
    def list_sessions(self) -> list[dict]:
        """
        すべてのセッションを一覧で取得。
        
        Returns:
            セッション情報のリスト（タイトル、作成日時など）
        """
        sessions = []
        for session_dir in sorted(self.sessions_dir.iterdir()):
            if session_dir.is_dir():
                metadata_path = session_dir / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                            sessions.append(metadata)
                    except Exception:
                        pass
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
    
    @staticmethod
    def format_history_preview(messages: list[dict], max_entries: int = 20) -> str:
        """簡易な履歴プレビューを生成する。

        ユーザーと AI の発話を区別しながら、会話の流れを目で追えるようにする。
        なお、セッション選択番号のような入力は履歴として扱わない。
        """
        if not messages:
            return "(履歴なし)"

        lines: list[str] = []
        for entry_index, message in enumerate(messages[-max_entries:], start=max(1, len(messages) - max_entries + 1)):
            role = str(message.get("role", "unknown")).lower()
            content = str(message.get("content", "")).strip()
            if not content:
                continue

            if role == "user" and content.isdigit() and len(content) <= 2:
                continue

            label = "ユーザー" if role == "user" else "AI" if role == "assistant" else "システム"
            preview = " ".join(content.split())
            if len(preview) > 100:
                preview = preview[:97].rstrip() + "..."
            lines.append(f"[{entry_index}] {label}: {preview}")
        return "\n".join(lines) if lines else "(履歴なし)"

    def get_session_title(self, session_id: str) -> Optional[str]:
        """セッションのタイトルを取得。既存タイトルが自動生成形式なら再評価する。"""
        metadata = self._load_metadata(session_id)
        if not metadata:
            return None

        title = metadata.get("title")
        messages = self.load_messages(session_id)
        if not messages:
            return title

        auto_title = self.summarize_title_from_messages(messages)
        if title is None or title.startswith("Session ") or title == "新規セッション":
            metadata["title"] = auto_title
            metadata["updated_at"] = datetime.now().isoformat()
            self._save_metadata(session_id, metadata)
            return auto_title
        return title
    
    def load_messages(self, session_id: str) -> list[dict]:
        """
        セッションのチャット履歴を読み込み。
        
        Args:
            session_id: セッションID
        
        Returns:
            メッセージリスト
        """
        return self._load_messages(session_id) or []
    
    def save_messages(self, session_id: str, messages: list[dict]) -> None:
        """
        チャット履歴を保存。
        
        Args:
            session_id: セッションID
            messages: メッセージリスト
        """
        self._save_messages(session_id, messages)

        # 最初のユーザー発話からタイトルを自動更新
        metadata = self._load_metadata(session_id)
        if metadata is not None:
            generated_title = self.summarize_title_from_messages(messages)
            metadata["title"] = generated_title
            metadata["updated_at"] = datetime.now().isoformat()
            self._save_metadata(session_id, metadata)
    
    def delete_session(self, session_id: str) -> None:
        """セッションを削除。"""
        import shutil
        session_dir = self.sessions_dir / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)
    
    def _save_metadata(self, session_id: str, metadata: dict) -> None:
        """メタデータをファイルに保存。"""
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = session_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def _load_metadata(self, session_id: str) -> Optional[dict]:
        """メタデータをファイルから読み込み。"""
        session_dir = self.sessions_dir / session_id
        metadata_path = session_dir / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None
    
    def _save_messages(self, session_id: str, messages: list[dict]) -> None:
        """メッセージをファイルに保存。"""
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        messages_path = session_dir / "messages.json"
        with open(messages_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    
    def _load_messages(self, session_id: str) -> Optional[list[dict]]:
        """メッセージをファイルから読み込み。"""
        session_dir = self.sessions_dir / session_id
        messages_path = session_dir / "messages.json"
        if messages_path.exists():
            try:
                with open(messages_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None


# セッションマネージャーのシングルトンインスタンス
session_manager = SessionManager()




def read_skill(skill_name: str) -> str:
    """
    指定したスキルの詳細説明を読み込む。
    
    Args:
        skill_name: スキル名（例: "pc-boot-shutdown-times"）
    
    Returns:
        スキルの詳細説明、またはエラーメッセージ
    """
    instructions = get_skill_instructions(skill_name)
    if instructions:
        return f"### {skill_name}\n\n{instructions}"
    return f"[NG] スキル '{skill_name}' が見つかりません。"


def letter_counter(word: str, letter: str) -> int:
    """
    単語内の特定の文字の出現回数を数える。

    Args:
        word (str): 検索対象の単語
        letter (str): 数える対象の文字

    Returns:
        int: 単語内における文字の出現回数
    """
    if not isinstance(word, str) or not isinstance(letter, str):
        return 0

    if len(letter) != 1:
        raise ValueError("'letter' パラメータは単一の文字である必要があります")

    return word.lower().count(letter.lower())


def bash(command: str, shell: str = "powershell") -> str:
    """
    Windows PowerShell または Git Bash でコマンドを実行する。

    実行中の標準出力をターミナルへ流し、ユーザーが何を実行しているか
    確認できるようにする。ただし最終的な戻り値としては、実行結果文字列
    をそのまま返す。

    Args:
        command: 実行するコマンド文字列
        shell: 実行シェル。"powershell" (デフォルト) または "gitbash"

    Returns:
        コマンド実行結果の標準出力、またはエラーメッセージ
    """
    try:
        # シェルの選択
        if shell.lower() == "gitbash":
            # Git Bash で実行
            cmd = [r"C:\Program Files\Git\bin\bash.exe", "-lc", command]
            encoding = "utf-8"
        elif shell.lower() == "powershell":
            # PowerShell で実行（デフォルト）
            cmd = ["powershell", "-NoProfile", "-Command", command]
            encoding = "utf-8"
        else:
            return f"[NG] 不明なシェル: {shell}。'powershell' または 'gitbash' を指定してください"

        print(f"$ {command}")
        sys.stdout.flush()

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding=encoding,
            errors="replace",
            bufsize=1,
        )

        if process.stdout is None:
            return "[NG] コマンドの標準出力を取得できませんでした"

        output_chunks: list[str] = []
        deadline = time.monotonic() + 30
        while True:
            chunk = process.stdout.readline()
            if chunk:
                sys.stdout.write(chunk)
                sys.stdout.flush()
                output_chunks.append(chunk)
                continue

            if process.poll() is not None:
                break

            if time.monotonic() >= deadline:
                process.kill()
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=30)

            time.sleep(0.05)

        returncode = process.wait()
        output_text = "".join(output_chunks).strip()

        if returncode == 0:
            return output_text if output_text else "[OK] コマンドが正常に実行されました"

        error_msg = output_text
        return f"[NG] エラー (終了コード {returncode}):\n{error_msg}"

    except subprocess.TimeoutExpired:
        return "[NG] コマンド実行がタイムアウトしました（30秒）"
    except Exception as e:
        return f"[NG] 予期しないエラー: {str(e)}"


model = ChatOpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    model="gpt-4o-mini",
    temperature=0.7,
)

# システムプロンプト（簡潔版）
# MemoryMiddleware、SkillsMiddleware、FilesystemMiddleware により、
# 以下が自動的にプロンプトに注入されるため、基本指示のみを記載:
# - AGENTS.md 内容（MemoryMiddleware）
# - skills/ 配下の SKILL.md 一覧（SkillsMiddleware）
# - ファイルシステムツール情報（FilesystemMiddleware）
system_prompt = """
あなたは有能なアシスタントです。
以下の原則に従ってユーザーのリクエストをサポートしてください:

## 基本方針

1. **メモリ・スキルの活用**
   - AGENTS.md に記載された記憶と好みを常に参考にしてください
   - 利用可能なスキル（SKILL.md）を確認し、必要な操作を実行してください

2. **ツールの活用**
   - read_skill() でスキルの詳細を取得
   - bash() でコマンド実行（実際に実行してください、提示だけでなく）
   - file_editor() でファイル操作
   - file_read()、file_read_advanced()、grep_search() で検索・分析

3. **実行の原則**
   - コマンドを「提示する」だけでなく、bash() で「実際に実行」してください
   - 長い出力は自動的に省略されるため、重要な情報を最初に返してください
   - トークン効率を意識し、edit_line、edit_range、edit_regex を活用してください

## 出力フォーマット

ユーザーのリクエストに応じてコードを生成する場合は、必ず markdown コードブロックで返してください:

\`\`\`言語名
... コード ...
\`\`\`

対応言語: java, python, javascript, typescript, csharp, go, rust, sql, bash, powershell など
"""

# ファイルシステムバックエンド設定（エージェントのファイル操作を安全に制限）
# ワークスペースの正本はカレントディレクトリに置き、
# %USERPROFILE%\.kraft はセッション履歴や内部メタデータ専用にする。
WORKSPACE_DIR = Path(
    os.environ.get("KRAFT_WORKSPACE_ROOT", str(Path.cwd()))
).resolve()
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

def build_filesystem_middleware(backend: Any | None = None) -> FilesystemMiddleware:
    """DeepAgents の組み込み `edit_file` を非表示にして、カスタム diff 版を優先する。

    `create_deep_agent` は `tools=` に同名のカスタムツールを追加しても、
    FilesystemMiddleware が既定で `edit_file` を含めるため、モデル側に
    組み込み版が残ってしまう。ここでは `tools=[...]` の allowlist で
    builtin の `edit_file` を除外し、ユーザー定義の `edit_file` を実際に
    利用可能にする。
    """
    allowed_fs_tools = [
        "ls",
        "read_file",
        "write_file",
        "delete",
        "glob",
        "grep",
    ]
    resolved_backend = backend if backend is not None else StateBackend()
    return FilesystemMiddleware(backend=resolved_backend, tools=allowed_fs_tools)


# DeepAgents ベースのエージェントビルダー
def build_agent_app() -> tuple[Any, dict[str, Any]]:
    """Deep Agent を生成して、HITL 設定付きで返す.
    
    ミドルウェアを組み込んで、以下を自動管理する:
    - FilesystemMiddleware: ワークスペースのファイル操作
    - MemoryMiddleware: AGENTS.md の記憶・プロンプト常駐
    - SkillsMiddleware: skills/ ディレクトリ配下の SKILL.md スキル一覧注入

    Returns:
        (app, config) のタプル
        - app: コンパイル済みの LangGraph
        - config: stream() 用の設定辞書（thread_id を含む）
    """
    checkpointer = MemorySaver()
    
    # ============================================================================
    # バックエンド構成：StateBackend をベースに、CompositeBackend で拡張
    # ============================================================================
    # StateBackend（インメモリ）をメイン
    state_backend = StateBackend()
    
    # CompositeBackend でファイルシステムバックエンドを割り当て
    # root_dir を WORKSPACE_DIR に設定して、ファイル操作を安全に制限
    file_backend = FilesystemBackend(root_dir=WORKSPACE_DIR)
    
    # CompositeBackend で複数バックエンドを組み合わせ
    backend = CompositeBackend(
        default=state_backend,  # ルート指定がない場合は StateBackend
        routes={
            "/": file_backend,  # デフォルトルートはファイルシステム
        },
    )
    
    # ============================================================================
    # ミドルウェア構成：順序が重要（FilesystemMiddleware → MemoryMiddleware → SkillsMiddleware）
    # ============================================================================
    # MemoryMiddleware 用ファイルパス（環境変数で上書き可能、デフォルトは AGENTS.md）
    memory_file_path = os.environ.get("KRAFT_MEMORY_FILE", "AGENTS.md")
    
    # SkillsMiddleware 用スキルディレクトリ（環境変数で上書き可能、デフォルトは %USERPROFILE%/.claude/skills）
    skills_dir = str(resolve_skills_dir())
    
    middlewares = [
        # 組み込みの edit_file を非表示にして、カスタム diff 表示版を優先する
        build_filesystem_middleware(backend),
        
        # AGENTS.md（またはカスタムファイル）を常に読み込み、システムプロンプトに常駐させる
        MemoryMiddleware(backend=backend, sources=[memory_file_path]),
        
        # skills/ ディレクトリ配下の SKILL.md 群からメタ情報を読み込んで
        # プロンプトにスキル一覧として注入する
        SkillsMiddleware(backend=backend, sources=[skills_dir]),
    ]
    
    # ============================================================================
    # エージェント生成：ミドルウェアとバックエンドを統合
    # ============================================================================
    app = create_deep_agent(
        model=model,
        tools=[read_skill, bash, edit_file, file_read, file_read_advanced, grep_search],
        backend=backend,  # CompositeBackend をセット
        middleware=middlewares,  # ミドルウェアチェーンをセット
        system_prompt=system_prompt,  # 既存の system_prompt を保持（ミドルウェアが追記）
        interrupt_on={
            "bash": True,        # bash コマンドは承認待ち
            "write_file": True,  # ファイル新規作成は承認待ち
            "edit_file": True,   # ファイル一部編集は承認待ち
            "read_file": False,  # ファイル読み込みは安全なので即時実行
        },
        checkpointer=checkpointer,
    )
    
    config = {"configurable": {"thread_id": "kraft_main_agent"}}
    return app, config


# レガシー互換性のため、元の agent 変数を作成
try:
    agent, _ = build_agent_app()
except Exception as e:
    print(f"[WARNING] DeepAgents initialization failed: {e}")
    # フォールバック: 簡易的なダミーエージェント
    agent = None

# エージェントのエクスポート（__init__.py から使用）
__all__ = [
    "agent",
    "build_agent_app",
    "session_manager",
    "WORKSPACE_DIR",
    "resolve_skills_dir",
    "discover_skills",
    "list_all_skills",
    "search_skills",
]


