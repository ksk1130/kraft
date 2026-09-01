# AGENTS.md

## プロジェクト名

kraft

## 概要

このリポジトリは、Python ベースの CLI / エージェント実験用アプリケーションです。`DeepAgents` を中心に、ファイルアクセス、メモリ注入、スキル探索、HITL 承認を組み合わせて、開発支援フローを実現します。

主な目標:

- DeepAgents のミドルウェア構成を利用する
- ワークスペースを安全に制限したうえでファイルを処理する
- `AGENTS.md` と `SKILL.md` を自動的に読み込み、LLM のコンテキストに付与する
- 重要なツール実行前にユーザー承認を要求する
- セッションごとに会話履歴を保持して再開できるようにする

## 実装方針

### 中核コンポーネント

- `src/kraft/agent.py`
  - `DeepAgents` のアプリ生成
  - `StateBackend` / `FilesystemBackend` / `CompositeBackend` の構成
  - `FilesystemMiddleware` / `MemoryMiddleware` / `SkillsMiddleware` の組み込み
- `src/kraft/__init__.py`
  - CLI の入口
  - セッション管理と対話ループ
  - スキル探索および HITL の再開処理
- `src/kraft/approval/hitl_prompt.py`
  - 承認ダイアログ UI
  - 実行対象、引数、危険度、選択肢を提示する

### スキルソース

スキルソースは一元化されています。

- repo-local 優先: `.kraft/skills` / `skills`
- 既定グローバル: `%USERPROFILE%\.claude\skills`
- 上書き: `KRAFT_SKILLS_DIR`
- `discover_skills()` と `resolve_skills_dir()` で統一的に決定する

repo-local のスキルは、グローバルの skill より優先される。これにより、この repository 固有の dogfood / review / triage のルールを安全に注入できる。

### 主要ツール

- `bash`
- `edit_file`
- `grep_search`
- `file_read`
- `file_read_advanced`
- `read_skill`

## 役割分担

### CLI / エージェント入口

- 起動・終了フロー
- 入力の受け取り
- スキル一覧表示
- セッション選択と復元

### メモリと状態管理

- `AGENTS.md` と会話履歴を参照、保存する
- セッションごとにメッセージ履歴を保持する

### ファイルシステム管理

- ワークスペース内の読み取り・編集・検索を行う
- `KRAFT_WORKSPACE_ROOT` によってアクセスを制限する

### スキル管理

- スキルの探索
- スキルの検索と詳細取得
- LLM のプロンプトへ注入

### HITL 承認

- 危険なツール実行前に中断する
- 実行内容をユーザーに表示する
- 承認 / 拒否 / タイムアウト時の挙動を制御する

## 環境変数

```bash
export OPENAI_API_KEY="your-api-key"
export KRAFT_WORKSPACE_ROOT="$(pwd)"
export KRAFT_SESSION_DIR="$HOME/.kraft/sessions"
export KRAFT_MEMORY_FILE="AGENTS.md"
export KRAFT_SKILLS_DIR="$HOME/.claude/skills"
export KRAFT_HITL_MODE="interactive"
```

PowerShell 例:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
$env:KRAFT_WORKSPACE_ROOT = "C:\path\to\workspace"
$env:KRAFT_SESSION_DIR = "$HOME\.kraft\sessions"
$env:KRAFT_MEMORY_FILE = "AGENTS.md"
$env:KRAFT_SKILLS_DIR = "$HOME\.claude\skills"
$env:KRAFT_HITL_MODE = "interactive"
```

## 実行方法

```bash
uv sync
./scripts/dogfood.sh
uv run kraft
```

`./scripts/dogfood.sh` は標準的な dogfood フローをまとめたエントリーポイントです。
- read-only の確認
- ターゲットテストの実行
- diff review の出力
- 実行ログの記録

## テスト

```bash
uv run pytest -q test
uv run pytest test/test_hitl_filesystem_integration.py -v
uv run pytest test/test_skill_search.py -v
```

重点観点:

- スキル検索の正確さ
- HITL 承認フローの挙動
- ファイル操作の安全性
- CLI の起動と初期表示

## 変更時の注意

- スキルソース解決は一元化する
- ファイルアクセスは `KRAFT_WORKSPACE_ROOT` を基準に行う
- 重要なツール実行は必ず HITL 承認の対象にする
- README と AGENTS.md の説明は実装と一致させる

## まとめ

このプロジェクトは、単なる CLI ではなく「スキル駆動型の開発支援エージェント」を目指した構成です。`DeepAgents` のミドルウェア、HITL 承認、ファイルアクセス制御、スキル検索の 4 層が揃っており、実際の利用時にはそれらをまとめて扱う設計になっています。

