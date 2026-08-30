#!/usr/bin/env python
"""grep_search ツールのテスト"""
import sys
sys.path.insert(0, 'src')

from kraft.tools.grep_tool import grep_search

print('■ Grep Search ツール使用テスト')
print()

# テスト: src/kraft/tools ディレクトリで 'def ' を検索
result = grep_search('def ', path='src/kraft/tools', recursive=True, max_results=10)
print('テスト: "def " を src/kraft/tools で検索')
print('-' * 60)
print(result)

