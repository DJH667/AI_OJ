"""OJ 前端（Streamlit）。前后端分离：仅经 REST API + Cookie 会话与 FastAPI 后端交互。

启动（backend 先起在 8000）：
    ../.venv/Scripts/python.exe -m streamlit run app.py --server.port 8501   # Windows
    wsl ~/oj-venv/... （WSL venv 装 streamlit 后可同机跑）

本页当前范围（D6a 起）：登录/注册 + AI 命题表单（语言必选下拉=已注册语言、硬核模式开关与重试调节、
任务创建与轮询）。题目/评测/用户管理页面组（Step6）随后续轮次接入。
"""
import time

import streamlit as st

from api_client import ApiClientError, get_client

# 预设考点（参考洛谷常见标签，用户可自定义）
TAG_OPTIONS = [
    "模拟", "枚举", "贪心", "二分", "双指针", "排序", "数学", "数论", "动态规划",
    "搜索/DFS", "BFS", "图论", "最短路", "最小生成树", "字符串", "前缀和", "差分", "位运算",
    "高精度", "分治", "递归", "哈希", "并查集", "数据结构", "栈/队列", "堆", "树", "其他",
]
COMPLEXITY_OPTIONS = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "其他"]
SCALE_OPTIONS = ["小（n<=10^3）", "中（n<=10^5）", "大（n<=10^7）", "其他"]


def _err(exc: ApiClientError) -> None:
    st.error(f"⚠️ {exc}")


def render_login_sidebar() -> None:
    st.sidebar.title("OJ 系统")
    client = get_client()
    if "user" in st.session_state:
        u = st.session_state["user"]
        st.sidebar.write(f"👤 {u.get('username')}（{u.get('role')}）")
        if st.sidebar.button("退出登录"):
            client.logout()
            for key in ("user", "api_client", "ai_task_id"):
                st.session_state.pop(key, None)
            st.rerun()
        return
    st.sidebar.subheader("登录")
    with st.sidebar.form("login_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录")
        if submitted:
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


def _available_languages() -> list[str]:
    try:
        data = get_client().get("/api/languages/")
        return data.get("name", [])
    except ApiClientError as exc:
        st.warning(f"获取语言失败：{exc}")
        return ["python", "cpp"]


def _available_problems() -> list[str]:
    try:
        data = get_client().get("/api/problems/")
        return [p["id"] for p in data]
    except ApiClientError:
        return []


def render_ai_page() -> None:
    st.header("🤖 AI 智能命题")
    with st.expander("模型配置（管理员，OpenRouter 计价）", expanded=False):
        _render_model_config()
    st.divider()

    mode = st.radio("输入方式", ["结构化表单", "纯文本"], horizontal=True)
    requirement = ""
    language = "python"
    hardcore = False
    retry_limit = 2
    problem_id = None

    if mode == "结构化表单":
        languages = _available_languages()
        if not languages:
            return
        c1, c2, c3 = st.columns(3)
        with c1:
            language = st.selectbox("语言（必选）", languages, index=languages.index("python") if "python" in languages else 0)
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
            if extra and extra not in tags:
                tags = [t for t in tags if t != "其他"] + [extra]
            else:
                tags = [t for t in tags if t != "其他"]
        scale_choice = st.selectbox("数据规模", SCALE_OPTIONS)
        scale = scale_choice
        if scale_choice == "其他":
            scale = st.text_input("自定义规模", key="scale_other")
        background = st.text_area("情景/背景故事（可选）", key="ai_bg")
        note = st.text_area("备注（可选）", key="ai_note")
        st.markdown("**语言必选；考点/复杂度/规模均可自定义；可引用站内题目链接或在下框选参考题**")

        ref_opts = _available_problems()
        ref = st.selectbox("站内参考题（可选，作风格/难度参考）", [""] + ref_opts)
        problem_id = ref or None

        c4, c5 = st.columns(2)
        with c4:
            hardcore = st.checkbox("硬核模式（对拍校验测试数据）", value=False, key="hardcore")
        if hardcore:
            with c5:
                retry_limit = st.slider("对拍重试次数", 0, 5, 2, help="对拍失败后最多额外重试次数")
        parts = [f"题目要求：{background or '设计一道算法题'}", f"难度分：{difficulty}/10"]
        if tags:
            parts.append(f"考点：{'、'.join(tags)}")
        if complexity:
            parts.append(f"预期复杂度：{complexity}")
        if scale:
            parts.append(f"数据规模：{scale}")
        if note:
            parts.append(f"备注：{note}")
        requirement = "\n".join(parts)
    else:
        language = None  # 纯文本：语言由模型抽取/兜底
        requirement = st.text_area("用自然语言描述命题需求（可附站内题目链接）", key="pure_req", height=160)
        uploaded = st.file_uploader("上传背景资料（文本类；纯文本模型无法观看图片）", type=["txt", "md", "csv", "json"])
        if uploaded is not None:
            try:
                text = uploaded.getvalue().decode("utf-8", errors="replace")
                requirement = f"{requirement}\n\n【上传资料】\n{text[:6000]}"
            except Exception as exc:  # noqa: BLE001
                st.warning(f"读取上传文件失败：{exc}")
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
    st.subheader(f"任务 {task_id}")
    if st.button("刷新状态"):
        st.rerun()
    try:
        data = get_client().get(f"/api/ai/problem-tasks/{task_id}")
    except ApiClientError as exc:
        st.warning(str(exc))
        return
    st.write(f"状态：**{data.get('status')}** · {data.get('progress', '')}")
    if data.get("review"):
        st.warning(f"需人工复核：{data.get('review_note', '')}")
    if data.get("error"):
        st.error(data["error"])
    usage = data.get("usage")
    if usage:
        st.caption(f"Token：{usage.get('input_tokens',0)} in / {usage.get('output_tokens',0)} out · "
                   f"费用 {usage.get('cost', 0)} {usage.get('currency','USD')}（按模型配置单价计）")
    result = data.get("result")
    if result:
        st.success(f"命题完成：{result.get('title', '')}")
        st.caption(f"测试点 {len(result.get('testcases', []))} 个 · samples {len(result.get('samples', []))} 个 · "
                   f"语言 {result.get('language', '')}")
        st.info("下一步：采纳到“题目新增/编辑”表单（Step6 题目页接入后支持预填；result 已含全量 testcases）")


def _render_model_config() -> None:
    client = get_client()
    if st.session_state.get("user", {}).get("role") != "admin":
        st.caption("仅管理员可配置（全局共享 + 密钥）。")
        return
    with st.form("ai_cfg_form"):
        provider = st.text_input("provider_url", "https://openrouter.ai/api/v1")
        model = st.text_input("model", "deepseek/deepseek-chat")
        key = st.text_input("api_key", type="password")
        c = st.columns(3)
        inp = c[0].number_input("input_price(每1M token)", min_value=0.0, value=0.0, format="%.4f")
        out = c[1].number_input("output_price(每1M token)", min_value=0.0, value=0.0, format="%.4f")
        unit = c[2].number_input("price_unit", min_value=1, value=1_000_000, step=100000)
        if st.form_submit_button("保存配置"):
            if not (provider and model and key):
                st.error("provider_url / model / api_key 必填（无 key 时走本地 mock）")
            else:
                try:
                    data = client.put("/api/ai/model-config", json={
                        "provider_url": provider, "model": model, "api_key": key,
                        "input_price": inp, "output_price": out, "price_unit": int(unit),
                    })
                    st.success(f"已保存：{data.get('model')}（api_key 已配置）")
                except ApiClientError as exc:
                    _err(exc)


def render_placeholder(name: str) -> None:
    st.header(name)
    st.info("该页面组随 Step6 前端（用户/题目/评测）在后续轮次接入。")


def main() -> None:
    st.set_page_config(page_title="OJ 前端", layout="wide")
    render_login_sidebar()
    if "user" not in st.session_state:
        st.info("请先在左侧登录（无账号可注册）。")
        return
    page = st.sidebar.radio("功能", ["AI 命题", "题目", "评测", "用户"])
    if page == "AI 命题":
        render_ai_page()
    elif page == "题目":
        render_placeholder("📚 题目管理")
    elif page == "评测":
        render_placeholder("🧪 评测与提交")
    else:
        render_placeholder("👥 用户管理")


if __name__ == "__main__":
    main()
