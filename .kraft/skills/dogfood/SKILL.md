# dogfood

このリポジトリで agent を使うときの標準動作を定義するスキルです。

## 目的
- 低リスクな read-only 操作は自動実行する
- 変更系の操作は必ず diff と承認を確認する
- この repo をトラブルなく扱うための実装指針を守る

## ルール
- issue / task を確認してから patch を作る
- focus したテストを実行してから完了と判断する
- diff を確実に確認してから最終報告を行う
- `uv run pytest -q test` を全体の最低検証として使う

## 典型フロー
1. `grep_search` または `file_read` で影響範囲を絞る
2. `read_skill` で必要なスキルを確認する
3. `edit_file` で変更を行う
4. 対象テストを実行する
5. 変更差分を確認して summary を作る

## 安全境界
- 自動承認 OK: grep_search, file_read, file_read_advanced, read_skill, session list
- 確認必須: bash, edit_file, git, write_file, delete
