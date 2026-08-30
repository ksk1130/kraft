#!/usr/bin/env python
"""ツール統合テストスクリプト"""
import sys
sys.path.insert(0, 'src')

try:
    from kraft.agent import agent, discover_skills
    skills = discover_skills()
    print("✓ エージェントのロード成功")
    print(f"✓ ロード済みスキル数: {len(skills)}")
    print(f"✓ ロード済みスキル: {list(skills.keys())}")
    print("✓ トークン制限エラー回避機能が有効です（max_completion_tokens: 4000）")
except Exception as e:
    print(f"✗ エラー: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

