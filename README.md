# kraft

Python ベースの CLI / エージェント実験プロジェクトです。
`DeepAgents` を中心に、ファイルアクセス、メモリ注入、スキル検索、HITL（Human In The Loop）承認を組み合わせた開発支援フローを提供します。

## 概要

- `DeepAgents` のミドルウェアを利用して、ファイル操作・メモリ参照・スキル読み込みを構成する
- ワークスペースを `KRAFT_WORKSPACE_ROOT` で固定し、安全にファイルを扱う
- `AGENTS.md` と `SKILL.md` を自動的に取り込み、LLM のコンテキストとして使う
- `bash` / `edit_file` / `grep_search` / `read_file` 系ツールの実行前に承認フローを挟む
- セッション単位で会話履歴を保存し、以前の状態へ再開できる

## 主要機能

### 1. DeepAgents ミドルウェア

`build_agent_app()` で以下を組み合わせます。

- `FilesystemMiddleware`
  - ファイル読み書き・検索・編集用ツールを提供
  - `KRAFT_WORKSPACE_ROOT` を root として制限
- `MemoryMiddleware`
  - `AGENTS.md` を読む
  - 記憶や作業方針をシステムプロンプトへ注入
- `SkillsMiddleware`
  - `KRAFT_SKILLS_DIR` または既定の `%USERPROFILE%\.claude\skills` を探索
  - `SKILL.md` を検出してスキル情報を読み込む

### 2. HITL 承認フロー

危険なツール実行の前に承認を求めます。`interrupt_on` の設定で、特に `bash` / `edit_file` を停止対象にし、UI には `approval/hitl_prompt.py` を使います。

### 3. セッション管理

`src/kraft/agent.py` の `SessionManager` が会話履歴を `~/.kraft/sessions/<session_id>/` に保存し、再開・一覧表示・タイトル生成を行います。

### 4. スキルの自動探索

- 既定スキルソース: `%USERPROFILE%\.claude\skills`
- 環境変数 `KRAFT_SKILLS_DIR` で上書き可能
- `discover_skills()` と `resolve_skills_dir()` で探索先を統一

## クイックスタート

### 依存関係を入れる

```bash
uv sync
```

### 環境変数を設定する

```bash
export OPENAI_API_KEY="your-api-key"
export KRAFT_WORKSPACE_ROOT="$(pwd)"
export KRAFT_SESSION_DIR="$HOME/.kraft/sessions"
export KRAFT_MEMORY_FILE="AGENTS.md"
export KRAFT_SKILLS_DIR="$HOME/.claude/skills"
export KRAFT_HITL_MODE="interactive"
```

Windows PowerShell では:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
$env:KRAFT_WORKSPACE_ROOT = "C:\path\to\workspace"
$env:KRAFT_SESSION_DIR = "$HOME\.kraft\sessions"
$env:KRAFT_MEMORY_FILE = "AGENTS.md"
$env:KRAFT_SKILLS_DIR = "$HOME\.claude\skills"
$env:KRAFT_HITL_MODE = "interactive"
```

### 実行

```bash
uv run kraft
```

起動時には、スキルソースとロード済みスキル数が表示されます。

## プロジェクト構成

```text
kraft/
├─ AGENTS.md
├─ README.md
├─ pyproject.toml
├─ src/
│  └─ kraft/
│     ├─ __init__.py
│     ├─ agent.py
│     ├─ deep_agents_hitl.py
│     ├─ display_formatter.py
│     ├─ approval/
│     │  ├─ __init__.py
│     │  ├─ hitl_prompt.py
│     │  ├─ tool_approval.py
│     │  └─ tool_config.py
│     └─ tools/
│        ├─ file_editor_wrapper.py
│        ├─ file_read_advanced.py
│        ├─ file_read_safe.py
│        ├─ grep_tool.py
│        ├─ hitl_wrapper.py
│        └─ tool_logging.py
├─ test/
│  ├─ conftest.py
│  └─ test_*.py
└─ uv.lock
```

## テスト

```bash
uv run pytest -q test
uv run pytest test/test_hitl_filesystem_integration.py -v
uv run pytest test/test_skill_search.py -v
```

個別に実行する場合は、以下のような検証を行います。

- `test_hitl_filesystem_integration.py`: ファイル操作と HITL 承認
- `test_hitl_multi_ai_message.py`: 複数メッセージの取り扱い
- `test_agent_deepagents_hitl.py`: DeepAgents と承認フローの連携
- `test_skill_search.py`: スキル検索と読み込み

## 重要な設計方針

- `KRAFT_WORKSPACE_ROOT` をファイルアクセスの基点にする
- `KRAFT_SESSION_DIR` でセッション履歴の保存先を切り替えられる
- `KRAFT_MEMORY_FILE` に指定したメモリファイルを AI に注入する
- 重要なツール実行は常に HITL 承認前提で行う
- README と AGENTS.md の説明内容は実装と一致させる

## 便利なコマンド

```bash
uv run kraft
uv run pytest -q test
uv run python test/test_tools.py
```

## 備考

- `bash` 実行は PowerShell を既定シェルとして扱います
- `edit_file` は組み込み版ではなく、差分表示付きのカスタムラッパーを優先します
- Windows 環境では文字コード差異や PowerShell 周りの挙動に注意してください


