"""Java/Python コード検出・ハイライト機能のテスト."""

from src.kraft.display_formatter import (
    _detect_java_code,
    _detect_python_code,
    _parse_and_render_answer,
    display_final_answer
)

# テスト1: Java コード検出
print("=" * 70)
print("Test 1: Java コード検出（プレーンテキスト）")
print("=" * 70)

java_plain = """以下は1から100までのFizzBuzzの例です。
public class FizzBuzz {
    public static void main(String[] args) {
        for (int i = 1; i <= 100; i++) {
            if (i % 15 == 0) {
                System.out.println("FizzBuzz");
            } else if (i % 3 == 0) {
                System.out.println("Fizz");
            } else if (i % 5 == 0) {
                System.out.println("Buzz");
            } else {
                System.out.println(i);
            }
        }
    }
}"""

is_java, desc, code = _detect_java_code(java_plain)
print(f"Java 検出: {is_java}")
print(f"説明: {desc}")
print(f"コード行数: {len(code.split(chr(10)))}")
print(f"コード先頭: {code[:80]}...")
print()

# テスト2: 検出したコードをハイライト表示
print("=" * 70)
print("Test 2: Java コードのハイライト表示")
print("=" * 70)

display_final_answer(java_plain)

print("\n" + "=" * 70)
print("Test 3: Python コード検出（プレーンテキスト）")
print("=" * 70)

python_plain = """以下はフィボナッチ数列の例です。
def fibonacci(n):
    '''フィボナッチ数列を生成'''
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b

# 使用例
for num in fibonacci(10):
    print(num)"""

is_python, desc, code = _detect_python_code(python_plain)
print(f"Python 検出: {is_python}")
print(f"説明: {desc}")
print(f"コード行数: {len(code.split(chr(10)))}")
print(f"コード先頭: {code[:80]}...")
print()

# テスト4: 検出したコードをハイライト表示
print("=" * 70)
print("Test 4: Python コードのハイライト表示")
print("=" * 70)

display_final_answer(python_plain)

print("\n✓ テスト完了")

