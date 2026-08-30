#!/usr/bin/env python3
"""bash ツール内の git log コマンド実行テスト"""

import subprocess

# Test 1: Direct command 
print("=== Test 1: Direct subprocess call ===")
cmd = ["powershell", "-NoProfile", "-Command", "git log -n 2 --oneline"]
result = subprocess.run(cmd, capture_output=True, text=False, timeout=30)
stdout = result.stdout.decode("utf-8", errors="replace")
stderr = result.stderr.decode("utf-8", errors="replace")
print(f"Return code: {result.returncode}")
print(f"Stdout: {stdout[:200]}")
print(f"Stderr: {stderr[:200] if stderr else '(empty)'}")
print()

# Test 2: With double dash
print("=== Test 2: With double dash ===")
cmd = ["powershell", "-NoProfile", "-Command", "git log -n 2 -- README.md"]
result = subprocess.run(cmd, capture_output=True, text=False, timeout=30)
stdout = result.stdout.decode("utf-8", errors="replace")
stderr = result.stderr.decode("utf-8", errors="replace")
print(f"Return code: {result.returncode}")
print(f"Stdout: {stdout[:200]}")
print(f"Stderr: {stderr[:200] if stderr else '(empty)'}")
print()

# Test 3: With double quotes around README.md
print("=== Test 3: With double quotes ===")
cmd = ["powershell", "-NoProfile", "-Command", 'git log -n 2 -- "README.md"']
result = subprocess.run(cmd, capture_output=True, text=False, timeout=30)
stdout = result.stdout.decode("utf-8", errors="replace")
stderr = result.stderr.decode("utf-8", errors="replace")
print(f"Return code: {result.returncode}")
print(f"Stdout: {stdout[:200]}")
print(f"Stderr: {stderr[:200] if stderr else '(empty)'}")
print()

# Test 4: Using -c flag for PowerShell (alternate approach)
print("=== Test 4: Using -c (EncodedCommand) ===")
import base64
ps_cmd = "git log -n 2 -- README.md"
encoded = base64.b64encode(ps_cmd.encode('utf-16-le')).decode('ascii')
cmd = ["powershell", "-NoProfile", "-EncodedCommand", encoded]
result = subprocess.run(cmd, capture_output=True, text=False, timeout=30)
stdout = result.stdout.decode("utf-8", errors="replace")
stderr = result.stderr.decode("utf-8", errors="replace")
print(f"Return code: {result.returncode}")
print(f"Stdout: {stdout[:200]}")
print(f"Stderr: {stderr[:200] if stderr else '(empty)'}")
