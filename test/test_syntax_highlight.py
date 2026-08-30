"""シンタックスハイライト機能のテスト."""

from src.kraft.display_formatter import _parse_and_render_answer
from rich.console import Console

# テスト用 Console
console = Console()


def test_java_code_block():
    """Java コードブロックのシンタックスハイライト."""
    answer = """これは Java のコード例です。

```java
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
```

以上です。"""
    
    rendered = _parse_and_render_answer(answer)
    console.print("[bold cyan]=== Test 1: Java Code Block ===[/bold cyan]")
    console.print(rendered)
    console.print()


def test_python_code_block():
    """Python コードブロックのシンタックスハイライト."""
    answer = """これは Python のコード例です。

```python
def fibonacci(n):
    '''フィボナッチ数列を生成'''
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b

# 使用例
for num in fibonacci(10):
    print(num)
```

完了しました。"""
    
    rendered = _parse_and_render_answer(answer)
    console.print("[bold cyan]=== Test 2: Python Code Block ===[/bold cyan]")
    console.print(rendered)
    console.print()


def test_multiple_code_blocks():
    """複数のコードブロック混在."""
    answer = """以下に複数の言語の例を示します。

```javascript
function greet(name) {
    return `Hello, ${name}!`;
}
console.log(greet("World"));
```

そして Python:

```python
def greet(name):
    return f"Hello, {name}!"

print(greet("World"))
```

以上です。"""
    
    rendered = _parse_and_render_answer(answer)
    console.print("[bold cyan]=== Test 3: Multiple Code Blocks ===[/bold cyan]")
    console.print(rendered)
    console.print()


def test_no_code_blocks():
    """コードブロックなしの Markdown."""
    answer = """これは **太字** と *斜体* を含む Markdown テキストです。

- リスト項目 1
- リスト項目 2
- リスト項目 3

## セクション

通常のテキストです。"""
    
    rendered = _parse_and_render_answer(answer)
    console.print("[bold cyan]=== Test 4: No Code Blocks ===[/bold cyan]")
    console.print(rendered)
    console.print()


def test_unknown_language():
    """未対応の言語."""
    answer = """未対応言語の例:

```rust
fn main() {
    println!("Hello, Rust!");
}
```

終了。"""
    
    rendered = _parse_and_render_answer(answer)
    console.print("[bold cyan]=== Test 5: Unknown Language ===[/bold cyan]")
    console.print(rendered)
    console.print()


if __name__ == "__main__":
    console.print("[bold yellow]シンタックスハイライト機能のテスト[/bold yellow]")
    console.print()
    
    test_java_code_block()
    test_python_code_block()
    test_multiple_code_blocks()
    test_no_code_blocks()
    test_unknown_language()
    
    console.print("[bold green]✓ すべてのテストが完了しました[/bold green]")

