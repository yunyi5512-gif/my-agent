import streamlit as st
import requests
import json
import os

# --- 1. 配置区 ---
DEEPSEEK_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
BASE_URL = "https://api.deepseek.com/chat/completions"
DB_FILE = "chat_history.json"

# --- 2. 联网搜索工具 ---
def get_web_info(query):
    """通过 Tavily 搜索网页"""
    url = "https://api.tavily.com/search"
    data = {
        "api_key": TAVILY_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": 3
    }
    try:
        response = requests.post(url, json=data, timeout=10)
        results = response.json().get("results", [])
        # 提取网页内容
        context = "\n".join([f"来源: {r['url']}\n摘要: {r['content']}" for r in results])
        return context
    except Exception as e:
        return f"联网失败: {e}"

# --- 3. 基础逻辑（加载记忆等保持不变） ---
def load_history():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return [{"role": "system", "content": "你是一个拥有联网能力的专家。当资料里有最新背景时，请结合回答。"}]

if "messages" not in st.session_state:
    st.session_state.messages = load_history()

# --- 4. 侧边栏 ---
with st.sidebar:
    st.title("⚡ 增强中心")
    is_web_enabled = st.toggle("开启联网搜索", value=True)
    if st.button("清空记忆"):
        st.session_state.messages = []
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.rerun()

# --- 5. 聊天主逻辑 ---
for m in st.session_state.messages:
    if m["role"] != "system":
        with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("问点最新的？"):
    with st.chat_message("user"): st.markdown(prompt)
    
    # 构建发给 AI 的最终提示词
    final_context = ""
    if is_web_enabled:
        with st.status("🌐 正在全网搜寻相关信息...", expanded=False):
            web_results = get_web_info(prompt)
            final_context = f"【最新网页资料】:\n{web_results}\n\n请结合以上资料回答用户：{prompt}"
            st.write("🔍 搜索完成，正在深度分析...")
    else:
        final_context = prompt

    st.session_state.messages.append({"role": "user", "content": prompt})

    # 发送给 DeepSeek
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "deepseek-chat",
            "messages": st.session_state.messages[:-1] + [{"role": "user", "content": final_context}],
            "stream": True
        }
        r = requests.post(BASE_URL, headers=headers, json=payload, stream=True)
        for line in r.iter_lines():
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
