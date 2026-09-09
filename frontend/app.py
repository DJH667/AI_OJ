"""OJ 前端（Streamlit，polish 2026-09-07）。

前后端分离：仅经 REST API + Cookie 会话与 FastAPI 后端交互（api_client.py）。
结构：全画幅登录/注册（注册成功自动登录）→ 侧边栏三项（题库 / 题目管理 / 个人）→
- 题库：分页圆角卡片（难度/标签/通过率条），点击进入题目详情；
- 题目详情（二级页）：左侧题面，右侧栏提交代码（黄色提交按钮）+ 近 3 次提交 + 查询提交记录入口；
- 查询提交记录（从题目右侧栏或"个人"页进入）：按题/全部、管理员按用户，时间倒序；
- 题目管理：编号/标题搜索、编辑/删除图标、AI 命题入口、出题表单（time_limit 步进 0.5、memory_limit 步进 128）；
- 个人：信息卡 + 管理员用户管理。
启动（backend 先起在 8000）：
    ../.venv/Scripts/python.exe -m streamlit run app.py --server.port 8501   # Windows
"""
import json
import math
import time
from datetime import datetime

import streamlit as st

from api_client import ApiClientError, SESSION_COOKIE, get_client

TAG_OPTIONS = [
    "模拟", "枚举", "贪心", "二分", "双指针", "排序", "数学", "数论", "动态规划",
    "搜索/DFS", "BFS", "图论", "最短路", "最小生成树", "字符串", "前缀和", "差分", "位运算",
    "高精度", "分治", "递归", "哈希", "并查集", "数据结构", "栈/队列", "堆", "树", "其他",
]
COMPLEXITY_OPTIONS = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "其他"]
SCALE_OPTIONS = ["小（n<=10^3）", "中（n<=10^5）", "大（n<=10^7）", "其他"]

NAV_ITEMS = [
    ("题库", ":material/menu_book:", "problems"),
    ("题目管理", ":material/table_chart:", "manage"),
    ("个人", ":material/person:", "profile"),
]

BANK_PAGE_SIZE = 10
QUERY_PAGE_SIZE = 10
RECENT_SUBMISSIONS = 3
ROLE_TEXT = {"admin": "管理员", "user": "普通用户", "banned": "已禁用"}


def _verdict(s: dict) -> str:
    """评测结论（区分 status=success 但非 AC 的情况）。

    后端契约中 status=success 仅表示"评测完成"（api.md），0 分也是 success；
    结论按 score/counts 判定：全对=通过、部分=部分通过、0 分=未通过。
    """
    status = s.get("status")
    if status == "pending":
        return "评测中"
    if status == "error":
        return "错误"
    if status == "success":
        score = s.get("score") or 0
        counts = s.get("counts") or 0
        if counts > 0 and score >= counts:
            return "通过"
        if score > 0:
            return "部分通过"
        return "未通过"
    return str(status or "未知")


_VERDICT_BADGE = {
    "评测中": ":orange-badge[评测中]",
    "错误": ":red-badge[错误]",
    "通过": ":green-badge[通过]",
    "部分通过": ":yellow-badge[部分通过]",
    "未通过": ":red-badge[未通过]",
}

# 测试点级结论（Step5 日志可见时才可得；CE 还可在提交详情经 compile_info 辨识）
CASE_BADGE = {
    "AC": ":green-badge[AC]", "WA": ":red-badge[WA]", "TLE": ":orange-badge[TLE]",
    "MLE": ":orange-badge[MLE]", "RE": ":orange-badge[RE]", "CE": ":red-badge[CE]",
    "UNK": ":gray-badge[UNK]",
}


def _case_composition(details: list) -> str:
    """测点结果构成，如 'AC x2 · TLE x1 · WA x1'。"""
    counts: dict[str, int] = {}
    for d in details:
        v = str(d.get("result", "UNK"))
        counts[v] = counts.get(v, 0) + 1
    return " · ".join(f"{CASE_BADGE.get(v, v)} x{n}" for v, n in counts.items())


def _error_badge(client, sid: str) -> str:
    """error 行细分：编译错误（CE，compile_info 存在）vs 评测错误。

    列表契约只回 status，编译信息需拉取详情；error 行稀少，代价可接受。
    """
    try:
        detail = client.get(f"/api/submissions/{sid}")
    except ApiClientError:
        return _VERDICT_BADGE["错误"]
    ci = detail.get("compile_info")
    if ci and str(ci.get("result", "")) == "compile error":
        return ":red-badge[编译错误]"
    return ":red-badge[评测错误]"


def _verdict_badge(s: dict) -> str:
    verdict = _verdict(s)
    return _VERDICT_BADGE.get(verdict, f":gray-badge[{verdict}]")


# 提交记录行列对齐：同一比例列宽保证各行的 状态/得分/语言/时间 纵向对齐
RECENT_COL_SPEC = [1.5, 1.0, 1.1, 1.6]
QUERY_COL_SPEC = [1.2, 2.4, 0.9, 1.0, 1.5, 0.8]


def _fmt_time(created_at: str) -> str:
    """提交时间缩写为 MM-DD HH:MM，便于列对齐展示。"""
    if not created_at:
        return "—"
    iso = created_at.replace("T", " ")
    return f"{iso[5:10]} {iso[11:16]}" if len(iso) >= 16 else iso


_LANGUAGE_LEXERS = {
    "python": "python",
    "cpp": "cpp",
    "c++": "cpp",
    "c": "c",
    "java": "java",
    "javascript": "javascript",
    "go": "go",
    "rust": "rust",
}


def _code_language(lang: str | None) -> str:
    """提交语言 → Pygments lexer（未知语言回退 text）。"""
    return _LANGUAGE_LEXERS.get((lang or "").lower(), "text")


# 难度标签（与后端方案 D 先验映射一致：入门 1.0 … NOI 10.0）
DIFFICULTY_OPTIONS = ["入门", "普及-", "普及", "普及+", "提高", "提高+", "省选", "NOI"]
DIFFICULTY_LABEL_PRIOR = {"入门": 1.0, "普及-": 2.0, "普及": 3.0, "普及+": 4.0,
                          "提高": 5.5, "提高+": 7.0, "省选": 8.5, "NOI": 10.0}
DIFFICULTY_CUSTOM = "其他（自定义）"


def _nearest_difficulty(score) -> str:
    """把 0–10 难度分映射到最近的难度标签（AI 产出预填时用）。"""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "入门"
    return min(DIFFICULTY_LABEL_PRIOR, key=lambda k: abs(DIFFICULTY_LABEL_PRIOR[k] - s))


def _clear_form_state(prefix: str | None = None) -> None:
    """清理出题表单的控件状态（防止跨题目/跨会话串值）。"""
    for k in list(st.session_state.keys()):
        if k.startswith("pf_") and (prefix is None or k.startswith(prefix)):
            st.session_state.pop(k, None)

# ============================== 全局样式 ==============================

_BASE_CSS = """
<style>
/* 全局：浅灰留白背景 */
.stApp { background: #FAFAF8; }

/* 侧边栏导航：圆角矩形卡片按钮（单击即可切换） */
section[data-testid="stSidebar"] div[data-testid="stButton"] button {
  width: 100%;
  border-radius: 14px;
  border: 1.5px solid #E4DBF5;
  background: #FFFFFF;
  color: #4C1D95;
  font-weight: 600;
  padding: 0.6rem 0.9rem;
  text-align: left;
  box-shadow: 0 1px 2px rgba(76, 29, 149, 0.06);
  transition: all 0.15s ease;
}
section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover {
  background: #FBF1D6;
  border-color: #F0B429;
  color: #7A4A00;
  transform: translateY(-1px);
}
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] {
  background: linear-gradient(135deg, #7C3AED, #5B21B6);
  border-color: #5B21B6;
  color: #FFFFFF;
  box-shadow: 0 4px 12px rgba(109, 40, 217, 0.35);
}
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"]:hover {
  background: linear-gradient(135deg, #6D28D9, #4C1D95);
  color: #FFFFFF;
}
/* 退出登录：弱化处理 */
.st-key-logout button {
  background: transparent !important;
  border: 1px solid #E9E2F5 !important;
  color: #6B7280 !important;
  box-shadow: none !important;
}

/* 主区域按钮 */
div[data-testid="stButton"] button,
div[data-testid="stFormSubmitButton"] button {
  border-radius: 12px;
  font-weight: 600;
  transition: all 0.15s ease;
}
div[data-testid="stButton"] button[kind="secondary"] {
  border: 1.5px solid #DED3F2;
  color: #4C1D95;
  background: #FFFFFF;
}
div[data-testid="stButton"] button[kind="secondary"]:hover {
  border-color: #F0B429;
  color: #7A4A00;
  background: #FDF6E3;
}

/* 提交评测：黄色醒目按钮，与其它部分颜色区分 */
.st-key-submit_btn button,
.st-key-submit_btn button[kind="primary"] {
  background: linear-gradient(135deg, #FBBF24, #F59E0B) !important;
  border: 1px solid #D97706 !important;
  color: #451A03 !important;
  font-weight: 700 !important;
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.35) !important;
}
.st-key-submit_btn button:hover {
  background: linear-gradient(135deg, #F59E0B, #D97706) !important;
  color: #FFFFFF !important;
}

/* 圆角卡片 + 悬停变灰（题目卡片等） */
div[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: 16px !important;
  border: 1px solid #E9E3F2 !important;
  background: #FFFFFF;
  box-shadow: 0 1px 3px rgba(38, 34, 46, 0.05);
  transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
  background: #F0EFED !important;
  border-color: #DAD7D2 !important;
  box-shadow: 0 3px 10px rgba(38, 34, 46, 0.08);
}

/* number_input 加减号放大（出题表单 time_limit / memory_limit） */
div[data-testid="stNumberInput"] button {
  min-width: 2.2rem !important;
  height: 2.2rem !important;
  border-radius: 8px !important;
  font-size: 1.15rem !important;
}
div[data-testid="stNumberInput"] button:hover {
  background: #FBF1D6 !important;
  border-color: #F0B429 !important;
}
</style>
"""

# 登录页隐藏侧边栏：让登录/注册占据整个画幅
_HIDE_SIDEBAR_CSS = """
<style>
section[data-testid="stSidebar"] { display: none; }
div[data-testid="stMainBlockContainer"] { max-width: 56rem; }
</style>
"""


# ============================== 通用工具 ==============================

def _err(exc: ApiClientError) -> None:
    st.error(f"⚠️ {exc}")


def _json_parse(text: str, field: str):
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        st.error(f"{field} 不是合法 JSON：{exc}")
        return None
    if not isinstance(value, list):
        st.error(f"{field} 应为数组")
        return None
    return value


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)


def _reset_sub_state() -> None:
    """切换一级页面时清理所有二级页面状态（题库页码除外）。"""
    for key in ("view_problem_id", "submit_open", "manage_action", "ai_open",
                "query_problem_id", "query_params", "query_page", "query_detail_sid",
                "prefill_problem", "prefill_score"):
        st.session_state.pop(key, None)
    _clear_form_state()


def _goto(page: str) -> None:
    st.session_state["page"] = page
    _reset_sub_state()
    st.rerun()


def _flash(message: str) -> None:
    """跨 rerun 的轻提示（下一轮以 st.toast 展示）。"""
    st.session_state["flash"] = message


# ============================== 会话级 TTL 缓存 ==============================
# 说明：不用 st.cache_data 是因为取数依赖 st.session_state 里的 ApiClient（含登录 Cookie），
# 缓存函数不能访问 session_state；这里用 session 级 TTL 缓存，退出登录即随 session 清空。

_CACHE_TTL_SECONDS = 30


def _cache_get(key: str):
    entry = st.session_state.get(f"cache:{key}")
    if not isinstance(entry, dict):
        return None
    if time.time() - entry.get("ts", 0) > _CACHE_TTL_SECONDS:
        return None
    return entry.get("data")


def _cache_set(key: str, data) -> None:
    st.session_state[f"cache:{key}"] = {"ts": time.time(), "data": data}


def _clear_caches() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith("cache:"):
            st.session_state.pop(key, None)


def _get_problems_cached(client) -> list:
    data = _cache_get("problems")
    if data is None:
        data = client.get("/api/problems/")
        _cache_set("problems", data)
    return data


def _get_languages_cached(client) -> list:
    data = _cache_get("languages")
    if data is None:
        data = client.get("/api/languages/").get("name", [])
        _cache_set("languages", data)
    return data


# ============================== 登录 / 注册 ==============================

def render_auth_page() -> None:
    """未登录时的全画幅居中登录/注册页（注册成功自动登录并进入题库）。"""
    # 标题/副标题放全宽居中（窄列里 h1 会换行，如"测"字被挤到第二行），
    # 仅登录卡片用窄列包裹居中
    st.space("large")
    st.title("OJ 在线评测", icon=":material/rocket_launch:", text_alignment="center")
    st.caption("登录或注册，开启你的刷题之旅", text_alignment="center")
    st.space("medium")
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        with st.container(border=True):
            tab_login, tab_register = st.tabs(["登录", "注册"])
            with tab_login:
                _render_login_form()
            with tab_register:
                _render_register_form()


def _render_login_form() -> None:
    with st.form("login_form", border=False):
        username = st.text_input("用户名", placeholder="用户名（3–40 字符）")
        password = st.text_input("密码", type="password", placeholder="密码（至少 6 位）")
        submitted = st.form_submit_button("登 录", key="login_submit", type="primary", width="stretch")
    if not submitted:
        return
    if not (username.strip() and password):
        st.error("请输入用户名和密码")
        return
    client = get_client()
    try:
        data = client.login(username.strip(), password)
    except ApiClientError as exc:
        st.error(f"登录失败：{exc}")
        return
    st.session_state["user"] = data
    _flash(f"欢迎回来，{data.get('username')}！")
    _goto("problems")


def _render_register_form() -> None:
    with st.form("register_form", border=False):
        rname = st.text_input("用户名", placeholder="3–40 个字符")
        rpass = st.text_input("密码", type="password", placeholder="至少 6 位")
        rpass2 = st.text_input("确认密码", type="password")
        submitted = st.form_submit_button("注 册 并 登 录", key="register_submit", type="primary", width="stretch")
    if not submitted:
        return
    rname = rname.strip()
    if not rname or not rpass or not rpass2:
        st.error("请填写完整的注册信息")
        return
    if len(rname) < 3 or len(rname) > 40:
        st.error("用户名长度须为 3–40 个字符")
        return
    if len(rpass) < 6:
        st.error("密码长度至少 6 位")
        return
    if rpass != rpass2:
        st.error("两次输入的密码不一致")
        return
    client = get_client()
    try:
        client.register(rname, rpass)
    except ApiClientError as exc:
        st.error(f"注册失败：{exc}")
        return
    try:
        data = client.login(rname, rpass)
    except ApiClientError as exc:
        st.error(f"注册成功，但自动登录失败：{exc}")
        return
    st.session_state["user"] = data
    _flash(f"注册成功，欢迎加入，{data.get('username')}！")
    _goto("problems")


# ============================== 侧边栏 ==============================

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## :material/rocket_launch: OJ 评测")
        u = st.session_state.get("user", {})
        role = u.get("role", "user")
        st.markdown(f"**{u.get('username', '未知用户')}** · :violet-badge[{ROLE_TEXT.get(role, role)}]")
        st.space("small")
        page = st.session_state.get("page", "problems")
        for label, icon, key in NAV_ITEMS:
            active = page == key
            if st.button(f"{icon} {label}", key=f"nav_{key}",
                         type="primary" if active else "secondary", width="stretch"):
                _goto(key)
        st.space("medium")
        if st.button(":material/logout: 退出登录", key="logout", width="stretch"):
            _logout()


def _logout() -> None:
    get_client().logout()
    for key in list(st.session_state.keys()):
        st.session_state.pop(key)
    st.session_state["flash"] = "已退出登录"
    st.session_state["clear_session_cookie"] = True  # 下次渲染时清除浏览器 Cookie
    st.rerun()


# ============================== 会话持久化（浏览器 Cookie） ==============================

_SESSION_COOKIE_TTL = 7 * 24 * 3600  # 与后端 SESSION_TTL（7 天）一致


def _restore_session() -> bool:
    """浏览器刷新后：用浏览器 Cookie 里的后端会话 id 恢复登录态。

    身份仍然以后端会话为准（经 GET /api/auth/me 校验），Cookie 只存 uuid4 会话 id；
    会话失效（401）时标记清除浏览器 Cookie。
    """
    try:
        sid = st.context.cookies.get(SESSION_COOKIE)
    except Exception:
        sid = None
    # 防御：AppTest/异常上下文可能返回非字符串（如 MagicMock），只接受真实会话 id
    if not isinstance(sid, str) or not sid:
        return False
    client = get_client()
    client.set_session_id(sid)
    try:
        data = client.get("/api/auth/me")
    except ApiClientError as exc:
        if str(exc).startswith("401"):
            st.session_state["clear_session_cookie"] = True
        return False
    st.session_state["user"] = data
    return True


def _persist_browser_session() -> None:
    """把后端会话 id 写入浏览器 Cookie（1.63 的 st.context.cookies 只读，用 JS 写入）。

    幂等：每次渲染写入同值；AppTest/无浏览器上下文时不会执行 JS，无副作用。
    """
    sid = get_client().session_id
    if not sid:
        return
    st.html(
        f"<script>document.cookie='{SESSION_COOKIE}={sid}; path=/; max-age={_SESSION_COOKIE_TTL}; SameSite=Lax';</script>",
        unsafe_allow_javascript=True,
    )


def _clear_browser_session() -> None:
    st.html(
        f"<script>document.cookie='{SESSION_COOKIE}=; path=/; max-age=0';</script>",
        unsafe_allow_javascript=True,
    )


# ============================== 题库 ==============================

def render_problem_bank() -> None:
    view_pid = st.session_state.get("view_problem_id")
    if view_pid:
        render_problem_detail(view_pid)
        return
    st.title("题库", icon=":material/menu_book:")
    st.caption("选择一道题目开始你的旅程")
    search = st.text_input("搜索题目", placeholder="按编号或标题关键词搜索（仅匹配标题）",
                           key="bank_search", label_visibility="collapsed")
    client = get_client()
    try:
        problems = _get_problems_cached(client)
    except ApiClientError as exc:
        _err(exc)
        return
    if not problems:
        st.space("medium")
        st.markdown("### :material/inbox: 当前题库为空", text_alignment="center")
        st.caption("题目将在「题目管理」中创建，也可以交给 AI 命题生成。", text_alignment="center")
        _, c, _ = st.columns([1, 1, 1])
        if c.button("去题目管理", type="primary", width="stretch"):
            _goto("manage")
        return

    problems = sorted(problems, key=lambda p: str(p.get("id", "")))
    query = search.strip().lower()
    if st.session_state.get("bank_query_prev") != search:
        # 搜索词变化时回到第一页
        st.session_state["bank_query_prev"] = search
        st.session_state.pop("bank_page", None)
    if query:
        matched = [p for p in problems
                   if query in str(p.get("id", "")).lower()
                   or query in (p.get("title") or "").lower()]
        st.caption(f"搜索「{search.strip()}」：匹配 {len(matched)} 道题目")
        if not matched:
            st.info("未找到匹配的题目")
            return
        problems = matched
    total_pages = max(1, math.ceil(len(problems) / BANK_PAGE_SIZE))
    page_num = int(st.session_state.get("bank_page", 1) or 1)
    page_num = max(1, min(page_num, total_pages))
    st.session_state["bank_page"] = page_num
    start = (page_num - 1) * BANK_PAGE_SIZE
    for p in problems[start:start + BANK_PAGE_SIZE]:
        _render_problem_card(p)

    prev_col, info_col, next_col = st.columns([1, 2, 1], vertical_alignment="center")
    if prev_col.button("← 上一页", key="bank_prev", disabled=page_num <= 1, width="stretch"):
        st.session_state["bank_page"] = page_num - 1
        st.rerun()
    info_col.markdown(f"第 {page_num} / {total_pages} 页 · 共 {len(problems)} 道题目", text_alignment="center")
    if next_col.button("下一页 →", key="bank_next", disabled=page_num >= total_pages, width="stretch"):
        st.session_state["bank_page"] = page_num + 1
        st.rerun()


def _render_problem_card(p: dict) -> None:
    pid = str(p.get("id", ""))
    with st.container(border=True, key=f"pb_card_{pid}"):
        left, right = st.columns([2.6, 1], vertical_alignment="center")
        with left:
            st.markdown(f"### {p.get('title') or '未命名题目'}")
            badges = [f":violet-badge[{p.get('difficulty') or '难度未知'}]", f":gray-badge[#{pid}]"]
            badges += [f":gray-badge[{t}]" for t in (p.get("tags") or [])]
            st.markdown(" ".join(badges))
        with right:
            st.caption("通过率")
            st.progress(float(p.get("pass_rate") or 0.0))
            if st.button("进入题目", key=f"open_{pid}", type="primary", width="stretch"):
                st.session_state["view_problem_id"] = pid
                st.session_state.pop("submit_open", None)
                st.rerun()


# ============================== 题目详情（二级页） ==============================

def render_problem_detail(pid: str) -> None:
    client = get_client()
    if st.button(":material/arrow_back: 返回题库", key="back_to_bank"):
        st.session_state.pop("view_problem_id", None)
        st.session_state.pop("submit_open", None)
        st.rerun()
    try:
        p = client.get(f"/api/problems/{pid}")
    except ApiClientError as exc:
        _err(exc)
        st.warning("题目可能已被删除，请返回题库。")
        return

    left, right = st.columns([2.1, 1], gap="large")
    with right:
        _render_submit_panel(pid)
    with left:
        st.title(p.get("title") or "未命名题目", icon=":material/article:")
        badges = [f":violet-badge[{p.get('difficulty') or '难度未知'}]"]
        badges += [f":gray-badge[{t}]" for t in (p.get("tags") or [])]
        st.markdown(" ".join(badges))
        st.caption(f"题目编号 `{pid}` · ⏱ 时限 {p.get('time_limit', 3.0)}s · 🧠 内存 {p.get('memory_limit', 128)}MB · "
                   f"样例 {len(p.get('samples') or [])} 个")

        st.markdown("**题目描述**")
        st.markdown(p.get("description") or "—")
        st.markdown("**输入格式**")
        st.markdown(p.get("input_description") or "—")
        st.markdown("**输出格式**")
        st.markdown(p.get("output_description") or "—")
        samples = p.get("samples") or []
        if samples:
            st.markdown("**样例**")
            for i, s in enumerate(samples, 1):
                st.caption(f"样例 {i}")
                sc1, sc2 = st.columns(2)
                sc1.code(s.get("input", ""), language="text")
                sc2.code(s.get("output", ""), language="text")
        st.markdown("**数据范围与约束**")
        st.markdown(p.get("constraints") or "—")
        if p.get("hint"):
            st.markdown("**提示**")
            st.markdown(p["hint"])
        meta = []
        if p.get("source"):
            meta.append(f"来源：{p['source']}")
        if p.get("author"):
            meta.append(f"作者：{p['author']}")
        if meta:
            st.caption(" · ".join(meta))


def _render_submit_panel(pid: str) -> None:
    client = get_client()
    with st.container(border=True):
        st.markdown("#### :material/send: 提交")
        if not st.session_state.get("submit_open"):
            if st.button("✏️ 提交代码", key=f"start_submit_{pid}", type="primary", width="stretch"):
                st.session_state["submit_open"] = True
                st.rerun()
        else:
            try:
                languages = _get_languages_cached(client)
            except ApiClientError as exc:
                _err(exc)
                languages = []
            lang = st.selectbox("语言", languages or ["python"])
            code = st.text_area("代码", height=280, placeholder="# 在这里粘贴你的代码…",
                                label_visibility="collapsed")
            if st.button("🚀 提交评测", key="submit_btn", type="primary", width="stretch"):
                if not code.strip():
                    st.error("代码不能为空")
                else:
                    try:
                        data = client.post("/api/submissions/", json={
                            "problem_id": pid, "language": lang, "code": code,
                        })
                        _clear_caches()
                        _flash(f"已提交，评测中…（#{data.get('submission_id')}）")
                        st.rerun()
                    except ApiClientError as exc:
                        _err(exc)
    with st.container(border=True):
        st.markdown("#### :material/history: 近 3 次提交")
        _render_recent_submissions(pid)
        if st.button("查询提交记录", key=f"goto_query_{pid}", width="stretch"):
            st.session_state["page"] = "query"
            _reset_sub_state()
            st.session_state["query_problem_id"] = pid
            st.rerun()


@st.fragment(run_every=2)
def _render_recent_submissions(pid: str) -> None:
    """右侧栏近 3 次提交：每 2s 自动刷新，提交后无需手动刷新即可看到评测结果。"""
    client = get_client()
    try:
        data = client.get("/api/submissions/", params={
            "problem_id": pid, "page_size": RECENT_SUBMISSIONS,
        })
        items = data.get("submissions", [])
    except ApiClientError as exc:
        st.caption(f"加载失败：{exc}")
        return
    if not items:
        st.caption("暂无提交记录，来做第一个提交的人吧！")
        return
    header = st.columns(RECENT_COL_SPEC, vertical_alignment="center")
    for col, label in zip(header, ("状态", "得分", "语言", "时间")):
        col.caption(label)
    for s in items:
        _render_submission_row(s)


def _render_submission_row(s: dict) -> None:
    """近 3 次提交行：状态/得分/语言/时间 四列纵向对齐。"""
    status = s.get("status", "")
    score = f"{s.get('score', 0)}/{s.get('counts', 0)}" if status == "success" else "—"
    badge = _error_badge(get_client(), s.get("submission_id", "")) if status == "error" else _verdict_badge(s)
    cols = st.columns(RECENT_COL_SPEC, vertical_alignment="center")
    cols[0].markdown(badge)
    cols[1].markdown(score)
    cols[2].markdown(s.get("language", ""))
    cols[3].markdown(_fmt_time(s.get("created_at", "")))


# ============================== 查询提交记录 ==============================

def render_query_page() -> None:
    st.title("查询提交记录", icon=":material/query_stats:")
    st.caption("按题目或全部范围查询提交记录（时间倒序）；管理员可查看所有用户的提交。")
    client = get_client()
    me = st.session_state.get("user", {})
    is_admin = me.get("role") == "admin"
    try:
        problems = sorted(_get_problems_cached(client), key=lambda p: str(p.get("id", "")))
        users = client.get("/api/users/").get("users", []) if is_admin else []
    except ApiClientError as exc:
        _err(exc)
        return

    title_by_id = {p["id"]: p.get("title") for p in problems}
    pids = [p["id"] for p in problems]
    preselect_pid = st.session_state.pop("query_problem_id", None)
    options = [""] + pids
    if preselect_pid and preselect_pid in pids:
        st.session_state.pop("query_problem", None)  # 重置旧的选择控件状态以应用预选
        index = pids.index(preselect_pid) + 1
    else:
        index = 0
    problem_choice = st.selectbox(
        "题目",
        options,
        index=index,
        key="query_problem",
        format_func=lambda pid: "全部题目" if pid == "" else title_by_id.get(pid, "未知题目"),
    )

    scope = "self"
    if is_admin:
        user_labels = ["仅自己", "全部用户"] + [u["username"] for u in users]
        scope_label = st.selectbox("用户范围", user_labels, key="query_scope")
        if scope_label == "全部用户":
            scope = "all"
        elif scope_label != "仅自己":
            for u in users:
                if u["username"] == scope_label:
                    scope = f"user:{u['user_id']}"
                    break

    run_col, status_col = st.columns([1, 1], vertical_alignment="center")
    if run_col.button("查询", key="run_query", type="primary", width="stretch"):
        st.session_state["query_params"] = _build_query_params(me, problem_choice, scope)
        st.session_state["query_page"] = 1
        st.rerun()
    status_col.selectbox(
        "状态筛选", ["全部", "评测中", "通过", "部分通过", "未通过", "错误"],
        key="query_status",
    )

    params = st.session_state.get("query_params")
    if params is None:
        st.caption("选择范围后点击「查询」")
        return
    _render_query_results(client, me, title_by_id, params)


def _build_query_params(me: dict, problem_choice: str, scope: str) -> dict:
    """把查询页控件状态转换为后端 GET /api/submissions/ 参数。

    - 普通用户：仅自己（后端亦强制归一）；
    - 管理员 + 全部用户：scope=all 一次性取全部（后端 2026-09-08 新增，仅管理员）；
    - 不传 page_size：后端返回该范围内全部记录，前端自行分页，避免固定截断。
    """
    params: dict = {}
    if problem_choice:
        params["problem_id"] = problem_choice
    if scope == "self":
        params["user_id"] = me.get("user_id")
    elif scope.startswith("user:"):
        params["user_id"] = scope[len("user:"):]
    elif scope == "all":
        params["scope"] = "all"
    return params


@st.fragment(run_every=3)
def _render_query_results(client, me: dict, title_by_id: dict, params: dict) -> None:
    """查询结果区：每 3s 自动刷新（pending 提交无需手动刷新即变最终状态）。

    每次 rerun 都重新从后端取数，应用当前状态筛选后按 QUERY_PAGE_SIZE 分页。
    """
    status_filter = st.session_state.get("query_status", "全部")
    try:
        data = client.get("/api/submissions/", params=params)
        rows = data.get("submissions", [])
    except ApiClientError as exc:
        _err(exc)
        return
    if status_filter != "全部":
        rows = [r for r in rows if _verdict(r) == status_filter]
    if not rows:
        st.space("small")
        st.markdown("### :material/inbox: 暂无提交记录", text_alignment="center")
        st.caption("提交评测后，这里会按时间倒序显示记录。", text_alignment="center")
        return

    total_pages = max(1, math.ceil(len(rows) / QUERY_PAGE_SIZE))
    page_num = int(st.session_state.get("query_page", 1) or 1)
    page_num = max(1, min(page_num, total_pages))
    st.session_state["query_page"] = page_num
    start = (page_num - 1) * QUERY_PAGE_SIZE

    header = st.columns(QUERY_COL_SPEC, vertical_alignment="center")
    for col, label in zip(header, ("状态", "题目", "语言", "得分", "时间", "详情")):
        col.caption(label)
    for s in rows[start:start + QUERY_PAGE_SIZE]:
        _render_query_row(s, title_by_id, client, me)

    prev_col, info_col, next_col = st.columns([1, 2, 1], vertical_alignment="center")
    if prev_col.button("← 上一页", key="query_prev", disabled=page_num <= 1, width="stretch"):
        st.session_state["query_page"] = page_num - 1
        st.rerun()
    info_col.markdown(f"第 {page_num} / {total_pages} 页 · 共 {len(rows)} 条记录", text_alignment="center")
    if next_col.button("下一页 →", key="query_next", disabled=page_num >= total_pages, width="stretch"):
        st.session_state["query_page"] = page_num + 1
        st.rerun()


def _render_query_row(s: dict, title_by_id: dict, client, me: dict) -> None:
    """查询页行：状态/题目/语言/得分/时间 列对齐 + 行内详情按钮切换。"""
    sid = s.get("submission_id", "")
    title = title_by_id.get(s.get("problem_id"), s.get("problem_id") or "未知题目")
    score = f"{s.get('score', 0)}/{s.get('counts', 0)}" if s.get("status") == "success" else "—"
    open_now = st.session_state.get("query_detail_sid") == sid
    cols = st.columns(QUERY_COL_SPEC, vertical_alignment="center")
    cols[0].markdown(_error_badge(client, sid) if s.get("status") == "error" else _verdict_badge(s))
    cols[1].markdown(title)
    cols[2].markdown(f"`{s.get('language', '')}`")
    cols[3].markdown(score)
    cols[4].markdown(_fmt_time(s.get("created_at", "")))
    if cols[5].button("收起" if open_now else "详情", key=f"query_detail_{sid}", width="stretch"):
        if open_now:
            st.session_state.pop("query_detail_sid", None)
        else:
            st.session_state["query_detail_sid"] = sid
        st.rerun()
    if open_now:
        with st.container(border=True):
            show_detail_and_log(client, sid, me)


def show_detail_and_log(client, sid: str, me: dict) -> None:
    try:
        detail = client.get(f"/api/submissions/{sid}")
    except ApiClientError as exc:
        if str(exc).startswith("403"):
            st.warning("该提交详情仅本人或管理员可见")
        else:
            _err(exc)
        return
    status = detail.get("status")
    badge = _verdict_badge(detail)
    if status == "error":
        ci = detail.get("compile_info")
        badge = (":red-badge[编译错误]" if ci and str(ci.get("result", "")) == "compile error"
                 else ":red-badge[评测错误]")
    st.markdown(f"{badge} · "
                f"score={detail.get('score')}/{detail.get('counts')}")
    if me.get("role") == "admin":
        if st.button(":material/refresh: 重新评测", key=f"rejudge_{sid}"):
            try:
                client.put(f"/api/submissions/{sid}/rejudge")
                _clear_caches()
                _flash(f"已提交重新评测：{sid}")
                st.rerun()
            except ApiClientError as exc:
                _err(exc)
    with st.expander("代码", expanded=False):
        st.code(detail.get("code") or "", language=_code_language(detail.get("language")))
    ci = detail.get("compile_info")
    if ci:
        st.write(f"编译：{ci.get('result')} · {ci.get('message', '')[:500]}")
    st.write(f"运行：{(detail.get('run_info') or {}).get('message', '—')}")
    if detail.get("error_info"):
        st.error(detail["error_info"])
    try:
        log = client.get(f"/api/submissions/{sid}/log")
        details = log.get("details", [])
        if details:
            st.markdown("**测试点日志**（本人/管理员或题目公开）")
            st.markdown(_case_composition(details))
            st.table([[d.get("id"), d.get("result"), d.get("time"), d.get("memory")] for d in details])
        else:
            st.caption("无测试点明细（可能未公开、本人未公开题目、或该提交无日志）")
    except ApiClientError as exc:
        if str(exc).startswith("403"):
            st.warning("评测日志不可见（题目未公开且非本人）")
        else:
            _err(exc)


# ============================== 题目管理 ==============================

def render_manage_page() -> None:
    if st.session_state.get("ai_open"):
        render_ai_page()
        return
    action = st.session_state.get("manage_action")
    if action == "new":
        render_problem_form_page(None)
        return
    if isinstance(action, str) and action.startswith("edit:"):
        render_problem_form_page(action[len("edit:"):])
        return

    st.title("题目管理", icon=":material/table_chart:")
    st.caption("新增、编辑或删除题目；删除仅管理员可用。")
    search_col, btn_col = st.columns([2.6, 1], vertical_alignment="bottom")
    search = search_col.text_input("搜索题目", placeholder="按编号或标题关键词搜索（仅匹配标题）",
                                   label_visibility="collapsed")
    ai_col, new_col = btn_col.columns(2)
    if ai_col.button(":material/auto_awesome: AI 命题", key="open_ai", width="stretch"):
        st.session_state["ai_open"] = True
        st.rerun()
    if new_col.button(":material/add: 新增题目", key="new_problem", type="primary", width="stretch"):
        st.session_state["manage_action"] = "new"
        st.rerun()

    client = get_client()
    try:
        problems = _get_problems_cached(client)
    except ApiClientError as exc:
        _err(exc)
        return
    if not problems:
        st.space("medium")
        st.markdown("### :material/inbox: 当前题库为空", text_alignment="center")
        st.caption("点击右上角「新增题目」，或使用「AI 命题」生成后采纳。", text_alignment="center")
        return

    problems = sorted(problems, key=lambda p: str(p.get("id", "")))
    is_admin = st.session_state.get("user", {}).get("role") == "admin"
    pending_map = {} if is_admin else _pending_apply_map(client)
    query = search.strip().lower()
    if query:
        matched = [p for p in problems
                   if query in str(p.get("id", "")).lower()
                   or query in (p.get("title") or "").lower()]
        st.caption(f"搜索「{search.strip()}」：匹配 {len(matched)} 道题目")
        if not matched:
            st.info("未找到匹配的题目")
            return
    else:
        matched = problems
    for p in matched:
        _render_manage_card(p, pending_map)


def _pending_apply_map(client) -> dict[str, set[str]]:
    """普通用户当前 pending 申请：{problem_id: {action,...}}，用于卡片待审批标记。"""
    try:
        apps = client.get("/api/applications/").get("applications", [])
    except ApiClientError:
        return {}
    out: dict[str, set[str]] = {}
    for a in apps:
        if a.get("status") == "pending":
            out.setdefault(str(a.get("problem_id", "")), set()).add(a.get("action", ""))
    return out


def _render_manage_card(p: dict, pending_map: dict) -> None:
    pid = str(p.get("id", ""))
    title = p.get("title") or "未命名题目"
    pending = pending_map.get(pid, set())
    is_admin = st.session_state.get("user", {}).get("role") == "admin"
    with st.container(border=True, key=f"mg_card_{pid}"):
        left, right = st.columns([3, 1.4], vertical_alignment="center")
        with left:
            st.markdown(f"### {title}")
            badges = [f":violet-badge[{p.get('difficulty') or '难度未知'}]"]
            badges += [f":gray-badge[{t}]" for t in (p.get("tags") or [])]
            if "edit" in pending:
                badges.append(":orange-badge[修改待审批]")
            if "delete" in pending:
                badges.append(":orange-badge[删除待审批]")
            st.markdown(" ".join(badges))
        with right:
            edit_col, del_col = st.columns(2)
            if edit_col.button(":material/edit:", key=f"edit_{pid}", help=f"编辑「{title}」",
                               width="stretch", disabled="edit" in pending):
                st.session_state["manage_action"] = f"edit:{pid}"
                st.rerun()
            if del_col.button(":material/delete:", key=f"del_{pid}", help=f"删除「{title}」",
                              width="stretch", disabled="delete" in pending):
                if is_admin:
                    _confirm_delete(pid, title)
                else:
                    _confirm_delete_apply(pid, title)


@st.dialog("提交删除申请")
def _confirm_delete_apply(pid: str, title: str) -> None:
    """普通用户删除题目：提交申请，管理员审批后生效。"""
    st.warning(f"删除「{title}」需管理员审批。审批通过后，该题及其全部提交记录、相关日志将被删除。")
    col_ok, col_cancel = st.columns(2)
    if col_ok.button("提交申请", type="primary", width="stretch"):
        try:
            get_client().post(f"/api/problems/{pid}/apply", json={"action": "delete"})
        except ApiClientError as exc:
            st.error(str(exc))
            return
        _flash(f"已提交删除申请：{title}，等待管理员审批")
        st.rerun()
    if col_cancel.button("取消", width="stretch"):
        st.rerun()


@st.dialog("确认删除题目")
def _confirm_delete(pid: str, title: str) -> None:
    st.warning(f"将删除题目「{title}」，该题的全部提交记录与相关日志也会一并删除，且无法恢复。")
    col_ok, col_cancel = st.columns(2)
    if col_ok.button("确认删除", type="primary", width="stretch"):
        try:
            get_client().delete(f"/api/problems/{pid}")
        except ApiClientError as exc:
            st.error(str(exc))
            return
        _clear_caches()
        _flash(f"已删除题目：{title}")
        st.rerun()
    if col_cancel.button("取消", width="stretch"):
        st.rerun()


# ============================== 出题表单（新增 / 编辑） ==============================

def render_problem_form_page(edit_id: str | None) -> None:
    is_admin = st.session_state.get("user", {}).get("role") == "admin"
    if not edit_id:
        st.title("新增题目", icon=":material/edit_note:")
    else:
        st.title("编辑题目" if is_admin else "编辑题目（提交修改申请）", icon=":material/edit_note:")
        if not is_admin:
            st.caption("普通用户的修改将作为申请提交，管理员审批后才会生效。")
    if st.button(":material/arrow_back: 返回题目管理", key="back_manage"):
        st.session_state.pop("manage_action", None)
        st.session_state.pop("prefill_problem", None)
        st.session_state.pop("prefill_score", None)
        _clear_form_state()
        st.rerun()

    prefill = st.session_state.pop("prefill_problem", None)
    if prefill is not None and prefill.get("difficulty_score") is not None:
        # AI 产出预填：保留难度分作先验提示，随表单保存提交（不回显）
        st.session_state["prefill_score"] = float(prefill["difficulty_score"])
    if edit_id:
        st.session_state.pop("prefill_score", None)  # 编辑以服务端数据为准
        client = get_client()
        try:
            prefill = client.get(f"/api/problems/{edit_id}")
        except ApiClientError as exc:
            _err(exc)
            st.warning("题目可能已被删除，请返回题目管理。")
            return
    body = _problem_form_body(prefill, edit_id)
    if body is None:
        return
    client = get_client()
    try:
        if edit_id:
            body["id"] = edit_id
            if is_admin:
                client.put(f"/api/problems/{edit_id}", json=body)
                _clear_caches()
                _flash(f"题目已更新：{body['title']}")
            else:
                client.post(f"/api/problems/{edit_id}/apply",
                            json={"action": "edit", "payload": body})
                _flash(f"已提交修改申请：{body['title']}，等待管理员审批")
        else:
            client.post("/api/problems/", json=body)
            _clear_caches()
            _flash(f"题目已添加：{body['title']}")
    except ApiClientError as exc:
        _err(exc)
        return
    st.session_state.pop("manage_action", None)
    st.session_state.pop("prefill_score", None)
    _clear_form_state()
    st.rerun()


def _problem_form_body(prefill: dict | None = None, edit_id: str | None = None) -> dict | None:
    p = prefill or {}
    pfx = f"pf_{edit_id}" if edit_id else "pf_new"
    score_hint = st.session_state.get("prefill_score") if not edit_id else None

    # 难度：选择题（8 档 + 自定义），默认 = 当前值 / AI 难度分最近档 / 入门
    current_diff = str(p.get("difficulty") or "")
    if current_diff and current_diff not in DIFFICULTY_OPTIONS:
        diff_options = DIFFICULTY_OPTIONS + [DIFFICULTY_CUSTOM, current_diff]
    else:
        diff_options = DIFFICULTY_OPTIONS + [DIFFICULTY_CUSTOM]
    if current_diff:
        diff_default = current_diff
    elif score_hint is not None:
        diff_default = _nearest_difficulty(score_hint)
    else:
        diff_default = "入门"
    diff_index = diff_options.index(diff_default)

    with st.form("problem_form", border=False):
        c = st.columns([1, 2, 1])
        pid = c[0].text_input("编号 id *", value=p.get("id", ""), disabled=bool(edit_id),
                              help="题目唯一编号（编辑时不可修改）", key=f"{pfx}_id")
        title = c[1].text_input("标题 title *", value=p.get("title", ""), key=f"{pfx}_title")
        difficulty_choice = c[2].selectbox(
            "难度 *", diff_options, index=diff_index, key=f"{pfx}_difficulty",
            help="难度标签对接方案 D 先验映射（入门 1.0 … NOI 10.0）")
        if difficulty_choice == DIFFICULTY_CUSTOM:
            difficulty = st.text_input("自定义难度标签",
                                       value="" if current_diff in DIFFICULTY_OPTIONS else current_diff,
                                       key=f"{pfx}_difficulty_custom")
        else:
            difficulty = difficulty_choice
        description = st.text_area("题目描述 description *", value=p.get("description", ""),
                                   height=120, key=f"{pfx}_desc")
        c2 = st.columns(2)
        input_desc = c2[0].text_area("输入格式 input_description *", value=p.get("input_description", ""),
                                     height=70, key=f"{pfx}_in")
        output_desc = c2[1].text_area("输出格式 output_description *", value=p.get("output_description", ""),
                                      height=70, key=f"{pfx}_out")
        constraints = st.text_area("数据范围与约束 constraints *（数据范围/限制）",
                                   value=p.get("constraints", ""), height=50, key=f"{pfx}_constraints")
        c3 = st.columns(4)
        # polish：time_limit 步进 0.5s、memory_limit 步进 128MB，加减号已用 CSS 放大
        time_limit = c3[0].number_input("时限 time_limit（秒）", min_value=0.5,
                                        value=float(p.get("time_limit", 1.0)), step=0.5, format="%.1f",
                                        key=f"{pfx}_time")
        memory_limit = c3[1].number_input("内存 memory_limit（MB）", min_value=128,
                                          value=int(p.get("memory_limit", 128)), step=128,
                                          key=f"{pfx}_memory")
        source = c3[2].text_input("来源 source", value=p.get("source", ""), key=f"{pfx}_source")
        author = c3[3].text_input("作者 author", value=p.get("author", ""), key=f"{pfx}_author")
        hint = st.text_input("提示 hint（可选）", value=p.get("hint", ""), key=f"{pfx}_hint")
        tags = st.text_input("标签 tags（逗号分隔）", value=",".join(p.get("tags", [])),
                             key=f"{pfx}_tags")
        samples_text = st.text_area("样例 samples（JSON 数组 [{input,output}]）",
                                    value=_dump(p.get("samples", [])), height=120, key=f"{pfx}_samples")
        testcases_text = st.text_area("测试点 testcases（JSON 数组 [{input,output}]）",
                                      value=_dump(p.get("testcases", [])), height=220, key=f"{pfx}_testcases")
        submitted = st.form_submit_button("保存题目", type="primary", width="stretch")
    if not submitted:
        return None
    samples = _json_parse(samples_text, "samples")
    testcases = _json_parse(testcases_text, "testcases")
    if samples is None or testcases is None:
        return None
    if not (pid and title and description and input_desc and output_desc and constraints):
        st.error("id/title/description/input_description/output_description/constraints 为必填")
        return None
    body = {
        "id": pid, "title": title, "description": description,
        "input_description": input_desc, "output_description": output_desc,
        "constraints": constraints, "samples": samples, "testcases": testcases,
        "time_limit": float(time_limit), "memory_limit": int(memory_limit),
        "hint": hint, "source": source, "author": author, "difficulty": difficulty,
    }
    if score_hint is not None:
        # 方案 D 先验提示：AI 难度分随表单提交（后端仅作私有先验，不回传）
        body["difficulty_score"] = score_hint
    if tags.strip():
        body["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    return body


# ============================== 个人中心 ==============================

def _mark_read_and_go(client, n: dict, page: str, task_id=None, problem_id=None) -> None:
    try:
        client.put(f"/api/notifications/{n['notification_id']}/read")
    except ApiClientError:
        pass
    st.session_state["page"] = page
    if task_id:
        st.session_state["ai_monitor_task"] = task_id
    if problem_id:
        st.session_state["view_problem_id"] = problem_id
    st.rerun()


def _render_notifications(client, data: dict) -> None:
    notifications = data.get("notifications", [])
    unread = data.get("unread", 0)
    if not notifications:
        st.caption("暂无消息")
        return
    if unread:
        if st.button("全部标记已读", key="read_all_notifs"):
            try:
                client.put("/api/notifications/read-all")
                st.rerun()
            except ApiClientError as exc:
                _err(exc)
    for n in notifications:
        with st.container(border=True):
            badge = ":orange-badge[新]" if not n.get("read") else ":gray-badge[已读]"
            st.markdown(f"{badge} **{n.get('title')}** · {_fmt_time(n.get('created_at', ''))}")
            st.write(n.get("body", ""))
            actions = []
            if n.get("kind") == "ai_task" and n.get("task_id"):
                actions.append(("查看任务", "task"))
            elif n.get("kind") == "application" and n.get("problem_id"):
                actions.append(("查看题目", "problem"))
            if not n.get("read"):
                actions.append(("标记已读", "read"))
            if actions:
                cols = st.columns(len(actions))
                for col, (label, act) in zip(cols, actions):
                    key = f"n_{act}_{n['notification_id']}"
                    if col.button(label, key=key, width="stretch"):
                        if act == "read":
                            try:
                                client.put(f"/api/notifications/{n['notification_id']}/read")
                                st.rerun()
                            except ApiClientError as exc:
                                _err(exc)
                        elif act == "task":
                            _mark_read_and_go(client, n, "ai_monitor", task_id=n.get("task_id"))
                        else:
                            _mark_read_and_go(client, n, "problems", problem_id=n.get("problem_id"))


def render_profile_page() -> None:
    st.title("个人中心", icon=":material/person:")
    client = get_client()
    me = st.session_state.get("user", {})
    try:
        info = client.get(f"/api/users/{me.get('user_id')}")
        notif_data = client.get("/api/notifications/")
    except ApiClientError as exc:
        _err(exc)
        return
    unread = notif_data.get("unread", 0)

    with st.container(border=True):
        head_l, head_r = st.columns([2, 1], vertical_alignment="center")
        with head_l:
            st.markdown(f"### :material/account_circle: {info.get('username')}")
            st.markdown(f":violet-badge[{ROLE_TEXT.get(info.get('role'), info.get('role'))}]")
        with head_r:
            if unread:
                st.markdown(f":orange-badge[你有 {unread} 条新信息]")
            else:
                st.caption("没有新信息")
        c = st.columns(4)
        c[0].metric("提交数", info.get("submit_count"))
        c[1].metric("通过题目", info.get("resolve_count"))
        c[2].metric("角色", ROLE_TEXT.get(info.get('role'), info.get('role')))
        c[3].metric("加入时间", info.get("join_time"))

    if st.button(":material/query_stats: 查询我的提交记录", key="profile_query", type="primary"):
        _goto("query")

    st.space("medium")
    st.subheader("信息中心", icon=":material/notifications:")
    _render_notifications(client, notif_data)

    if me.get("role") != "admin":
        return
    st.space("medium")
    col_users, col_apps = st.columns(2, gap="large")
    with col_users:
        st.subheader("用户管理", icon=":material/admin_panel_settings:")
        user_query = st.text_input("搜索用户名", placeholder="按用户名关键词过滤",
                                   key="user_search", label_visibility="collapsed")
        try:
            users = client.get("/api/users/").get("users", [])
        except ApiClientError as exc:
            _err(exc)
            users = []
        if user_query.strip():
            q = user_query.strip().lower()
            users = [u for u in users if q in (u.get("username") or "").lower()]
            st.caption(f"搜索「{user_query.strip()}」：匹配 {len(users)} 个用户")
        if not users:
            st.caption("未找到匹配的用户")
        for u in users:
            _render_user_row(u, me, client)
    with col_apps:
        st.subheader("申请审批", icon=":material/approval:")
        _render_application_list(client)


def _render_user_row(u: dict, me: dict, client) -> None:
    with st.container(border=True):
        rc = st.columns([1.5, 2, 2.5, 1, 1])
        rc[0].markdown(f"**{u.get('username')}**")
        rc[1].markdown(f":violet-badge[{ROLE_TEXT.get(u.get('role'), u.get('role'))}]")
        rc[2].write(f"提交 {u.get('submit_count')} · 通过 {u.get('resolve_count')}")
        roles = ["user", "admin", "banned"]
        new_role = rc[3].selectbox(
            "role", roles,
            index=roles.index(u["role"]) if u["role"] in roles else 0,
            key=f"role_{u['user_id']}", label_visibility="collapsed")
        if rc[4].button("保存", key=f"save_{u['user_id']}", width="stretch"):
            if u["user_id"] == me.get("user_id") and new_role != "admin":
                st.warning("不能降级当前管理员账号（避免失去管理员）")
            else:
                try:
                    client.put(f"/api/users/{u['user_id']}/role", json={"role": new_role})
                    _flash(f"{u['username']} → {ROLE_TEXT.get(new_role, new_role)}")
                    st.rerun()
                except ApiClientError as exc:
                    _err(exc)


def _render_application_list(client) -> None:
    try:
        apps = client.get("/api/applications/").get("applications", [])
    except ApiClientError as exc:
        _err(exc)
        return
    scope = st.segmented_control("筛选", ["待处理", "全部"], default="待处理", key="app_filter")
    if scope == "待处理":
        apps = [a for a in apps if a.get("status") == "pending"]
    if not apps:
        st.caption("暂无申请")
        return
    for a in apps:
        _render_application_card(a, client)


def _render_application_card(a: dict, client) -> None:
    aid = a.get("application_id")
    action = "修改" if a.get("action") == "edit" else "删除"
    status = a.get("status")
    with st.container(border=True):
        st.markdown(f"**{a.get('problem_title') or a.get('problem_id')}** · :gray-badge[{action}申请]")
        st.caption(f"申请人 {a.get('username')} · {_fmt_time(a.get('created_at', ''))}")
        if a.get("action") == "edit" and a.get("payload"):
            with st.expander("查看修改内容"):
                pl = a["payload"]
                st.markdown(f"标题：**{pl.get('title', '')}** · 难度：{pl.get('difficulty', '')}")
                st.caption(f"时限 {pl.get('time_limit')}s · 内存 {pl.get('memory_limit')}MB · "
                           f"标签 {', '.join(pl.get('tags') or []) or '—'}")
        if status == "pending":
            c1, c2 = st.columns(2)
            if c1.button("接纳", key=f"accept_{aid}", type="primary", width="stretch"):
                try:
                    client.put(f"/api/applications/{aid}", json={"decision": "accept"})
                    _clear_caches()
                    _flash(f"已通过申请：{a.get('problem_title')}（{action}）")
                    st.rerun()
                except ApiClientError as exc:
                    st.error(str(exc))
            if c2.button("拒绝", key=f"reject_{aid}", width="stretch"):
                try:
                    client.put(f"/api/applications/{aid}", json={"decision": "reject"})
                    _flash(f"已拒绝申请：{a.get('problem_title')}")
                    st.rerun()
                except ApiClientError as exc:
                    st.error(str(exc))
        else:
            badge = ":green-badge[已接纳]" if status == "accepted" else ":red-badge[已拒绝]"
            st.markdown(f"{badge} · 处理人 {a.get('decided_by')}")
            if a.get("decision_note"):
                st.caption(f"原因：{a['decision_note']}")


# ============================== AI 命题（题目管理二级页） ==============================

def _available_languages() -> list[str]:
    try:
        return _get_languages_cached(get_client())
    except ApiClientError:
        return ["python", "cpp"]


def _available_problems() -> list[dict]:
    try:
        return _get_problems_cached(get_client())
    except ApiClientError:
        return []


def render_ai_page() -> None:
    st.title("AI 智能命题", icon=":material/auto_awesome:")
    back_col, monitor_col = st.columns([3, 1], vertical_alignment="center")
    if back_col.button(":material/arrow_back: 返回题目管理", key="back_ai"):
        st.session_state.pop("ai_open", None)
        st.rerun()
    if monitor_col.button(":material/monitoring: 查看进行中的任务", key="open_ai_monitor", width="stretch"):
        st.session_state["page"] = "ai_monitor"
        st.rerun()
    with st.expander("模型配置（per-user，OpenRouter 计价 / CNY）", expanded=False):
        _render_model_config()

    mode = st.segmented_control("输入方式", ["结构化表单", "纯文本"], default="结构化表单")
    requirement, language, problem_id, hardcore, retry_limit, ignore_complexity = "", None, None, False, 2, False
    if mode == "结构化表单":
        languages = _available_languages()
        if not languages:
            return
        c1, c2, c3 = st.columns(3)
        with c1:
            language = st.selectbox("语言（必选）", languages,
                                    index=languages.index("python") if "python" in languages else 0)
        with c2:
            difficulty = st.select_slider("难度分", options=list(range(1, 11)), value=3)
        with c3:
            complexity_choice = st.selectbox("预期复杂度", ["不考察复杂度"] + COMPLEXITY_OPTIONS)
        ignore_complexity = complexity_choice == "不考察复杂度"
        complexity = "" if ignore_complexity else complexity_choice
        if complexity_choice == "其他":
            complexity = st.text_input("自定义复杂度", key="complexity_other")
        tags = st.multiselect("考点（可多选）", TAG_OPTIONS)
        if "其他" in tags:
            extra = st.text_input("自定义考点", key="tag_other")
            if extra:
                tags = tags[:]
        scale_choice = st.selectbox("数据规模", SCALE_OPTIONS)
        scale = scale_choice
        if scale_choice == "其他":
            scale = st.text_input("自定义规模", key="scale_other")
        background = st.text_area("情景/背景故事（可选）", key="ai_bg")
        note = st.text_area("备注（可选）", key="ai_note")
        problems = _available_problems()
        ref_opts = [p["id"] for p in problems]
        title_by_id = {p["id"]: p.get("title") or "未命名题目" for p in problems}
        ref = st.selectbox(
            "站内参考题（可选）",
            [""] + ref_opts,
            format_func=lambda pid: "（无）" if pid == "" else f"{str(pid).ljust(12)} {title_by_id.get(pid, '')}",
        )
        problem_id = ref or None
        c4, c5 = st.columns(2)
        with c4:
            hardcore = st.checkbox("硬核模式（对拍校验测试数据）", value=False, key="hardcore")
        with c5:
            retry_limit = st.slider("重试次数（JSON/对拍失败）", 0, 5, 2)
        parts = [f"题目要求：{background or '设计一道算法题'}", f"难度分：{difficulty}/10"]
        if tags:
            parts.append(f"考点：{'、'.join(t for t in tags if t != '其他')}")
        if complexity:
            parts.append(f"预期复杂度：{complexity}")
        if scale:
            parts.append(f"数据规模：{scale}")
        if note:
            parts.append(f"备注：{note}")
        requirement = "\n".join(parts)
    else:
        requirement = st.text_area("用自然语言描述命题需求（可附站内题目链接）", key="pure_req", height=160)
        uploaded = st.file_uploader("上传背景资料（文本类；纯文本模型无法观看图片）", type=["txt", "md", "csv", "json"])
        if uploaded is not None:
            requirement = f"{requirement}\n\n【上传资料】\n{uploaded.getvalue().decode('utf-8', errors='replace')[:6000]}"
        c6, c7 = st.columns(2)
        with c6:
            hardcore = st.checkbox("硬核模式（对拍校验测试数据）", value=False, key="hardcore_txt")
        with c7:
            retry_limit = st.slider("重试次数（JSON/对拍失败）", 0, 5, 2, key="retry_txt")

    if st.button("🚀 生成题目", type="primary"):
        if not requirement.strip():
            st.error("命题需求不能为空")
            return
        body = {"requirement": requirement, "hardcore": hardcore, "retry_limit": retry_limit,
                "ignore_complexity": ignore_complexity}
        if language:
            body["language"] = language
        if problem_id:
            body["problem_id"] = problem_id
        try:
            data = get_client().post("/api/ai/problem-tasks/", json=body)
            st.session_state["ai_task_id"] = data.get("task_id")
            st.success(f"任务已创建：{data.get('task_id')}")
        except ApiClientError as exc:
            _err(exc)
    if st.session_state.get("ai_task_id"):
        render_task_progress(st.session_state["ai_task_id"])


def _fmt_elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _iso_seconds(value) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except ValueError:
        return None


@st.fragment(run_every=2)
def render_task_progress(task_id: str) -> None:
    client = get_client()
    try:
        data = client.get(f"/api/ai/problem-tasks/{task_id}")
    except ApiClientError as exc:
        st.warning(str(exc))
        return
    status = data.get("status")
    phase = data.get("phase", "")
    progress = data.get("progress", "")

    st.subheader(f"任务 {task_id}")
    head_l, head_r = st.columns([3, 1], vertical_alignment="center")
    with head_l:
        st.markdown(f"状态：**{status}** · 阶段：**{progress or phase or '—'}**")
    with head_r:
        if status in ("waiting", "running"):
            if st.button("终止任务", key=f"cancel_ai_{task_id}", width="stretch"):
                try:
                    client.put(f"/api/ai/problem-tasks/{task_id}/cancel")
                    st.rerun()
                except ApiClientError as exc:
                    _err(exc)
    st.caption("每 2 秒自动刷新")

    started = data.get("started_at") or data.get("created_at")
    finished = data.get("finished_at")
    start_ts = _iso_seconds(started)
    end_ts = _iso_seconds(finished) if finished else None
    elapsed = None
    if start_ts is not None:
        elapsed = (end_ts if end_ts else datetime.now().timestamp()) - start_ts

    usage = data.get("usage") or {}
    in_tok = usage.get("input_tokens", 0)
    out_tok = usage.get("output_tokens", 0)
    total_tok = usage.get("total_tokens", in_tok + out_tok)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("已用时间", _fmt_elapsed(elapsed) if elapsed is not None else "—")
    c2.metric("Token 总数", total_tok)
    c3.metric("输入 / 输出", f"{in_tok} / {out_tok}")
    c4.metric("估算费用", f"¥{usage.get('cost', 0):.4f}")
    if usage.get("fx_rate"):
        st.caption(f"自动汇率 {usage['fx_rate']}（{usage.get('fx_source', '')}）· {usage.get('currency', 'CNY')}")
    if data.get("attempts"):
        st.caption(f"重试 {data.get('attempts', 0)} 次（最多 {data.get('retry_limit', 0) + 1} 次）")
    if data.get("hardcore"):
        st.caption("硬核模式 · 对拍校验开启")
    if data.get("ignore_complexity"):
        st.caption("本题不考察复杂度（强化边界/极端用例）")

    if data.get("review"):
        st.warning(f"需人工复核：{data.get('review_note', '')}")
    if data.get("error"):
        st.error(data["error"])
    result = data.get("result")
    if result:
        st.success(f"命题完成：{result.get('title', '')}（语言 {result.get('language', '')}，"
                   f"测试点 {len(result.get('testcases', []))} 个）")
        if st.button("✏️ 采纳到题目编辑（预填）", type="primary"):
            _clear_form_state("pf_new_")  # AI 预填覆盖旧草稿
            st.session_state["prefill_problem"] = result
            st.session_state["manage_action"] = "new"
            st.session_state["page"] = "manage"
            st.session_state.pop("ai_open", None)
            st.rerun()
        with st.expander("查看产出 JSON"):
            st.json(result)
    elif data.get("review"):
        if st.button("🔄 以相同需求重试（新任务）"):
            body = {"requirement": data.get("requirement", ""), "hardcore": True,
                    "retry_limit": data.get("retry_limit", 2),
                    "ignore_complexity": data.get("ignore_complexity", False)}
            if data.get("language"):
                body["language"] = data["language"]
            try:
                nd = client.post("/api/ai/problem-tasks/", json=body)
                st.session_state["ai_task_id"] = nd.get("task_id")
                st.rerun()
            except ApiClientError as exc:
                _err(exc)


def render_ai_monitor_page() -> None:
    st.title("AI 命题监控", icon=":material/monitoring:")
    back_col, refresh_col = st.columns([3, 1], vertical_alignment="center")
    if back_col.button(":material/arrow_back: 返回 AI 命题", key="back_from_monitor"):
        st.session_state["page"] = "manage"
        st.session_state["ai_open"] = True
        st.rerun()
    if refresh_col.button(":material/refresh: 刷新任务列表", key="refresh_monitor", width="stretch"):
        st.rerun()
    client = get_client()
    try:
        data = client.get("/api/ai/problem-tasks/")
        tasks = data.get("tasks", [])
    except ApiClientError as exc:
        _err(exc)
        return
    if not tasks:
        st.space("medium")
        st.markdown("### :material/inbox: 暂无 AI 命题任务", text_alignment="center")
        st.caption("在 AI 命题页创建任务后会显示在这里。", text_alignment="center")
        return
    task_ids = [t.get("task_id") for t in tasks]
    current = st.session_state.get("ai_monitor_task")
    if current not in task_ids:
        current = task_ids[0]
        st.session_state["ai_monitor_task"] = current
    label_by_id = {
        t["task_id"]: f"{t['task_id']} · {t.get('status')} · {t.get('progress') or t.get('phase')}"
        for t in tasks
    }
    selected = st.selectbox(
        "选择任务", task_ids, index=task_ids.index(current),
        key="ai_monitor_select",
        format_func=lambda tid: label_by_id.get(tid, tid),
    )
    st.session_state["ai_monitor_task"] = selected
    render_task_progress(selected)


def _render_model_config() -> None:
    client = get_client()
    st.caption("选择模型并填写 API Key（支持 OpenRouter、DeepSeek 官方与千问官方直连）；"
               "模型单价与汇率由系统自动获取真实数据，无需手工填写。不填 Key 走本地 mock。")
    try:
        catalog_data = client.get("/api/ai/models")
        cfg = client.get("/api/ai/model-config")
    except ApiClientError as exc:
        _err(exc)
        return
    models = catalog_data.get("models", [])
    source = catalog_data.get("source", "builtin")
    model_by_id = {m["id"]: m for m in models}
    CUSTOM_MODEL = "__custom__"
    options = [m["id"] for m in models] + [CUSTOM_MODEL]
    current_model = cfg.get("model") or ""
    custom_prefill = ""
    if current_model and current_model in model_by_id:
        index = options.index(current_model)
    else:
        # 旧配置/不在目录的模型：选中“自定义模型…”并预填原 id，保留可见可编辑
        index = options.index(CUSTOM_MODEL)
        if current_model:
            custom_prefill = current_model

    with st.form("ai_cfg_form"):
        model = st.selectbox(
            "模型",
            options,
            index=index,
            key="ai_model",
            format_func=lambda mid: ("自定义模型…" if mid == CUSTOM_MODEL else
                                     f"{model_by_id[mid]['name']}（{mid}）" if mid in model_by_id else mid),
        )
        if model == CUSTOM_MODEL:
            custom_model = st.text_input(
                "自定义模型 id",
                value=custom_prefill,
                placeholder="如 deepseek-v4-flash / qwen-plus（官方直连）",
                key="ai_model_custom",
                help="填 provider 侧的真实模型 id；官方直连不带厂商前缀（deepseek-chat / deepseek-reasoner 已弃用）。")
        else:
            custom_model = ""
        key = st.text_input("API Key", type="password", key="ai_key",
                            value=st.session_state.get("ai_key_display", ""),
                            help="留空走本地 mock 演示；Key 仅存本地、不回显。"
                                 "OpenRouter、DeepSeek 官方与千问官方 key 均支持，与 provider_url 配套使用。")
        with st.expander("高级（可选）"):
            provider = st.text_input("provider_url",
                                     value=cfg.get("provider_url") or "https://openrouter.ai/api/v1",
                                     key="ai_provider",
                                     help="OpenAI 兼容接口基址。OpenRouter 填 https://openrouter.ai/api/v1；"
                                          "DeepSeek 官方填 https://api.deepseek.com；"
                                          "千问官方填 https://dashscope.aliyuncs.com/compatible-mode/v1。")
            st.caption("OpenRouter：模型用厂商前缀 id（如 deepseek/deepseek-v4-pro），Key 用 OpenRouter 的 key；"
                       "DeepSeek 官方：模型用 deepseek-v4-flash / deepseek-v4-pro（不带前缀），Key 用官网 key；"
                       "千问官方：模型用 qwen-turbo / qwen-plus / qwen-max（不带前缀），"
                       "provider_url 填 https://dashscope.aliyuncs.com/compatible-mode/v1，Key 用官网 key。"
                       "旧 id deepseek-chat / deepseek-reasoner 已弃用；"
                       "混用（OpenRouter 模型 id 配官方地址）会报 Model Not Exist。")
        submitted = st.form_submit_button("保存配置", key="ai_cfg_save", type="primary", width="stretch")

    # 选中模型的真实单价（自动获取，随选择即时更新）
    chosen_model = custom_model.strip() if model == CUSTOM_MODEL else model
    sel = model_by_id.get(chosen_model)
    if sel:
        st.markdown(f":material/sell: **{sel['name']}** · `{sel['id']}`")
        st.markdown(f"输入 **{sel['input_price']}** USD/1M tokens · 输出 **{sel['output_price']}** USD/1M tokens")
        if sel.get("description"):
            st.caption(sel["description"])
    else:
        st.caption(f"模型「{chosen_model or '未填写'}」不在目录中（自定义模型），单价按已存配置计算。")
    fx_src = {"frankfurter": "实时汇率（Frankfurter/ECB）",
              "builtin": "内置参考汇率（实时获取失败，稍后自动重试）"}.get(cfg.get("fx_source"), cfg.get("fx_source") or "—")
    src_label = {"openrouter": "OpenRouter 实时目录",
                 "openrouter+builtin": "OpenRouter 实时目录 + 内置补充",
                 "builtin": "内置离线目录"}.get(source, source)
    st.caption(f"汇率 USD→CNY：**{cfg.get('fx_rate')}**（{fx_src}）· 模型目录来源：{src_label}")
    if submitted:
        st.session_state["ai_key_display"] = key
        try:
            data = client.put("/api/ai/model-config", json={
                "provider_url": provider, "model": chosen_model, "api_key": key,
            })
            st.success(f"已保存：{data.get('model')}")
        except ApiClientError as exc:
            _err(exc)
    st.caption("计价：费用 = token/1M × 模型真实单价(USD) × 自动汇率，CNY 展示。")


# ============================== 入口 ==============================

def main() -> None:
    st.set_page_config(page_title="OJ 评测系统", page_icon=":material/rocket_launch:", layout="wide")
    authed = "user" in st.session_state
    if not authed:
        authed = _restore_session()  # 刷新后从浏览器 Cookie 恢复登录态
    if authed:
        st.html(_BASE_CSS)
        _persist_browser_session()
    else:
        # 登录/注册占据整个画幅：隐藏侧边栏
        st.html(_BASE_CSS + _HIDE_SIDEBAR_CSS)
        if st.session_state.pop("clear_session_cookie", False):
            _clear_browser_session()
    flash = st.session_state.pop("flash", None)
    if flash:
        st.toast(flash)
    if not authed:
        render_auth_page()
        return
    render_sidebar()
    page = st.session_state.get("page", "problems")
    if page == "problems":
        render_problem_bank()
    elif page == "manage":
        render_manage_page()
    elif page == "query":
        render_query_page()
    elif page == "ai_monitor":
        render_ai_monitor_page()
    else:
        render_profile_page()


if __name__ == "__main__":
    main()
