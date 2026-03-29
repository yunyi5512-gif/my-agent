import streamlit as st
import requests
import json
import os

# --- 1. 配置区 ---
DEEPSEEK_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
BASE_URL = "https://api.deepseek.com/chat/completions"
DB_FILE = "chat_history.json"

# --- 2. 工具函数 (必须放在主逻辑前面) ---

def check_intent(user_query):
    """意图识别：判断是否需要联网"""
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个意图分类器。如果用户的问题涉及实时新闻、天气、最近发生的事件、或需要搜索才能回答的信息，请只回复'YES'，否则只回复'NO'。"},
            {"role": "user", "content": user_query}
        ],
        "max_tokens": 5
    }
    try:
        r = requests.post(BASE_URL, headers=headers, json=payload, timeout=5)
        return "YES" in r.json()["choices"][0]["message"]["content"].strip().upper()
    except:
        return False

def get_web_info(query):
    """联网搜索"""
    url = "https://api.tavily.com/search"
    data = {"api_key": TAVILY_KEY, "query": query, "search_depth": "basic", "max_results": 3}
    try:
        response = requests.post(url, json=data, timeout=10)
        results = response.json().get("results", [])
        return "\n".join([f"来源: {r['url']}\n摘要: {r['content']}" for r in results])
    except:
        return "联网搜索暂时不可用。"

def load_history():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return [{"role": "system", "content": "你是一个既能联网又能分析文件的全能助手。"}]

# --- 3. 页面初始化 ---
if "messages" not in st.session_state:
    st.session_state.messages = load_history()

# --- 4. 侧边栏 ---
with st.sidebar:
    st.title("⚡ 增强中心")
    is_web_enabled = st.toggle("🌍 开启自动意图联网", value=True)
    
    st.divider()
    st.header("📁 文件中心")
    uploaded_file = st.file_uploader("上传文本文件", type=['txt', 'py', 'md'])
    if uploaded_file and st.button("喂给 AI 学习"):
        content = uploaded_file.read().decode("utf-8")
        st.session_state.messages.append({"role": "user", "content": f"【文件背景】：\n{content}"})
        st.success("文件已加载！")

    if st.button("🗑️ 清空记忆"):
        st.session_state.messages = [st.session_state.messages[0]]
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.rerun()

# --- 5. 聊天主界面 ---
for m in st.session_state.messages:
    if m["role"] != "system" and not m["content"].startswith("【文件背景】："):
        with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("说点什么？"):
    with st.chat_message("user"): st.markdown(prompt)
    
    final_prompt = prompt
    # 自动识别是否需要联网
    if is_web_enabled:
        with st.spinner("🧠 正在思考是否需要联网..."):
            if check_intent(prompt):
                with st.status("🌐 AI 决定联网搜搜...", expanded=False):
                    web_results = get_web_info(prompt)
                    final_prompt = f"【参考资料】:\n{web_results}\n\n【用户问题】: {prompt}"
                    st.write("🔍 搜到了！")

    st.session_state.messages.append({"role": "user", "content": prompt})

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
        except Exception as e:
            st.error(f"连接失败: {e}")
