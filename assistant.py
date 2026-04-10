import streamlit as st
import requests
import base64
import json
import os

# ===== 1. 页面配置与视觉补丁 =====
st.set_page_config(page_title="AI Multi-Core Study", layout="wide")

st.markdown("""
<style>
    :root { --bg-dark: #0f172a; }

    /* Light 模式：聊天文字黑色 */
    .stChatMessage p {
        color: #111827 !important;
    }

    /* Dark 模式：聊天文字白色 */
    @media (prefers-color-scheme: dark) {
        .stChatMessage p {
            color: #ffffff !important;
        }
    }

    div[data-baseweb="select"] * {
        color: #1e293b !important;
        -webkit-text-fill-color: #1e293b !important;
    }

    div[role="listbox"] * {
        color: #1e293b !important;
    }

    code {
        background-color: #0f172a !important;
        color: #e2e8f0 !important;
        border-radius: 4px;
    }

    pre {
        background-color: #0f172a !important;
        border: 1px solid #334155;
        border-radius: 10px;
    }

    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1rem;
    }
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

# ===== 3. 工具函数 =====
def get_web_info(query):
    """Tavily 联网搜索"""
    if not TAVILY_KEY:
        return "搜索插件未配置 TAVILY_API_KEY。"

    url = "https://api.tavily.com/search"
    data = {
        "api_key": TAVILY_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": 3
    }
    try:
        response = requests.post(url, json=data, timeout=15)
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            return "未检索到有效结果。"
        return "\n\n".join(
            [f"来源: {r.get('url', '未知')}\n摘要: {r.get('content', '无摘要')}" for r in results]
        )
    except Exception as e:
        return f"搜索插件暂时离线：{e}"

def encode_image(image_file):
    image_file.seek(0)
    return base64.b64encode(image_file.read()).decode("utf-8")

def dispatch_center(user_query, api_key, url, model):
    """调度决策中心"""
    if not api_key:
        return "[CHAT]"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是一个调度员。只需回复标签：[SEARCH]（需联网查事实）或 [CHAT]（日常交流）。"
            },
            {
                "role": "user",
                "content": user_query
            }
        ],
        "max_tokens": 10,
        "stream": False
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip().upper()
    except Exception:
        return "[CHAT]"

def build_messages(history, final_prompt, uploaded_img, current_cfg):
    """构造发送给模型的 messages"""
    messages = []

    # 历史对话
    for m in history:
        messages.append({
            "role": m["role"],
            "content": m["content"]
        })

    # 当前输入
    if uploaded_img and current_cfg["vision"]:
        base_64_img = encode_image(uploaded_img)
        user_content = [
            {"type": "text", "text": final_prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_img}"}}
        ]
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append({"role": "user", "content": final_prompt})

    return messages

def stream_chat(url, api_key, payload):
    """统一流式输出"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    with requests.post(url, headers=headers, json=payload, stream=True, timeout=120) as r:
        r.raise_for_status()
        for raw_line in r.iter_lines():
            if not raw_line:
                continue

            line = raw_line.decode("utf-8").strip()

            if line.startswith("data: "):
                line = line[6:]

            if line == "[DONE]":
                break

            try:
                data = json.loads(line)
                delta = data["choices"][0].get("delta", {})
                content = delta.get("content", "")

                if isinstance(content, str) and content:
                    yield content

            except Exception:
                continue

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
        uploaded_img = st.file_uploader("拍张照/传图", type=["png", "jpg", "jpeg"])

st.markdown(
    '<div class="main-header"><h1>🤖 AI Study Ultimate</h1><p>联网 · 识图 · 双核引擎全开启</p></div>',
    unsafe_allow_html=True
)

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ===== 5. 主逻辑 =====
if prompt := st.chat_input("下达指令..."):
    if not current_cfg["key"]:
        st.error(f"{selected_engine} 未配置 API Key。")
        st.stop()

    with st.chat_message("user"):
        st.markdown(prompt)

    final_prompt = prompt

    # 1. 决策：是否需要联网
    if is_web:
        with st.spinner("🤖 决策中..."):
            tool_choice = dispatch_center(
                prompt,
                current_cfg["key"],
                current_cfg["url"],
                current_cfg["model"]
            )

        if "[SEARCH]" in tool_choice:
            with st.status("🌐 正在检索实时信息...", expanded=False):
                search_res = get_web_info(prompt)
                final_prompt = f"【实时联网信息】\n{search_res}\n\n请结合以上信息回答用户问题：{prompt}"

    # 显示到历史里的是用户原始输入
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. 构造消息
    messages = build_messages(
        history=st.session_state.messages[:-1],
        final_prompt=final_prompt,
        uploaded_img=uploaded_img,
        current_cfg=current_cfg
    )

    # 3. AI 响应
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""

        payload = {
            "model": current_cfg["model"],
            "messages": messages,
            "stream": True
        }

        try:
            for chunk in stream_chat(current_cfg["url"], current_cfg["key"], payload):
                full_res += chunk
                placeholder.markdown(full_res + "▌")

            if not full_res:
                full_res = "模型未返回内容。"

            placeholder.markdown(full_res)
            st.session_state.messages.append({"role": "assistant", "content": full_res})

        except Exception as e:
            st.error(f"响应失败: {e}")
