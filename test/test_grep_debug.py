#!/usr/bin/env python
"""grep_search のデバッグテスト"""
import sys
sys.path.insert(0, 'src')

from pathlib import Path
from kraft.tools.grep_tool import _is_text_file, _should_skip_dir, grep_search

# 対象ディレクトリ
target_dir = Path('C:\\Users\\kskan\\Desktop\\java_MyAIAgent2')

print('■ java_MyAIAgent2 配下の .java ファイル一覧')
print()

java_files = list(target_dir.rglob('*.java'))
print(f'見つかったファイル数: {len(java_files)}')
print()

# 最初の10個のみ表示
for i, f in enumerate(java_files[:10], 1):
    is_text = _is_text_file(f)
    parent_skip = _should_skip_dir(f.parent)
    print(f'{i}. {f.name}')
    print(f'   テキスト判定: {is_text}')
    print(f'   親スキップ: {parent_skip}')
    print()

print('\n■ grep_search テスト')
print('=' * 70)
result = grep_search('org\\.apache\\.tika', path='C:\\Users\\kskan\\Desktop\\java_MyAIAgent2', recursive=True, max_results=20)
print(result)

