import requests
import streamlit as st
import json
import os

# ===== 1. 页面配置（必须放最前面）=====
st.set_page_config(
    page_title="assistant Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== 2. 自定义高级 CSS（保持你的全亮白字体样式） =====
st.markdown("""
<style>
    :root { --primary-color: #6366f1; --bg-dark: #0f172a; --card-bg: #1e293b; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem; border-radius: 15px; margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
    }
    .main-header h1 { color: white; font-size: 2.5rem; font-weight: 700; margin: 0; }
    .main-header p { color: #e0e7ff; font-size: 1.1rem; margin: 0.5rem 0 0 0; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%); }
    .stChatMessage { background: var(--card-bg); border-radius: 12px; padding: 1rem; margin: 0.5rem 0; border-left: 4px solid var(--primary-color); }
    .stButton>button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 8px; width: 100%; }

    /* 全局字体亮化 */
    .stChatMessage, .stChatMessage p, .stChatMessage span, .stChatMessage div { color: #ffffff !important; line-height: 1.6; }
    .st-ae summary, .st-ae p, .st-ae div { color: #ffffff !important; }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] h3 { color: #ffffff !important; }
    [data-testid="stFileUploader"] section div div, [data-testid="stFileUploader"] small { color: #ffffff !important; }
    .stTextInput input { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

# ===== 3. 配置区（双引擎映射） =====
# 请在 Streamlit Secrets 中配置这三个 Key
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY") # 或你习惯的名字
CODEX_KEY = os.getenv("CODEX_API_KEY")    # Duckcoding 中转站 Key
TAVILY_KEY = os.getenv("TAVILY_API_KEY")

# 双引擎映射表
ENGINE_CONFIG = {
    "DeepSeek-V3": {
        "url": "https://api.deepseek.com/chat/completions",
        "key": DEEPSEEK_KEY,
        "model": "deepseek-chat"
    },
    "Codex-Plus": {
        "url": "https://api.codxcoding.com/v1/chat/completions",
        "key": CODEX_KEY,
        "model": "gpt-5" # 请根据中转站后台实际支持的模型名修改
    }
}

DB_FILE = "chat_history.json"

TOOLS_DESC = """
你是一个高效的调度员。请根据用户输入选择标签：
- [SEARCH]: 涉及实时新闻、事实查证。
- [CALC]: 涉及数学计算。直接给出结果，禁止推导过程！
- [FILE]: 涉及对上传文件内容的提问。
- [CHAT]: 日常闲聊。
只回复标签，严禁多言。
"""

# 安全检查
if not TAVILY_KEY:
    st.error("⚠️ TAVILY_API_KEY 缺失，请检查配置。")
    st.stop()

# ===== 4. 核心功能函数 =====

def dispatch_center(user_query, api_key, url, model):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": TOOLS_DESC},
            {"role": "user", "content": f"请选择标签：{user_query}"}
        ],
        "max_tokens": 10
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=5)
        return r.json()["choices"][0]["message"]["content"].strip().upper()
    except: return "[CHAT]"

def get_web_info(query):
    url = "https://api.tavily.com/search"
    data = {"api_key": TAVILY_KEY, "query": query, "search_depth": "basic", "max_results": 3}
    try:
        response = requests.post(url, json=data, timeout=10)
        results = response.json().get("results", [])
        return "\n".join([f"来源: {r['url']}\n摘要: {r['content']}" for r in results])
    except: return "联网搜索暂不可用。"

# ===== 5. 界面布局与逻辑 =====

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": "全能助手已就绪。"}]
if "last_tool" not in st.session_state:
    st.session_state.last_tool = "等待指令"

st.markdown('<div class="main-header"><h1>🤖 Pro Agent Multi-Core</h1><p>双引擎驱动 · 智能调度 · 高级视觉版</p ></div>', unsafe_allow_html=True)

# 侧边栏
with st.sidebar:
    st.markdown("### 🤖 引擎切换")
    selected_engine = st.selectbox("当前核心", list(ENGINE_CONFIG.keys()))
    
    # 动态获取当前引擎参数
    current_cfg = ENGINE_CONFIG[selected_engine]
    
    st.divider()
    st.markdown("### ⚡ 控制中心")
    col_a, col_b = st.columns(2)
    with col_a: is_web = st.toggle("🌍 联网", value=True)
    with col_b: auto_save = st.toggle("💾 存档", value=True)
    
    with st.expander("📁 文件管理", expanded=True):
        uploaded_file = st.file_uploader("上传文档", type=['txt', 'py', 'md'])

    if st.button("🗑️ 清空记忆"):
        st.session_state.messages = [st.session_state.messages[0]]
        st.rerun()

col1, col2 = st.columns([3, 1])

with col1:
    for m in st.session_state.messages:
        if m["role"] != "system":
            with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("指令下达..."):
        with st.chat_message("user"): st.markdown(prompt)
        
        # 1. 决策
        with st.spinner(f"正在通过 {selected_engine} 决策..."):
            tool_choice = dispatch_center(prompt, current_cfg['key'], current_cfg['url'], current_cfg['model'])
            st.session_state.last_tool = tool_choice
        
        # 2. 准备 Prompt
        final_prompt = prompt
        if "[SEARCH]" in tool_choice and is_web:
            with st.status("🌐 联网搜索中...", expanded=False):
                res = get_web_info(prompt)
                final_prompt = f"【联网信息】：\n{res}\n\n请结合以上信息回答：{prompt}"
        elif "[CALC]" in tool_choice:
            final_prompt = f"你是精密计算器。请计算并直接给出数字结果，严禁推导：{prompt}"

        st.session_state.messages.append({"role": "user", "content": prompt})

        # 3. 回答
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_res = ""
            headers = {"Authorization": f"Bearer {current_cfg['key']}", "Content-Type": "application/json"}
            payload = {
                "model": current_cfg['model'],
                "messages": st.session_state.messages[:-1] + [{"role": "user", "content": final_prompt}],
                "stream": True
            }
            try:
                response = requests.post(current_cfg['url'], headers=headers, json=payload, stream=True)
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
            except Exception as e:
                st.error(f"引擎响应失败: {e}")

with col2:
    st.markdown("### 📊 状态监控")
    st.metric("核心引擎", selected_engine)
    st.metric("上次动作", st.session_state.last_tool)
    st.success(f"{selected_engine} 运行中")
