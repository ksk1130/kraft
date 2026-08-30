# AGENTS.md

## プロジェクト名
kraft

## 概要
このプロジェクトは、Python ベースの CLI/エージェント実験用アプリケーションです。DeepAgents を中心に、ファイルシステム操作、メモリ注入、スキル検索、HITL（Human In The Loop）承認を組み合わせて、開発支援フローを提供します。

主な目的:
- DeepAgents のミドルウェア構成を利用する
- ワークスペース内ファイルを安全に操作する
- スキルを自動探索・読み込みして LLM にコンテキストとして渡す
- 重要なツール実行前にユーザー承認を求める
- 会話と作業状態を保持する

## 現在の実装方針

### 1. 中核コンポーネント
- `src/kraft/agent.py`
  - DeepAgents のアプリ生成とバックエンド構成を定義
  - `StateBackend` / `FilesystemBackend` / `CompositeBackend` を組み合わせる
  - `FilesystemMiddleware`、`MemoryMiddleware`、`SkillsMiddleware` を組み込む
- `src/kraft/__init__.py`
  - CLI の入口点
  - 起動時にスキルソースの確認と初期表示を行う
  - ツール実行の承認フローと再開処理を担当する
- `src/kraft/approval/hitl_prompt.py`
  - ユーザー向けの承認UI
  - 実行対象ツール、引数、危険度、選択肢を表示する

### 2. スキルソース
現在の実装では、スキルソースは一元的に解決されています。

- 定義値: `%USERPROFILE%\.claude\skills`
- 上書き: `KRAFT_SKILLS_DIR`
- 起動時に `discover_skills()` で一覧取得し、`resolve_skills_dir()` でソースを解決する

### 3. 主なツール
- `bash`
- `file_editor`
- `grep_search`
- `file_read`
- `file_read_advanced`
- `read_skill`

## 役割の整理

### CLI / エージェント入口
- 起動・終了フロー
- ユーザー入力の受け取り
- スキル一覧表示
- HITL の再開判定

### メモリ・状態管理
- `AGENTS.md` などのメモリファイルを参照する
- エージェント状態と対話コンテキストを保持する

### ファイルシステム管理
- ワークスペース内の読み取り・編集・検索
- `KRAFT_WORKSPACE_ROOT` によるアクセス制限
- 安全な root 配下のみを対象にする

### スキル管理
- スキルの探索
- スキルの検索・詳細取得
- LLM プロンプトへの注入

### HITL 承認フロー
- `interrupt_on` により危険なツール実行前に一時停止する
- 実行可否や引数をユーザーに提示する
- 承認 / 拒否 / タイムアウト時の挙動を制御する

## 環境変数

```powershell
$env:OPENAI_API_KEY = "your-api-key"
$env:KRAFT_WORKSPACE_ROOT = "C:\path\to\workspace"
$env:KRAFT_SESSION_DIR = "$HOME\.kraft\sessions"
$env:KRAFT_MEMORY_FILE = "AGENTS.md"
$env:KRAFT_SKILLS_DIR = "$HOME\.claude\skills"
$env:KRAFT_HITL_MODE = "interactive"
```

### 主要な意味
- `KRAFT_WORKSPACE_ROOT`: ファイルアクセスの基点
- `KRAFT_MEMORY_FILE`: エージェントメモリとして参照するファイル
- `KRAFT_SKILLS_DIR`: スキルの実体所在
- `KRAFT_HITL_MODE`: 承認動作の制御 (`auto` / `interactive` / `strict`)

## 実行方法

### 依存関係の準備
```bash
uv sync
```

### 実行
```bash
uv run kraft
```

### テスト実行
```bash
uv run pytest -q test
uv run pytest test/test_hitl_filesystem_integration.py -v
uv run pytest test/test_skill_search.py -v
```

## テスト方針
テストは `test/` 配下に置かれ、以下の観点を重視する。

- スキル検索の正確性
- HITL 承認フローの動作
- ファイル操作の安全性
- CLI の起動と初期表示

## 変更時の注意
- スキルソースの解決は一元化する
- ファイルアクセスは `KRAFT_WORKSPACE_ROOT` を基準に行う
- 重要なツール実行は HITL による承認を前提とする
- README と AGENTS.md の説明は実装と一致させる

## まとめ
このプロジェクトは、単なる CLI ではなく「スキル駆動型の開発支援エージェント」を目指した構成です。DeepAgents のミドルウェア、HITL 承認、ファイルアクセス制御、スキル検索の 4 層が揃っており、実際の利用時にはそれらをまとめて扱う設計になっています。

