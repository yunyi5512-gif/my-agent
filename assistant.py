import streamlit as st
import requests
import json
import os

# --- 1. 基础配置 ---
st.set_page_config(page_title="霄的 AI 实验室", page_icon="📂")
st.title("📂 文件分析版 AI Agent")

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    st.error("❌ 未检测到环境变量 OPENAI_API_KEY，请检查系统设置！")
    st.stop()
BASE_URL = "https://api.deepseek.com/chat/completions"
DB_FILE = "chat_history.json"

# --- 2. 记忆存取逻辑 ---
def load_history():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return [{"role": "system", "content": "你是一个专业的代码助手。"}]

def save_history(history):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

if "messages" not in st.session_state:
    st.session_state.messages = load_history()

# --- 3. 侧边栏：【新增】文件上传功能 ---
with st.sidebar:
    st.header("📁 文件中心")
    uploaded_file = st.file_uploader("上传一个文本文件 (.txt, .py, .md)", type=['txt', 'py', 'md'])
    
    if uploaded_file is not None:
        # 读取文件内容
        content = uploaded_file.read().decode("utf-8")
        st.success("文件读取成功！")
        if st.button("让 AI 学习这个文件"):
            # 将文件内容作为背景知识喂给 AI
            file_info = f"【已知文件内容如下】：\n{content}\n---"
            st.session_state.messages.append({"role": "user", "content": file_info})
            st.write("✅ 已将文件内容存入当前上下文")

    st.divider()
    if st.button("彻底格式化记忆"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.session_state.messages = [{"role": "system", "content": "你是一个专业的代码助手。"}]
        st.rerun()

# --- 4. 聊天界面渲染 ---
for message in st.session_state.messages:
    if message["role"] != "system" and not message["content"].startswith("【已知文件内容"):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# --- 5. 对话逻辑 (打字机效果版) ---
if prompt := st.chat_input("说点什么？"):
    # 在界面展示用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 展示 AI 消息容器
    with st.chat_message("assistant"):
        # 创建一个流式处理的占位符
        response_placeholder = st.empty()
        full_response = ""
        
        try:
            headers = {"Authorization": f"Bearer {API_KEY}"}
            payload = {
                "model": "deepseek-chat",
                "messages": st.session_state.messages,
                "temperature": 0.7,
                "stream": True # 💡 关键：开启流式传输
            }
            
            # 发送请求
            response = requests.post(BASE_URL, headers=headers, json=payload, stream=True, timeout=60)
            
            if response.status_code == 200:
                # 遍历响应流
                for line in response.iter_lines():
                    if line:
                        # 去掉前面的 "data: " 前缀
                        line_data = line.decode("utf-8")
                        if line_data.startswith("data: "):
                            line_data = line_data[6:]
                        
                        # 如果收到 [DONE] 说明结束了
                        if line_data == "[DONE]":
                            break
                        
                        try:
                            chunk = json.loads(line_data)
                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                delta = chunk["choices"][0].get("delta", {})
                                if "content" in delta:
                                    content = delta["content"]
                                    full_response += content
                                    # 💡 实时更新界面上的文字，形成打字机效果
                                    response_placeholder.markdown(full_response + "▌")
                        except json.JSONDecodeError:
                            continue
                
                # 最后去掉光标，完整显示
                response_placeholder.markdown(full_response)
                
                # 存入记忆并存盘
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_history(st.session_state.messages)
            else:
                st.error(f"API 报错: {response.status_code}")
                
        except Exception as e:
            st.error(f"发生错误: {e}")