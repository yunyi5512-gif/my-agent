import streamlit as st
import requests
import base64
import json
import os

# ===== 1. 页面配置与视觉补丁（保持你最爱的亮白样式） =====
st.set_page_config(page_title="AI Multi-Core Study", layout="wide")

st.markdown("""
<style>
    :root { --bg-dark: #0f172a; }
    .stChatMessage p { color: #ffffff !important; }
    /* 下拉框黑化补丁 */
    div[data-baseweb="select"] * { color: #1e293b !important; -webkit-text-fill-color: #1e293b !important; }
    div[role="listbox"] * { color: #1e293b !important; }
    /* 代码框深色补丁 */
    code { background-color: #0f172a !important; color: #e2e8f0 !important; border-radius: 4px; }
    pre { background-color: #0f172a !important; border: 1px solid #334155; border-radius: 10px; }
    .main-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 12px; color: white; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

# ===== 2. 配置映射 =====
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
CODEX_KEY = os.getenv("CODEX_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")

ENGINE_CONFIG = {
    "DeepSeek-V3": {
        "url": "https://api.deepseek.com/chat/completions",
        "key": DEEPSEEK_KEY,
        "model": "deepseek-chat",
        "vision": False
    },
    "Codex-Plus": {
        "url": "https://api.duckcoding.ai/v1/chat/completions",
        "key": CODEX_KEY,
        "model": "gpt-5.4", 
        "vision": True
    }
}

# ===== 3. 工具函数（搜索 + 识图） =====
def get_web_info(query):
    """Tavily 联网搜索"""
    url = "https://api.tavily.com/search"
    data = {"api_key": TAVILY_KEY, "query": query, "search_depth": "basic", "max_results": 3}
    try:
        response = requests.post(url, json=data, timeout=10)
        results = response.json().get("results", [])
        return "\n".join([f"来源: {r['url']}\n摘要: {r['content']}" for r in results])
    except: return "搜索插件暂时离线。"

def encode_image(image_file):
    return base64.b64encode(image_file.read()).decode('utf-8')

def dispatch_center(user_query, api_key, url, model):
    """调度决策中心"""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个调度员。只需回复标签：[SEARCH]（需联网查事实）或 [CHAT]（日常交流）。"},
            {"role": "user", "content": user_query}
        ], "max_tokens": 10
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=5)
        return r.json()["choices"][0]["message"]["content"].strip().upper()
    except: return "[CHAT]"

# ===== 4. 界面交互 =====
with st.sidebar:
    st.markdown("### 🤖 引擎切换")
    selected_engine = st.selectbox("当前核心", list(ENGINE_CONFIG.keys()))
    current_cfg = ENGINE_CONFIG[selected_engine]
    
    st.divider()
    st.markdown("### ⚡ 功能开关")
    is_web = st.toggle("🌍 联网搜索", value=True)
    
    uploaded_img = None
    if current_cfg["vision"]:
        st.markdown("### 📸 视觉学习")
        uploaded_img = st.file_uploader("拍张照/传图", type=['png', 'jpg', 'jpeg'])

st.markdown('<div class="main-header"><h1>🤖 AI Study Ultimate</h1><p>联网 · 识图 · 双核引擎全开启</p ></div>', unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

# ===== 5. 主逻辑 =====
if prompt := st.chat_input("下达指令..."):
    with st.chat_message("user"): st.markdown(prompt)
    
    final_prompt = prompt
    # 1. 决策：是否需要联网
    if is_web:
        with st.spinner("🤖 决策中..."):
            tool_choice = dispatch_center(prompt, current_cfg['key'], current_cfg['url'], current_cfg['model'])
        
        if "[SEARCH]" in tool_choice:
            with st.status("🌐 正在检索实时信息...", expanded=False):
                search_res = get_web_info(prompt)
                final_prompt = f"【实时联网信息】：\n{search_res}\n\n请结合信息回答：{prompt}"

    # 2. 构造多模态内容
    content_list = [{"type": "text", "text": final_prompt}]
    if uploaded_img and current_cfg["vision"]:
        base_4_img = encode_image(uploaded_img)
        content_list.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_4_img}"}})

    st.session_state.messages.append({"role": "user", "content": prompt})

    # 3. AI 响应
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        headers = {"Authorization": f"Bearer {current_cfg['key']}", "Content-Type": "application/json"}
        payload = {
            "model": current_cfg['model'],
            "messages": [{"role": "user", "content": content_list}],
            "stream": True
        }
        try:
            r = requests.post(current_cfg['url'], headers=headers, json=payload, stream=True)
            for line in r.iter_lines():
                if line:
                    decoded = line.decode("utf-8").replace("data: ", "")
                    if decoded == "[DONE]": break
                    try:
                        delta = json.loads(decoded)["choices"][0]["delta"].get("content", "")
                        full_res += delta
                        placeholder.markdown(full_res + "▌")
                    except: continue
            placeholder.markdown(full_res)
            st.session_state.messages.append({"role": "assistant", "content": full_res})
        except Exception as e:
            st.error(f"响应失败: {e}")
