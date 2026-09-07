"""OJ 前端（Streamlit，Step6 + AI 命题）。前后端分离：仅经 REST API + Cookie 会话与 FastAPI 后端交互。

启动（backend 先起在 8000）：
    ../.venv/Scripts/python.exe -m streamlit run app.py --server.port 8501   # Windows
页面组：用户（登录/注册/信息/管理）、题目（列表/详情/新增/编辑/删除）、
评测与提交（提交/列表/详情/日志）、AI 命题（两界面/硬核对拍/产出预填题目编辑）。
"""
import json
import time

import streamlit as st

from api_client import ApiClientError, get_client

TAG_OPTIONS = [
    "模拟", "枚举", "贪心", "二分", "双指针", "排序", "数学", "数论", "动态规划",
    "搜索/DFS", "BFS", "图论", "最短路", "最小生成树", "字符串", "前缀和", "差分", "位运算",
    "高精度", "分治", "递归", "哈希", "并查集", "数据结构", "栈/队列", "堆", "树", "其他",
]
COMPLEXITY_OPTIONS = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "其他"]
SCALE_OPTIONS = ["小（n<=10^3）", "中（n<=10^5）", "大（n<=10^7）", "其他"]
PAGES = ["AI 命题", "题目", "评测", "用户"]


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


# ============================== 登录侧栏 ==============================

def render_login_sidebar() -> None:
    st.sidebar.title("OJ 系统")
    client = get_client()
    if "user" in st.session_state:
        u = st.session_state["user"]
        st.sidebar.write(f"👤 {u.get('username')}（{u.get('role')}）")
        if st.sidebar.button("退出登录"):
            client.logout()
            for key in ("user", "api_client", "ai_task_id", "prefill_problem"):
                st.session_state.pop(key, None)
            st.rerun()
        return
    st.sidebar.subheader("登录")
    with st.sidebar.form("login_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        if st.form_submit_button("登录"):
            try:
                data = client.login(username, password)
                st.session_state["user"] = data
                st.rerun()
            except ApiClientError as exc:
                st.sidebar.error(str(exc))
    if st.sidebar.checkbox("注册新账号"):
        with st.sidebar.form("reg_form"):
            rname = st.text_input("新用户名")
            rpass = st.text_input("新密码", type="password")
            if st.form_submit_button("注册"):
                try:
                    client.register(rname, rpass)
                    st.sidebar.success("注册成功，请登录")
                except ApiClientError as exc:
                    st.sidebar.error(str(exc))


# ============================== 题目页面组 ==============================

REQUIRED_KEYS = ["id", "title", "description", "input_description", "output_description",
                 "constraints"]
OPTIONAL_TEXT = ["hint", "source", "author", "difficulty"]


def _problem_form_body(prefill: dict | None = None) -> dict | None:
    p = prefill or {}
    with st.form("problem_form"):
        c = st.columns(3)
        pid = c[0].text_input("id*", value=p.get("id", ""))
        title = c[1].text_input("title*", value=p.get("title", ""))
        difficulty = c[2].text_input("difficulty(标签)", value=p.get("difficulty", ""))
        description = st.text_area("description*", value=p.get("description", ""), height=120)
        c2 = st.columns(2)
        input_desc = c2[0].text_area("input_description*", value=p.get("input_description", ""), height=70)
        output_desc = c2[1].text_area("output_description*", value=p.get("output_description", ""), height=70)
        constraints = st.text_area("constraints*（数据范围/限制）", value=p.get("constraints", ""), height=50)
        c3 = st.columns(4)
        time_limit = c3[0].number_input("time_limit(s)", min_value=0.1, value=float(p.get("time_limit", 3.0)), format="%.1f")
        memory_limit = c3[1].number_input("memory_limit(MB)", min_value=1, value=int(p.get("memory_limit", 128)))
        source = c3[2].text_input("source", value=p.get("source", ""))
        author = c3[3].text_input("author", value=p.get("author", ""))
        hint = st.text_input("hint(可选)", value=p.get("hint", ""))
        tags = st.text_input("tags(逗号分隔)", value=",".join(p.get("tags", [])))
        samples_text = st.text_area("samples（JSON 数组 [{input,output}]）", value=_dump(p.get("samples", [])), height=120)
        testcases_text = st.text_area("testcases（JSON 数组 [{input,output}]）", value=_dump(p.get("testcases", [])), height=220)
        submitted = st.form_submit_button("保存题目")
    if not submitted:
        return None
    samples = _json_parse(samples_text, "samples")
    testcases = _json_parse(testcases_text, "testcases")
    if samples is None or testcases is None:
        return None
    if not (pid and title and description and constraints):
        st.error("id/title/description/constraints 为必填")
        return None
    body = {
        "id": pid, "title": title, "description": description,
        "input_description": input_desc, "output_description": output_desc,
        "constraints": constraints, "samples": samples, "testcases": testcases,
        "time_limit": float(time_limit), "memory_limit": int(memory_limit),
        "hint": hint, "source": source, "author": author, "difficulty": difficulty,
    }
    if tags.strip():
        body["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    return body


def render_problems_page() -> None:
    st.header("📚 题目管理")
    client = get_client()
    # 采纳 AI 产出 → 自动打开新增表单并预填
    prefill = st.session_state.pop("prefill_problem", None)
    action = st.session_state.pop("problem_action", "新建")
    edit_id = st.session_state.pop("problem_edit_id", None)

    if st.button("＋ 新建题目"):
        st.session_state["problem_action"] = "新建"
        st.rerun()
    if edit_id:
        try:
            detail = client.get(f"/api/problems/{edit_id}")
            st.session_state["prefill_problem"] = detail
            st.session_state["problem_action"] = "编辑"
            st.rerun()
        except ApiClientError as exc:
            _err(exc)

    if action == "编辑" and prefill:
        st.subheader(f"编辑题目 {prefill.get('id')}")
        body = _problem_form_body(prefill)
        if body:
            if body["id"] != prefill.get("id"):
                body["id"] = prefill.get("id")
            try:
                client.put(f"/api/problems/{prefill.get('id')}", json=body)
                st.success("题目已更新")
                st.rerun()
            except ApiClientError as exc:
                _err(exc)
    elif action == "新建":
        st.subheader("新增题目" + ("（已预填 AI 产出，可编辑）" if prefill else ""))
        body = _problem_form_body(prefill)
        if body:
            try:
                client.post("/api/problems/", json=body)
                st.success("题目已添加")
                st.rerun()
            except ApiClientError as exc:
                _err(exc)
    st.divider()

    try:
        problems = client.get("/api/problems/")
    except ApiClientError as exc:
        _err(exc)
        return
    if not problems:
        st.info("题库为空。可新建题目，或使用 AI 命题生成后采纳。")
        return
    is_admin = st.session_state.get("user", {}).get("role") == "admin"
    for p in problems:
        c = st.columns([3, 2, 1, 1, 1])
        c[0].write(f"**{p['id']}** · {p['title']}")
        if c[1].button("详情", key=f"view_{p['id']}"):
            st.session_state["problem_edit_id"] = p["id"]
            st.session_state["problem_view"] = True
            st.rerun()
        if c[2].button("编辑", key=f"edit_{p['id']}"):
            st.session_state["problem_edit_id"] = p["id"]
            st.session_state["problem_action"] = "编辑"
            st.rerun()
        if c[3].button("删除", key=f"del_{p['id']}"):
            if is_admin:
                try:
                    client.delete(f"/api/problems/{p['id']}")
                    st.success(f"已删除 {p['id']}")
                    st.rerun()
                except ApiClientError as exc:
                    _err(exc)
            else:
                st.warning("仅管理员可删除题目")
        with c[4].expander("预览"):
            try:
                detail = client.get(f"/api/problems/{p['id']}")
            except ApiClientError as exc:
                _err(exc)
                continue
            st.write(detail.get("description", ""))
            st.markdown(f"**输入**：{detail.get('input_description','')}")
            st.markdown(f"**输出**：{detail.get('output_description','')}")
            st.markdown(f"**限制**：{detail.get('constraints','')}")
            st.caption(f"样例 {len(detail.get('samples',[]))} 个 · 测试点 {len(detail.get('testcases',[]))} 个 · "
                       f"限时 {detail.get('time_limit')}s / {detail.get('memory_limit')}MB")


# ============================== 评测页面组 ==============================

def render_submissions_page() -> None:
    st.header("🧪 评测与提交")
    client = get_client()
    me = st.session_state["user"]

    st.subheader("提交代码")
    try:
        problems = client.get("/api/problems/")
        languages = client.get("/api/languages/").get("name", [])
    except ApiClientError as exc:
        _err(exc)
        return
    with st.form("submit_form"):
        c = st.columns(2)
        pids = [p["id"] for p in problems]
        pid = c[0].selectbox("题目", pids) if pids else c[0].text_input("题目 id")
        lang = c[1].selectbox("语言", languages) if languages else c[1].text_input("语言")
        code = st.text_area("代码", height=180)
        if st.form_submit_button("提交评测"):
            if not pids and not (pid and lang):
                st.error("请先创建题目或选择语言")
            else:
                try:
                    data = client.post("/api/submissions/", json={"problem_id": pid, "language": lang, "code": code})
                    st.success(f"已提交：{data.get('submission_id')}（异步评测中）")
                    st.session_state["watch_sid"] = data.get("submission_id")
                except ApiClientError as exc:
                    _err(exc)

    st.subheader("我的提交记录")
    with st.form("list_filter"):
        c = st.columns(3)
        user_id = c[0].text_input("user_id（留空=仅自己）", value="")
        problem = c[1].text_input("problem_id（可选）")
        status = c[2].selectbox("status", ["", "pending", "success", "error"])
        if st.form_submit_button("查询"):
            params = {}
            if me.get("role") == "admin" and user_id.strip():
                params["user_id"] = user_id.strip()
            elif user_id.strip():
                st.warning("普通用户只能查自己的提交")
            if problem.strip():
                params["problem_id"] = problem.strip()
            if status:
                params["status"] = status
            if not params:
                params = {"user_id": me.get("user_id")}
            try:
                data = client.get(f"/api/submissions/?{'&'.join(f'{k}={v}' for k, v in params.items())}")
                st.session_state["sub_list"] = data.get("submissions", [])
            except ApiClientError as exc:
                _err(exc)
    sub_list = st.session_state.get("sub_list", [])
    if sub_list:
        rows = []
        for s in sub_list:
            if s.get("status") == "success":
                rows.append([s["submission_id"], s["status"], s.get("score", 0), s.get("counts", 0)])
            else:
                rows.append([s["submission_id"], s["status"], "-", "-"])
        st.table(rows)
        sids = [r[0] for r in rows]
        target = st.selectbox("查看详情/日志", ["--"] + sids)
        if target != "--":
            show_detail_and_log(client, target, me)


def show_detail_and_log(client, sid: str, me: dict) -> None:
    try:
        detail = client.get(f"/api/submissions/{sid}")
    except ApiClientError as exc:
        if str(exc).startswith("403"):
            st.warning("该提交详情仅本人或管理员可见")
        else:
            _err(exc)
        return
    st.markdown(f"**{sid}** · status=`{detail.get('status')}` · "
                f"score={detail.get('score')}/{detail.get('counts')}")
    with st.expander("代码", expanded=False):
        st.code(detail.get("code", ""), language="python")
    ci = detail.get("compile_info")
    if ci:
        st.write(f"编译：{ci.get('result')} · {ci.get('message','')[:500]}")
    st.write(f"运行：{(detail.get('run_info') or {}).get('message', '—')}")
    if detail.get("error_info"):
        st.error(detail["error_info"])
    try:
        log = client.get(f"/api/submissions/{sid}/log")
        details = log.get("details", [])
        if details:
            st.markdown("**测试点日志**（本人/管理员或题目公开）")
            st.table([[d.get("id"), d.get("result"), d.get("time"), d.get("memory")] for d in details])
        else:
            st.caption("无测试点明细（可能未公开、本人未公开题目、或该提交无日志）")
    except ApiClientError as exc:
        if str(exc).startswith("403"):
            st.warning("评测日志不可见（题目未公开且非本人）")
        else:
            _err(exc)


# ============================== 用户页面组 ==============================

def render_users_page() -> None:
    st.header("👥 用户")
    client = get_client()
    me = st.session_state["user"]
    try:
        info = client.get(f"/api/users/{me.get('user_id')}")
    except ApiClientError as exc:
        _err(exc)
        return
    c = st.columns(4)
    c[0].metric("用户名", info.get("username"))
    c[1].metric("角色", info.get("role"))
    c[2].metric("提交数", info.get("submit_count"))
    c[3].metric("通过数", info.get("resolve_count"))
    st.caption(f"加入时间：{info.get('join_time')}")

    if me.get("role") != "admin":
        st.info("用户管理仅管理员可见")
        return
    st.divider()
    st.subheader("用户管理（管理员）")
    try:
        users = client.get("/api/users/").get("users", [])
    except ApiClientError as exc:
        _err(exc)
        return
    for u in users:
        rc = st.columns([1, 2, 2, 1, 2])
        rc[0].write(u.get("user_id"))
        rc[1].write(u.get("username"))
        rc[2].write(f"{u.get('role')} · 提交{u.get('submit_count')} · 通过{u.get('resolve_count')}")
        new_role = rc[3].selectbox("role", ["user", "admin", "banned"], index=["user", "admin", "banned"].index(u["role"]) if u["role"] in ("user", "admin", "banned") else 0,
                                   key=f"role_{u['user_id']}", label_visibility="collapsed")
        if rc[4].button("保存", key=f"save_{u['user_id']}"):
            if u["user_id"] == me.get("user_id") and new_role != "admin":
                st.warning("不能降级当前管理员账号（避免失去管理员）")
            else:
                try:
                    client.put(f"/api/users/{u['user_id']}/role", json={"role": new_role})
                    st.success(f"{u['username']} → {new_role}")
                    st.rerun()
                except ApiClientError as exc:
                    _err(exc)


# ============================== AI 命题 ==============================

def _available_languages() -> list[str]:
    try:
        return get_client().get("/api/languages/").get("name", [])
    except ApiClientError:
        return ["python", "cpp"]


def _available_problems() -> list[str]:
    try:
        return [p["id"] for p in get_client().get("/api/problems/")]
    except ApiClientError:
        return []


def render_ai_page() -> None:
    st.header("🤖 AI 智能命题")
    with st.expander("模型配置（per-user，OpenRouter 计价 / CNY）", expanded=False):
        _render_model_config()
    st.divider()

    mode = st.radio("输入方式", ["结构化表单", "纯文本"], horizontal=True)
    requirement, language, problem_id, hardcore, retry_limit = "", None, None, False, 2
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
            complexity_choice = st.selectbox("预期复杂度", COMPLEXITY_OPTIONS)
        complexity = complexity_choice
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
        ref_opts = _available_problems()
        ref = st.selectbox("站内参考题（可选）", [""] + ref_opts)
        problem_id = ref or None
        c4, c5 = st.columns(2)
        with c4:
            hardcore = st.checkbox("硬核模式（对拍校验测试数据）", value=False, key="hardcore")
        if hardcore:
            with c5:
                retry_limit = st.slider("对拍重试次数", 0, 5, 2)
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
        if hardcore:
            with c7:
                retry_limit = st.slider("对拍重试次数", 0, 5, 2, key="retry_txt")

    if st.button("🚀 生成题目", type="primary"):
        if not requirement.strip():
            st.error("命题需求不能为空")
            return
        body = {"requirement": requirement, "hardcore": hardcore, "retry_limit": retry_limit}
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


def render_task_progress(task_id: str) -> None:
    client = get_client()
    st.subheader(f"任务 {task_id}")
    if st.button("刷新状态"):
        st.rerun()
    try:
        data = client.get(f"/api/ai/problem-tasks/{task_id}")
    except ApiClientError as exc:
        st.warning(str(exc))
        return
    st.write(f"状态：**{data.get('status')}** · {data.get('progress', '')}")
    usage = data.get("usage")
    if usage:
        st.caption(f"Token：{usage.get('input_tokens',0)} in / {usage.get('output_tokens',0)} out · "
                   f"费用 {usage.get('cost',0)} {usage.get('currency','CNY')}（USD 单价 × fx_rate {usage.get('fx_rate','')}）")
    if data.get("review"):
        st.warning(f"需人工复核：{data.get('review_note','')}")
    if data.get("error"):
        st.error(data["error"])
    result = data.get("result")
    if result:
        st.success(f"命题完成：{result.get('title','')}（语言 {result.get('language','')}，"
                   f"测试点 {len(result.get('testcases',[]))} 个）")
        if st.button("✏️ 采纳到题目编辑（预填）", type="primary"):
            st.session_state["prefill_problem"] = result
            st.session_state["problem_action"] = "新建"
            st.session_state["page"] = "题目"
            st.rerun()
        with st.expander("查看产出 JSON"):
            st.json(result)
    elif data.get("review"):
        if st.button("🔄 以相同需求重试（新任务）"):
            body = {"requirement": data.get("requirement", ""), "hardcore": True,
                    "retry_limit": data.get("retry_limit", 2)}
            if data.get("language"):
                body["language"] = data["language"]
            try:
                nd = client.post("/api/ai/problem-tasks/", json=body)
                st.session_state["ai_task_id"] = nd.get("task_id")
                st.rerun()
            except ApiClientError as exc:
                _err(exc)


def _render_model_config() -> None:
    client = get_client()
    st.caption("配置仅用于你自己的命题任务（per-user）；provider_url 通常为 OpenRouter，model 需在其上有明确计价。")
    with st.form("ai_cfg_form"):
        provider = st.text_input("provider_url", "https://openrouter.ai/api/v1")
        model = st.text_input("model", "deepseek/deepseek-chat")
        key = st.text_input("api_key", type="password")
        c = st.columns(3)
        inp = c[0].number_input("input_price（USD/unit）", min_value=0.0, value=0.0, format="%.4f")
        out = c[1].number_input("output_price（USD/unit）", min_value=0.0, value=0.0, format="%.4f")
        unit = c[2].number_input("price_unit", min_value=1, value=1_000_000, step=100000)
        fx = st.number_input("fx_rate（USD→CNY，请按当日更新）", min_value=0.1, value=7.2, format="%.4f",
                             help="默认 7.2 为 2026-09 参考值；以中国人民银行中间价为准，当日可更新。")
        if st.form_submit_button("保存配置"):
            if not (provider and model and key):
                st.error("provider_url / model / api_key 必填（无 key 时走本地 mock）")
            else:
                try:
                    data = client.put("/api/ai/model-config", json={
                        "provider_url": provider, "model": model, "api_key": key,
                        "input_price": inp, "output_price": out, "price_unit": int(unit), "fx_rate": fx,
                    })
                    st.success(f"已保存：{data.get('model')}（{data.get('currency')}）")
                except ApiClientError as exc:
                    _err(exc)
    st.caption("计价：模型单价取自 OpenRouter（USD/1M tokens）；费用 = token/单位×单价(USD)×fx_rate，CNY 展示。")


def main() -> None:
    st.set_page_config(page_title="OJ 前端", layout="wide")
    render_login_sidebar()
    if "user" not in st.session_state:
        st.info("请先在左侧登录（无账号可注册）。")
        return
    page = st.sidebar.radio("功能", PAGES, index=PAGES.index(st.session_state.get("page", "AI 命题")))
    st.session_state["page"] = page
    if page == "AI 命题":
        render_ai_page()
    elif page == "题目":
        render_problems_page()
    elif page == "评测":
        render_submissions_page()
    else:
        render_users_page()


if __name__ == "__main__":
    main()
