# kraft

Python ベースの CLI/エージェント実験用プロジェクトです。DeepAgents ミドルウェアを中心に、スキル検索・ツール呼び出し・HITL 承認を扱えるようにしています。

## 概要

- **DeepAgents ミドルウェア統合**: FilesystemMiddleware、MemoryMiddleware、SkillsMiddleware により、ファイル操作・エージェントメモリ・スキル管理を自動化
- **マルチバックエンド**: StateBackend（メモリ） + FilesystemBackend（ファイルI/O） を CompositeBackend で統合
- **スキルソース一本化**: デフォルトは `%USERPROFILE%\.claude\skills`、`KRAFT_SKILLS_DIR` で上書き可能
- スキルを自動ロードして LLM に提供する
- `bash`、`file_editor`、`grep_search` などのツールを組み込む
- DeepAgents の `interrupt_on` による承認フローを利用する
- ワークスペースはカレントディレクトリを基準にし、ユーザー作業ファイルはそこに置く
- `%USERPROFILE%\.kraft` はセッション履歴やメタデータ用に使用する

## 主要機能

### 1. DeepAgents ミドルウェアシステム

エージェント初期化時に 3 つのミドルウェアを自動構成:

#### FilesystemMiddleware
- ファイルシステム操作ツール (`ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`) を自動提供
- `backend` パラメータで CompositeBackend と連携
- ファイルアクセスは root_dir（KRAFT_WORKSPACE_ROOT）に制限

#### MemoryMiddleware
- `AGENTS.md` またはカスタムメモリファイルを読み込み、システムプロンプトに自動注入
- `KRAFT_MEMORY_FILE` で上書き可能（デフォルト: `"AGENTS.md"`）
- エージェントメモリ機能を提供

#### SkillsMiddleware
- デフォルトでは `%USERPROFILE%\.claude\skills` をスキルソースとして利用
- `KRAFT_SKILLS_DIR` が設定されていると、それを優先して読み込み
- `SKILL.md` を自動探索し、スキルメタデータをシステムプロンプトに常駐化
- 起動時に読み込まれたスキルの一覧を表示可能

> `SkillManager` は後方互換のため残していますが、現在の実装ではスキルの実体は `SkillsMiddleware` と同じソース解決に統一されています。

### 1.5 スキル管理（統一ソース方式）

スキルの検索・列挙・表示は `SkillsMiddleware` のソース解決に統一されており、起動時に読み込まれたスキル一覧をそのまま利用できます。

- 既定スキルソース: `%USERPROFILE%\.claude\skills`
- 上書き: `KRAFT_SKILLS_DIR`
- 提供機能:
  - スキル一覧表示
  - 検索
  - 詳細取得
  - LLM プロンプトへの自動コンテキスト注入

### 2. ツール群

実装済みの主要ツール:

- `read_skill(skill_name)`
- `bash(command, shell="powershell")`
- `file_editor(operation)`
- `grep_search(pattern, path=".", recursive=True, case_sensitive=False, max_results=20)`
- `file_read(...)`
- `file_read_advanced(...)`

### 3. DeepAgents + HITL

`build_agent_app()` で DeepAgents を生成し、次のように承認対象を設定しています。

```python
interrupt_on={
    "bash": True,
    "write_file": True,
    "edit_file": True,
    "read_file": False,
}
```

承認はミドルウェア側で行い、見た目は `src/kraft/approval/hitl_prompt.py` の UI を使って表示します。

### 4. バックエンド構成

マルチバックエンド設定により、異なる種類のデータストレージを統合:

```python
# メモリストレージ（エージェント状態用）
state_backend = StateBackend()

# ファイルシステムストレージ（WORKSPACE_DIR に制限）
file_backend = FilesystemBackend(root_dir=WORKSPACE_DIR)

# ルーティングバックエンド（複数バックエンドを統合）
backend = CompositeBackend(
    default=state_backend,
    routes={"/": file_backend}
)
```

この構成により、ファイル操作は WORKSPACE_DIR 内に安全に制限されます。

### 5. ワークスペース方針

実装上の基準は次のとおりです。

- ワークスペースの正本: カレントディレクトリ
- `KRAFT_WORKSPACE_ROOT` があればそれを優先（FilesystemBackend の root_dir）
- `%USERPROFILE%\.kraft`: セッション履歴・メタデータ専用
- `KRAFT_SESSION_DIR`: セッション保存先を上書き可能

```powershell
$env:KRAFT_WORKSPACE_ROOT = "C:\path\to\workspace"
$env:KRAFT_SESSION_DIR = "$HOME\.kraft\sessions"
$env:KRAFT_MEMORY_FILE = "AGENTS.md"
$env:KRAFT_SKILLS_DIR = "skills"
```

## 実行方法

### 依存環境

```bash
uv sync
```

### 環境変数設定

#### LLM 接続
```powershell
$env:OPENAI_API_KEY = "your-api-key"
```

#### ワークスペース設定
```powershell
# ファイル操作のルートディレクトリ（省略時: カレント）
$env:KRAFT_WORKSPACE_ROOT = "C:\path\to\workspace"

# セッション履歴の保存先（省略時: $HOME\.kraft\sessions）
$env:KRAFT_SESSION_DIR = "$HOME\.kraft\sessions"

# エージェントメモリファイル（MemoryMiddleware が読込、省略時: "AGENTS.md"）
$env:KRAFT_MEMORY_FILE = "AGENTS.md"

# スキルディレクトリ（SkillsMiddleware が読込、省略時: "$HOME\.claude\skills"）
$env:KRAFT_SKILLS_DIR = "$HOME\.claude\skills"

# HITL 動作モード（auto / interactive / strict、省略時: interactive）
$env:KRAFT_HITL_MODE = "interactive"
```

### 実行

```bash
uv run kraft
```

## テスト

テストは [test](test) ディレクトリへ整理されています。

```bash
# 全テスト実行
uv run pytest -q test

# 特定のテストモジュール実行
uv run pytest test/test_hitl_filesystem_integration.py -v
uv run pytest test/test_agent_deepagents_hitl.py -v
uv run pytest test/test_skill_search.py -v
```

現在の確認済み結果（DeepAgents ミドルウェア統合後）:

- **11/11 PASSED** (ミドルウェア統合テスト)
  - test_hitl_filesystem_integration.py: 2/2 PASSED
  - test_hitl_multi_ai_message.py: 1/1 PASSED
  - test_agent_deepagents_hitl.py: 2/2 PASSED
  - test_skill_search.py: 6/6 PASSED
- 0 failed

### 動作確認

```bash
# スキル読込・エージェント初期化の検証
uv run python test/test_tools.py
```

起動時には次の情報が表示されます。

```text
スキルソース: C:\Users\<user>\.claude\skills
ロード済みスキル数: 1
スキル: pc-boot-shutdown-times
```

この表示は `discover_skills()` と `resolve_skills_dir()` を使って実際の読み込みソースに基づいて出力されます。

## プロジェクト構造

```text
kraft/
├─ pyproject.toml
├─ README.md
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
└─ .venv/
```

## 実装ハイライト

### DeepAgents ミドルウェアアーキテクチャ

- **モジュール化**: FilesystemMiddleware、MemoryMiddleware、SkillsMiddleware により関心の分離を実現
- **自動コンテキスト注入**: AGENTS.md と skills/ ディレクトリの内容が自動的にシステムプロンプトに統合
- **マルチバックエンド**: CompositeBackend により、メモリとファイルシステムを透過的に組み合わせ
- **安全なファイルアクセス**: FilesystemBackend の root_dir 制限により、ワークスペース内のアクセスのみ許可

### 従来との主な違い

| 項目 | 従来（v0） | 現在（ミドルウェア対応） |
|---|---|---|
| ファイルツール | 手動登録 | FilesystemMiddleware で自動提供 |
| スキル読込 | SkillManager.load() で手動 | SkillsMiddleware が自動読込 + 既定は %USERPROFILE%\.claude\skills |
| エージェントメモリ | なし | MemoryMiddleware で AGENTS.md 読込 |
| バックエンド | StateBackend のみ | CompositeBackend で統合 |
| システムプロンプト | ~250行（手動構築） | ~50行（ミドルウェアが注入） |
| 起動時表示 | なし | スキルソースとロード済みスキルを出力 |

## 備考

- Windows 環境ではコマンド出力の文字コード差異に注意する
- HITL 承認は、標準の interrupt/resume フローを中心にしつつ、見た目は `hitl_prompt.py` を使う構成にしている
- DeepAgents API はドキュメントと実装に乖離がある場合があるため、ソースコード検証が必須（参考: backends/composite.py, middleware/*.py）

## ファイル構成の詳細

### エージェント層 (`src/kraft/`)

- **agent.py**: メインエージェント工場
  - `resolve_skills_dir()`: スキルソースを解決する共通関数
  - `discover_skills()`: 実際に読み込むスキル一覧を返す
  - `SessionManager`: セッション履歴管理
  - `build_agent_app()`: DeepAgents ミドルウェア統合エージェント生成
  - ツール関数群: bash, file_editor, file_read, file_read_advanced, grep_search

- **deep_agents_hitl.py**: HITL 承認フロー（interrupt/resume）
- **display_formatter.py**: LLM 出力のフォーマッティング

### 承認層 (`src/kraft/approval/`)

- **tool_approval.py**: ツール呼び出し承認判定
- **tool_config.py**: ツール設定（HITL の対象外など）
- **hitl_prompt.py**: 承認 UI/プロンプト

### ツール層 (`src/kraft/tools/`)

- **file_editor_wrapper.py**: ファイル編集ツール（Windows パス対応）
- **file_read_safe.py**: 安全なファイル読込
- **file_read_advanced.py**: 高度なファイル読込（行指定など）
- **grep_tool.py**: grep 実装
- **hitl_wrapper.py**: HITL 統合ラッパー
- **tool_logging.py**: ツール実行ログ

