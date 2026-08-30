"""Agent Response パネル内でのシンタックスハイライト表示テスト."""

from src.kraft.display_formatter import display_final_answer

# Test 1: Java コードのみ
print("=" * 60)
print("Test 1: Java Code with Markdown Syntax Highlighting")
print("=" * 60)

java_answer = """これは Java のコード例です。

```java
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
        System.out.println("シンタックスハイライト対応");
    }
}
```

コンパイルと実行:

```bash
javac HelloWorld.java
java HelloWorld
```

完了です。"""

display_final_answer(java_answer)

print("\n" + "=" * 60)
print("Test 2: Python Code with Markdown Syntax Highlighting")
print("=" * 60 + "\n")

python_answer = """以下は Python のフィボナッチ数列実装です。

```python
def fibonacci(n: int) -> list[int]:
    '''フィボナッチ数列を生成'''
    result = []
    a, b = 0, 1
    for _ in range(n):
        result.append(a)
        a, b = b, a + b
    return result

# 使用例
if __name__ == "__main__":
    seq = fibonacci(10)
    print(f"最初の10個: {seq}")
```

実行方法:

```bash
python fibonacci.py
```

推奨です。"""

display_final_answer(python_answer)

print("\n" + "=" * 60)
print("Test 3: Multiple Languages")
print("=" * 60 + "\n")

multi_answer = """複数の言語を混在させた例:

**JavaScript:**

```javascript
function factorial(n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}
console.log(factorial(5)); // 120
```

**C#:**

```csharp
public class Program {
    public static int Factorial(int n) {
        return n <= 1 ? 1 : n * Factorial(n - 1);
    }
    
    static void Main() {
        Console.WriteLine(Factorial(5)); // 120
    }
}
```

**Go:**

```go
package main

import "fmt"

func factorial(n int) int {
    if n <= 1 {
        return 1
    }
    return n * factorial(n-1)
}

func main() {
    fmt.Println(factorial(5)) // 120
}
```

以上です。"""

display_final_answer(multi_answer)

print("\n✓ すべてのテストが完了しました")

