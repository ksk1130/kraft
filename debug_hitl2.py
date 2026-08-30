from langchain.agents.middleware.human_in_the_loop import HumanInTheLoopMiddleware
import inspect

source = inspect.getsource(HumanInTheLoopMiddleware._process_decision)
lines = source.split('\n')

# 全行表示
for i, line in enumerate(lines[:200], 1):
    print(f"{i:3d}: {line}")
