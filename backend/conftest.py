"""使 pytest 能稳定 import backend 包（main / app）。

显式把 backend/ 加入 sys.path，避免依赖 pytest 的隐式 rootdir 插入规则
（评审意见 P3，2026-09-03）。
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
