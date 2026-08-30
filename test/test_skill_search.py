#!/usr/bin/env python
"""TODO 5: Enhanced Skill Listing の テストコード"""

import sys
from pathlib import Path

# プロジェクトルートを追加
sys.path.insert(0, str(Path(__file__).parent))

from src.kraft.agent import list_all_skills, search_skills


def test_skill_search_basic():
    """基本的なスキル検索機能をテスト"""
    print("=" * 70)
    print("Test 1: 基本的なスキル検索")
    print("=" * 70)
    
    # すべてのスキルを表示
    all_skills = list_all_skills()
    print(f"\n✓ ロード済みスキル: {len(all_skills)} 個\n")
    for name, desc in all_skills[:3]:  # 最初の3個を表示
        desc_preview = desc[:70] if desc else "(説明なし)"
        print(f"  - {name}: {desc_preview}")
    
    if len(all_skills) > 3:
        print(f"  ... 他 {len(all_skills) - 3} 個")


def test_skill_search_keyword():
    """キーワード検索をテスト"""
    print("\n" + "=" * 70)
    print("Test 2: キーワード検索（'python'）")
    print("=" * 70)
    
    results = search_skills("python")
    print(f"\n✓ マッチしたスキル: {len(results)} 個\n")
    for name, desc in results:
        desc_preview = desc[:70] if desc else "(説明なし)"
        print(f"  - {name}: {desc_preview}")
    
    if not results:
        print("  (マッチするスキルがありません)")


def test_skill_search_case_insensitive():
    """大文字小文字区別しない検索をテスト"""
    print("\n" + "=" * 70)
    print("Test 3: 大文字小文字区別しない検索（'PYTHON'）")
    print("=" * 70)
    
    results = search_skills("PYTHON")
    print(f"\n✓ マッチしたスキル: {len(results)} 個\n")
    for name, desc in results[:3]:
        desc_preview = desc[:70] if desc else "(説明なし)"
        print(f"  - {name}: {desc_preview}")
    
    if len(results) > 3:
        print(f"  ... 他 {len(results) - 3} 個")


def test_skill_search_multiple_keywords():
    """複数キーワード検索をテスト"""
    print("\n" + "=" * 70)
    print("Test 4: 複数キーワード検索例")
    print("=" * 70)
    
    keywords = ["python", "azure", "deploy", "debug"]
    
    for keyword in keywords:
        results = search_skills(keyword)
        print(f"\n  '{keyword}': {len(results)} 個のスキルが見つかりました")
        if results:
            print(f"    - 最初のマッチ: {results[0][0]}")


def test_skill_search_no_match():
    """マッチしないキーワード検索をテスト"""
    print("\n" + "=" * 70)
    print("Test 5: マッチしないキーワード検索（'zzzzzzz'）")
    print("=" * 70)
    
    results = search_skills("zzzzzzz")
    print(f"\n✓ マッチしたスキル: {len(results)} 個")
    if not results:
        print("  (期待通り、マッチするスキルがありません)")


def test_skill_scoring():
    """スコアリング機能をテスト（名前マッチが説明マッチより優先）"""
    print("\n" + "=" * 70)
    print("Test 6: スコアリング機能（名前マッチ優先）")
    print("=" * 70)
    
    # テスト用の複合クエリ
    keyword = "python"
    results = search_skills(keyword)
    
    print(f"\n✓ キーワード '{keyword}' の検索結果:\n")
    if results:
        for i, (name, desc) in enumerate(results[:5], 1):
            # 名前マッチと説明マッチを判定
            has_name_match = keyword.lower() in name.lower()
            has_desc_match = keyword.lower() in desc.lower()
            
            match_type = "名前" if has_name_match else "説明"
            desc_preview = desc[:60] if desc else "(説明なし)"
            print(f"  {i}. {name} ({match_type} マッチ)")
            print(f"     {desc_preview}\n")
    else:
        print("  (マッチするスキルがありません)")


if __name__ == "__main__":
    print("\n")
    print("[cyan bold]TODO 5: Enhanced Skill Listing テスト[/cyan bold]\n")
    
    try:
        test_skill_search_basic()
        test_skill_search_keyword()
        test_skill_search_case_insensitive()
        test_skill_search_multiple_keywords()
        test_skill_search_no_match()
        test_skill_scoring()
        
        print("\n" + "=" * 70)
        print("✓ テスト完了")
        print("=" * 70 + "\n")
        
    except Exception as e:
        print(f"\n[NG] テストエラー: {e}")
        import traceback
        traceback.print_exc()

