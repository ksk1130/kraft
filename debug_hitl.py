from langchain.agents.middleware.human_in_the_loop import HumanInTheLoopMiddleware
import inspect

source = inspect.getsource(HumanInTheLoopMiddleware.after_model)
lines = source.split('\n')

# 前150行を表示
for i, line in enumerate(lines[:150], 1):
    print(f"{i:3d}: {line}")
