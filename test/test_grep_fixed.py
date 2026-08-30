#!/usr/bin/env python
"""grep_search の除外パス判定テスト"""
import sys
sys.path.insert(0, 'src')

from pathlib import Path
from kraft.tools.grep_tool import _file_in_excluded_path

# テスト
test_paths = [
    Path('C:\\Users\\kskan\\Desktop\\java_MyAIAgent2\\mcp-server\\src\\main\\java\\DocumentTextExtractor.java'),
    Path('C:\\Users\\kskan\\Desktop\\java_MyAIAgent2\\.gradle\\caches\\test.txt'),
    Path('C:\\Users\\kskan\\Desktop\\java_MyAIAgent2\\build\\test.txt'),
    Path('C:\\Users\\kskan\\Desktop\\java_MyAIAgent2\\__pycache__\\test.pyc'),
]

print('■ 除外パス判定テスト')
print()
for p in test_paths:
    skip = _file_in_excluded_path(p)
    status = 'スキップ' if skip else '検索対象'
    print(f'{p.name}: {status}')

print()
print('■ grep_search テスト（修正後）')
print('=' * 70)

from kraft.tools.grep_tool import grep_search
result = grep_search('org\\.apache\\.tika', path='C:\\Users\\kskan\\Desktop\\java_MyAIAgent2', recursive=True, max_results=20)
print(result)

