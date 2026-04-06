import requests # 确保库的引入放在最前面
import streamlit as st
import json
import os
# 工具说明书：告诉 AI 你有哪些超能力
TOOLS_DESC = """
你现在拥有以下工具：
1. [SEARCH]: 当用户询问实时信息、新闻、天气或需要搜索才能回答的问题时使用。
2. [CALC]: 当用户需要进行复杂的数学计算或执行 Python 代码逻辑时使用。
3. [FILE]: 当用户询问关于已上传文件内容的问题时使用。
4. [CHAT]: 仅在简单的打招呼、闲聊或不需要外部信息时使用。

请先分析用户意图，只回复对应的标签（如 [SEARCH]），不要说多余的话。
"""
# --- 1. 配置区 ---
DEEPSEEK_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
BASE_URL = "https://api.deepseek.com/chat/completions"
DB_FILE = "chat_history.json"

# --- 2. 安全检查：如果Key为空，直接停止 app 并报错 ---
if not DEEPSEEK_KEY or not TAVILY_KEY:
    st.error("⚠️ Secrets 里的 OPENAI_API_KEY 或 TAVILY_API_KEY 貌似没设好？快去 Streamlit 后台瞧瞧。")
    st.stop() # 彻底停止应用

# --- 3. 增强版工具函数 (已融合 Claude 的错误处理优化) ---

def dispatch_center(user_query):
    """调度中心：让 AI 自己选工具"""
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": TOOLS_DESC},
            {"role": "user", "content": f"用户输入：{user_query}\n请选择最合适的工具标签："}
        ],
        "max_tokens": 10
    }
    try:
        r = requests.post(BASE_URL, headers=headers, json=payload, timeout=5)
        decision = r.json()["choices"][0]["message"]["content"].strip().upper()
        return decision
    except:
        return "[CHAT]"

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
    """加载历史记忆 (已融合 Token 限制优化：只保留最近10条对话)"""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
            # 只保留系统提示词 + 最近10条对话（避免token爆表）
            if len(history) > 11:
                return [history[0]] + history[-10:]
            return history
    return [{"role": "system", "content": "你是一个既能联网又能分析文件的全能助手。"}]

# --- 4. 页面初始化 ---
if "messages" not in st.session_state:
    st.session_state.messages = load_history()

# --- 5. 侧边栏 ---
with st.sidebar:
    st.title("⚡ 增强中心")
    is_web_enabled = st.toggle("🌍 开启自动意图联网", value=True)
    
    st.divider()
    
    # 文件中心
    st.header("📁 文件中心")
    uploaded_file = st.file_uploader("上传文本文件", type=['txt', 'py', 'md'])
    if uploaded_file and st.button("喂给 AI 学习"):
        # 增加文件大小限制 (1MB以内)
        if uploaded_file.size > 1024 * 1024:
            st.error("文件太大，请上传小于1MB的文件")
        else:
            # decode 时使用 'ignore'，遇到乱码自动跳过，不报错
            content = uploaded_file.read().decode("utf-8", errors='ignore')
            st.session_state.messages.append({"role": "user", "content": f"【文件背景】：\n{content}"})
            st.success("文件已加载！")

    if st.button("🗑️ 清空记忆"):
        # 只保留 system prompt
        st.session_state.messages = [st.session_state.messages[0]]
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.rerun()

# --- 6. 聊天主界面 ---
# 统一对话展示 (过滤掉文件背景)
for m in st.session_state.messages:
    if m["role"] != "system" and not m["content"].startswith("【文件背景】："):
        with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("指令下达..."):
    with st.chat_message("user"): st.markdown(prompt)
    
    final_prompt = prompt
    # --- 智能调度阶段 ---
    with st.spinner("🤖 Agent 正在思考决策..."):
        tool_choice = dispatch_center(prompt)
    
    # --- 根据 AI 的决策执行工具 ---
    if "[SEARCH]" in tool_choice and is_web_enabled:
        with st.status("🌐 正在调用搜索工具...", expanded=False):
            res = get_web_info(prompt)
            final_prompt = f"【联网插件返回】：\n{res}\n\n问题：{prompt}"
    
    elif "[FILE]" in tool_choice:
        with st.status("📁 正在检索本地文件...", expanded=False):
            # 这里可以保留你之前的逻辑，或者后续升级成 Claude 说的向量搜索
            st.write("已关联文件上下文进行回答")

    elif "[CALC]" in tool_choice:
        with st.status("🔢 正在准备计算环境...", expanded=False):
            # 这里甚至可以加一个简单的 eval() 逻辑，或者让 AI 模拟计算
            final_prompt = f"请作为高级数学专家，精确计算以下问题：{prompt}"

    # --- 统一展示和记忆 ---
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # ... 后面的流式请求代码保持不变，但记得发送的是 final_prompt ...
    # 发起 DeepSeek 请求
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
            # 将变量名改为 response 避免干扰
            response = requests.post(BASE_URL, headers=headers, json=payload, stream=True)
            for line in response.iter_lines():
                if line:
                    decoded = line.decode("utf-8").replace("data: ", "")
                    if decoded == "[DONE]": break
                    try:
                        line_json = json.loads(decoded)
                        content = line_json["choices"][0]["delta"].get("content", "")
                        full_res += content
                        placeholder.markdown(full_res + "▌")
                    except: continue
            
            placeholder.markdown(full_res)
            
            # --- 保存 AI 回答并保存文件 ---
            st.session_state.messages.append({"role": "assistant", "content": full_res})
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            st.error(f"连接失败: {e}")
