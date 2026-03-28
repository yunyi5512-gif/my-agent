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
    url = "https://api.tavily.com/search"
    data = {"api_key": TAVILY_KEY, "query": query, "search_depth": "basic", "max_results": 3}
    try:
        response = requests.post(url, json=data, timeout=10)
        results = response.json().get("results", [])
        return "\n".join([f"来源: {r['url']}\n摘要: {r['content']}" for r in results])
    except:
        return "联网搜索暂时不可用。"

# --- 3. 记忆存取逻辑 ---
def load_history():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return [{"role": "system", "content": "你是一个既能联网又能分析文件的全能助手。"}]

if "messages" not in st.session_state:
    st.session_state.messages = load_history()

# --- 4. 侧边栏：【功能合集】 ---
with st.sidebar:
    st.title("⚡ 增强中心")
    
    # 联网开关
    is_web_enabled = st.toggle("🌍 开启联网搜索", value=True)
    
    st.divider()
    
    # --- 找回失去的文件上传功能 ---
    st.header("📁 文件中心")
    uploaded_file = st.file_uploader("上传一个文本文件 (.txt, .py, .md)", type=['txt', 'py', 'md'])
    if uploaded_file and st.button("喂给 AI 学习"):
        content = uploaded_file.read().decode("utf-8")
        # 把文件内容作为一条特殊的背景信息存入记忆
        st.session_state.messages.append({"role": "user", "content": f"【上传文件背景】：\n{content}"})
        st.success("文件内容已加载到脑子里了！")

    st.divider()
    if st.button("🗑️ 清空记忆"):
        st.session_state.messages = []
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.rerun()

# --- 5. 对话展示 ---
for m in st.session_state.messages:
    if m["role"] != "system" and not m["content"].startswith("【上传文件背景】："):
        with st.chat_message(m["role"]): st.markdown(m["content"])

# --- 6. 核心对话逻辑 ---
if prompt := st.chat_input("问问最新的，或者聊聊文件内容？"):
    with st.chat_message("user"): st.markdown(prompt)
    
    final_prompt = prompt
    # 如果开启联网，先去抓数据
    if is_web_enabled:
        with st.status("🔍 正在全网搜寻...", expanded=False):
            web_results = get_web_info(prompt)
            final_prompt = f"【参考搜索资料】:\n{web_results}\n\n【用户问题】: {prompt}"
    
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
        # 注意：发送给 AI 时，要包含之前的记忆（包括文件背景）
        payload = {
            "model": "deepseek-chat",
            "messages": st.session_state.messages[:-1] + [{"role": "user", "content": final_prompt}],
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
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)
