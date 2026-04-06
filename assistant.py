import requests
import streamlit as st
import json
import os

# ===== 1. 页面配置（必须放最前面）=====
st.set_page_config(
    page_title="DeepSeek Pro Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== 2. 自定义高级 CSS =====
st.markdown("""
<style>
    /* 1. 侧边栏全局文字加亮 */
    [data-testid="stSidebar"] .stMarkdown, 
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p {
        color: #f1f5f9 !important; /* 换成非常亮的灰白色 */
        font-weight: 500; /* 加粗一点点，更清晰 */
    }

    /* 2. 侧边栏标题特殊颜色（青紫色，呼应主题） */
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3 {
        color: #a5b4fc !important; /* 亮紫色标题 */
        text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
    }

    /* 3. 侧边栏 Selectbox 和上传组件的文字 */
    [data-testid="stSidebar"] .stSelectbox div div,
    [data-testid="stSidebar"] .stFileUploader section div {
        color: #ffffff !important;
    }

    /* 4. 这里的 Expander 头部也要亮一点 */
    [data-testid="stSidebar"] .st-ae summary {
        color: #f8fafc !important;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ===== 3. 配置与调度指令 =====
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY") # 建议统一用这个名
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
BASE_URL = "https://api.deepseek.com/chat/completions"
DB_FILE = "chat_history.json"

TOOLS_DESC = """
你是一个高效的调度员。请根据用户输入选择标签：
- [SEARCH]: 涉及实时新闻、具体事实查证。
- [CALC]: 涉及数学计算、代码逻辑。直接给出结果，不要冗长推导。
- [FILE]: 涉及对上传文件内容的提问。
- [CHAT]: 日常打招呼、闲聊。
只回复标签，严禁多言。
"""

# 安全检查
if not DEEPSEEK_KEY or not TAVILY_KEY:
    st.error("⚠️ API Keys 缺失，请检查 Secrets 配置。")
    st.stop()

# ===== 4. 核心功能函数 =====

def dispatch_center(user_query):
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": TOOLS_DESC},
            {"role": "user", "content": f"用户输入：{user_query}\n请选择标签："}
        ],
        "max_tokens": 10
    }
    try:
        r = requests.post(BASE_URL, headers=headers, json=payload, timeout=5)
        return r.json()["choices"][0]["message"]["content"].strip().upper()
    except: return "[CHAT]"

def get_web_info(query):
    url = "https://api.tavily.com/search"
    data = {"api_key": TAVILY_KEY, "query": query, "search_depth": "basic", "max_results": 3}
    try:
        response = requests.post(url, json=data, timeout=10)
        results = response.json().get("results", [])
        return "\n".join([f"来源: {r['url']}\n摘要: {r['content']}" for r in results])
    except: return "联网搜索暂时不可用。"

def load_history():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
            return [history[0]] + history[-10:] if len(history) > 11 else history
    return [{"role": "system", "content": "你是一个既能联网又能分析文件的全能助手。"}]

# ===== 5. 界面布局与逻辑 =====

# 初始化
if "messages" not in st.session_state:
    st.session_state.messages = load_history()
if "last_tool" not in st.session_state:
    st.session_state.last_tool = "等待指令"

# 顶部横幅
st.markdown('<div class="main-header"><h1>🤖 DeepSeek Pro Agent</h1><p>智能调度 · 联网搜索 · 文件分析 · 精准计算</p ></div>', unsafe_allow_html=True)

# 侧边栏
with st.sidebar:
    st.markdown("### ⚡ 控制中心")
    col_a, col_b = st.columns(2)
    with col_a: is_web = st.toggle("🌍 联网", value=True)
    with col_b: auto_save = st.toggle("💾 存档", value=True)
    
    st.divider()
    with st.expander("📁 文件管理", expanded=True):
        uploaded_file = st.file_uploader("上传文档", type=['txt', 'py', 'md'])
        if uploaded_file: st.success(f"✅ {uploaded_file.name}")

    if st.button("🗑️ 清空记忆"):
        st.session_state.messages = [st.session_state.messages[0]]
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.rerun()

# 主布局分列
col1, col2 = st.columns([3, 1])

with col1:
    # 展示历史对话
    for m in st.session_state.messages:
        if m["role"] != "system" and not m["content"].startswith("【文件背景】："):
            with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("指令下达..."):
        with st.chat_message("user"): st.markdown(prompt)
        
        final_prompt = prompt
        # 调度决策
        with st.spinner("🤖 Agent 正在决策路径..."):
            tool_choice = dispatch_center(prompt)
            st.session_state.last_tool = tool_choice
        
        with st.expander("👁️ 查看 Agent 决策过程", expanded=False):
            st.write(f"**识别工具**: `{tool_choice}`")
            if "[SEARCH]" in tool_choice: st.info("路径：实时数据需求 -> 激活搜索引擎")
            elif "[CALC]" in tool_choice: st.info("路径：数理逻辑 -> 激活精准计算模式")
            else: st.info("路径：常规语义理解")

        # 工具执行
        if "[SEARCH]" in tool_choice and is_web:
            with st.status("🌐 联网搜索中...", expanded=False):
                res = get_web_info(prompt)
                final_prompt = f"【联网插件返回】：\n{res}\n\n问题：{prompt}"
        elif "[FILE]" in tool_choice:
            with st.status("📁 检索本地文件...", expanded=False):
                st.write("已关联文件上下文")

        st.session_state.messages.append({"role": "user", "content": prompt})

        # AI 回答
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_res = ""
            headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "deepseek-chat",
                "messages": st.session_state.messages[:-1] + [{"role": "user", "content": final_prompt}],
                "stream": True
            }
            try:
                response = requests.post(BASE_URL, headers=headers, json=payload, stream=True)
                for line in response.iter_lines():
                    if line:
                        decoded = line.decode("utf-8").replace("data: ", "")
                        if decoded == "[DONE]": break
                        try:
                            content = json.loads(decoded)["choices"][0]["delta"].get("content", "")
                            full_res += content
                            placeholder.markdown(full_res + "▌")
                        except: continue
                placeholder.markdown(full_res)
                st.session_state.messages.append({"role": "assistant", "content": full_res})
                if auto_save:
                    with open(DB_FILE, "w", encoding="utf-8") as f:
                        json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)
            except Exception as e:
                st.error(f"连接失败: {e}")

with col2:
    st.markdown("### 📊 实时状态")
    st.metric("对话轮次", len(st.session_state.messages))
    st.metric("上次激活", st.session_state.last_tool)
    st.info("Agent 运行正常")
