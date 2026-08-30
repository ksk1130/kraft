#!/usr/bin/env python
"""新しいコマンドの動作テスト"""
import sys
sys.path.insert(0, 'src')

from kraft.agent import discover_skills

print('■ /skills コマンドのテスト')
print()
print('[Skills] ロード済みスキル一覧')
skills = discover_skills()
if skills:
    for i, (name, skill) in enumerate(skills.items(), 1):
        description = skill.get("description", "")[:60] if skill.get("description") else "(説明なし)"
        print(f'  {i}. {name}')
        print(f'     {description}')
else:
    print('  (スキルがロードされていません)')

print()
print('■ /help コマンドのテスト')
print()
print('[Help] 利用可能なコマンド')
print()
print('  セッション管理:')
print('    /session list    - セッション一覧を表示')
print('    /session delete  - 現在のセッションを削除')
print()
print('  スキル・ツール:')
print('    /skills          - ロード済みスキルを表示')
print()
print('  その他:')
print('    /clear           - 会話履歴をクリア')
print('    /help            - このヘルプを表示')
print('    exit/quit/bye    - 対話を終了')

