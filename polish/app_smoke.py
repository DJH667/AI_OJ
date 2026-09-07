"""前端冒烟测试（st.testing.v1.AppTest）：驱动主要页面流程，直连本地后端 127.0.0.1:8000。

前置：
- 后端已启动（WSL：cd backend && ~/oj-venv/bin/python -m uvicorn main:app --port 8000）；
- 题库已种入 P1000/P1001（后端启动自动种入）；
- 运行：cd 仓库根 && .venv/Scripts/python.exe polish/app_smoke.py（Windows venv 含 streamlit）。

说明：脚本会注册一次性用户 smokeuser 并真实提交评测，产生少量演示数据；
验收/演示前如需干净环境，删除 backend/data/ 下 smokeuser 相关文件即可
（users/smokeuser.json、submissions/ 中的记录、sessions/ 与 logs/access/ 中含 smokeuser 的文件）。
"""
import httpx
import importlib
import sys
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "frontend" / "app.py")
USER, PASSWORD = "smokeuser", "secret123"

# 判定徽章回归（fix 2026-09-07：status=success 但 0 分 ≠ 通过）
sys.path.insert(0, str(Path(APP).parent))
app_mod = importlib.import_module("app")
assert app_mod._verdict({"status": "success", "score": 0, "counts": 20}) == "未通过"
assert app_mod._verdict({"status": "success", "score": 10, "counts": 20}) == "部分通过"
assert app_mod._verdict({"status": "success", "score": 20, "counts": 20}) == "通过"
assert app_mod._verdict({"status": "pending", "score": 0, "counts": 0}) == "评测中"
assert app_mod._verdict({"status": "error"}) == "错误"
assert app_mod._fmt_time("2026-09-07T18:56:04") == "09-07 18:56"
comp = app_mod._case_composition([{"result": "AC"}, {"result": "TLE"}, {"result": "TLE"}])
assert "AC] x1" in comp and "TLE] x2" in comp, comp
print("0. 判定徽章逻辑（0 分 ≠ 通过）与时间/测点构成格式 OK")

# 准备一次性用户（若已存在说明上次清理失败，直接复用）
http = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30)
r = http.post("/api/users/", json={"username": USER, "password": PASSWORD})
assert r.status_code == 200 or r.json().get("msg") == "username already exists", r.text

at = AppTest.from_file(APP, default_timeout=60)
at.run()
assert not at.exception, at.exception
titles = [t.value for t in at.title]
assert "OJ 在线评测" in titles, f"auth page missing: {titles}"
print("1. 未登录 → 全画幅登录/注册页 OK")

# 真实登录（走登录表单 → 后端会话 Cookie）
inputs = at.text_input
assert len(inputs) >= 2, "登录表单字段缺失"
inputs[0].set_value(USER)
inputs[1].set_value(PASSWORD)
at.button(key="login_submit").click().run()
assert not at.exception, at.exception
assert at.session_state["user"]["username"] == USER, at.session_state.get("user")
assert at.session_state["page"] == "problems", at.session_state.get("page")
btns = [b.key for b in at.button]
for k in ("nav_problems", "nav_manage", "nav_profile", "logout"):
    assert k in btns, f"missing nav {k}: {btns}"
assert "open_P1000" in btns and "open_P1001" in btns, f"missing bank cards: {btns}"
# 题库搜索：按标题关键词过滤（编号同理）
search_box = [w for w in at.text_input if w.label == "搜索题目"]
assert search_box, "题库搜索框缺失"
search_box[0].set_value("A+B")
at.run()
assert not at.exception, at.exception
btns = [b.key for b in at.button]
assert "open_P1001" in btns and "open_P1000" not in btns, btns
search_box = [w for w in at.text_input if w.label == "搜索题目"]
search_box[0].set_value("")
at.run()
assert not at.exception, at.exception
btns = [b.key for b in at.button]
assert "open_P1000" in btns and "open_P1001" in btns, btns
print("2. 登录后默认题库页 + 三项侧边栏 + 种子题卡片 + 题库搜索 OK")

# 进入题目详情
at.button(key="open_P1000").click().run()
assert not at.exception, at.exception
assert at.session_state["view_problem_id"] == "P1000"
btns = [b.key for b in at.button]
assert "back_to_bank" in btns and "start_submit_P1000" in btns and "goto_query_P1000" in btns, btns
caps = [c.value for c in at.caption]
assert any("题目编号" in (c or "") for c in caps), f"详情页缺少题目编号: {caps}"
print("3. 题目详情二级页（返回/提交入口/查询入口 + 题目编号）OK")

# 展开提交表单（大文本框 + 语言选择）
at.button(key="start_submit_P1000").click().run()
assert not at.exception, at.exception
btns = [b.key for b in at.button]
assert "submit_btn" in btns, btns
assert any(w.label == "语言" for w in at.selectbox), "语言选择缺失"
assert any(w.label == "代码" for w in at.text_area), "代码文本框缺失"
print("4. 提交面板（语言选择 + 大文本框 + 黄色提交按钮）OK")

# 提交代码（真实评测 python）
areas = [w for w in at.text_area if w.label == "代码"]
areas[0].set_value("print('Hello, World!')")
at.button(key="submit_btn").click().run()
assert not at.exception, at.exception
print("5. 提交评测请求已发出 OK")

# 返回题库 → 查询页入口验证前先看详情页右侧栏近 3 次提交（可能仍在评测）
btns = [b.key for b in at.button]
assert "goto_query_P1000" in btns, "详情页查询入口缺失"

# 查询提交记录（跳转查询页并预选该题）
at.button(key="goto_query_P1000").click().run()
assert not at.exception, at.exception
assert at.session_state["page"] == "query"
at.button(key="run_query").click().run()
assert not at.exception, at.exception
caps = [c.value for c in at.caption]
for label in ("状态", "题目", "语言", "得分", "时间"):
    assert label in caps, f"查询页表头缺失 {label}: {caps}"
detail_btns = [b.key for b in at.button if b.key.startswith("query_detail_")]
assert detail_btns, "查询行详情按钮缺失"
at.button(key=detail_btns[0]).click().run()
assert not at.exception, at.exception
print("6. 查询页（列对齐表头 + 按题预选 + 详情按钮切换）OK")

# 题目管理
at.button(key="nav_manage").click().run()
assert not at.exception, at.exception
assert at.session_state["page"] == "manage"
btns = [b.key for b in at.button]
assert "edit_P1000" in btns and "del_P1000" in btns, btns
assert "new_problem" in btns and "open_ai" in btns, btns
print("7. 题目管理（搜索 + 编辑/删除图标 + 新增/AI 入口）OK")

# 新增题目表单（time_limit/memory_limit 步进 + 难度选择）
at.button(key="new_problem").click().run()
assert not at.exception, at.exception
numbers = {w.label for w in at.number_input}
assert "时限 time_limit（秒）" in numbers and "内存 memory_limit（MB）" in numbers, numbers
diffs = [w for w in at.selectbox if w.label == "难度 *"]
assert diffs and diffs[0].value == "入门", [d.value for d in diffs]
assert app_mod._nearest_difficulty(7.0) == "提高+" and app_mod._nearest_difficulty(2.3) == "普及-"
print("8. 出题表单（时限/内存输入 + 难度下拉默认入门）OK")

# 返回 → 编辑已有题目（预填 + 编号锁定 + 难度预选；普通用户为申请修改）
at.button(key="back_manage").click().run()
assert not at.exception, at.exception
at.button(key="edit_P1000").click().run()
assert not at.exception, at.exception
assert at.session_state["manage_action"] == "edit:P1000", at.session_state.get("manage_action")
assert at.title[0].value == "编辑题目（提交修改申请）", at.title[0].value
titles = [w.value for w in at.text_input if w.label == "标题 title *"]
assert titles and titles[0] == "Hello, World!", titles
locked = [w for w in at.text_input if w.label == "编号 id *"]
assert locked and locked[0].disabled, "编辑时编号应锁定"
diffs = [w for w in at.selectbox if w.label == "难度 *"]
assert diffs and diffs[0].value == "入门", [d.value for d in diffs]
print("8b. 编辑题目表单（预填 + 编号锁定 + 难度预选 + 申请提示）OK")

# 8c：普通用户提交修改申请 → 卡片显示待审批、编辑按钮禁用
title_box = [w for w in at.text_input if w.label == "标题 title *"]
title_box[0].set_value("Hello, World! v2")
submit_btns = [b for b in at.button if b.label == "保存题目"]
assert submit_btns, "表单保存按钮缺失"
submit_btns[0].click().run()
assert not at.exception, at.exception
mds = [m.value or "" for m in at.markdown]
assert any("修改待审批" in m for m in mds), "管理卡片缺少待审批标记"
edit_btn = [b for b in at.button if b.key == "edit_P1000"]
assert edit_btn and edit_btn[0].disabled, "待审批时编辑按钮应禁用"
print("8c. 普通用户修改申请提交与待审批状态 OK")

# 8c 提交后已回到管理列表 → 个人页
at.button(key="nav_profile").click().run()
assert not at.exception, at.exception
assert at.session_state["page"] == "profile"
btns = [b.key for b in at.button]
assert "profile_query" in btns, btns
print("9. 个人中心（信息卡 + 查询入口）OK")

print("APP SMOKE PASSED")
