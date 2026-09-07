"""使 pytest 能稳定 import backend 包（main / app）。

显式把 backend/ 加入 sys.path，避免依赖 pytest 的隐式 rootdir 插入规则
（评审意见 P3，2026-09-03）。
"""
import os
import sys
from pathlib import Path

# 测试环境关闭演示种子题（polish 2026-09-07）：pytest 导入 main 前生效，
# 避免 TestClient 启动时把 Hello World/A+B 种入题库，干扰"空题库"类断言。
os.environ["OJ_SEED_DEMO"] = "0"

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
