"""Streamlit Web UI"""
import streamlit as st
import requests
import json
from datetime import datetime

# 页面配置
st.set_page_config(
    page_title="LawBot+ 法律咨询",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API配置
API_BASE = "http://localhost:8000"


def init_session():
    """初始化会话状态"""
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = ""
    
    if "current_messages" not in st.session_state:
        st.session_state.current_messages = []
    
    if "pending_review" not in st.session_state:
        st.session_state.pending_review = {}


# 初始化
init_session()


# ============== API 函数 ==============

def get_conversation_list() -> list:
    """获取会话列表"""
    try:
        response = requests.get(f"{API_BASE}/sessions", timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []


def get_conversation(session_id: str) -> dict:
    """获取指定会话"""
    try:
        response = requests.get(f"{API_BASE}/sessions/{session_id}", timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def save_conversation(session_id: str, messages: list, title: str = None) -> str:
    """保存会话"""
    try:
        response = requests.post(
            f"{API_BASE}/sessions",
            json={
                "session_id": session_id,
                "messages": messages,
                "title": title
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get("session_id", session_id)
        return session_id
    except Exception as e:
        st.error(f"保存失败: {e}")
        return session_id


def delete_conversation(session_id: str):
    """删除会话"""
    try:
        requests.delete(f"{API_BASE}/sessions/{session_id}", timeout=10)
    except:
        pass


def create_new_conversation():
    """创建新会话"""
    # 先保存当前会话
    if st.session_state.current_messages and st.session_state.current_session_id:
        save_conversation(st.session_state.current_session_id, st.session_state.current_messages)
    
    st.session_state.current_session_id = ""
    st.session_state.current_messages = []


def load_conversation(session_id: str):
    """加载指定会话"""
    conv = get_conversation(session_id)
    if conv:
        st.session_state.current_session_id = session_id
        st.session_state.current_messages = conv.get("messages", [])
    else:
        st.session_state.current_session_id = session_id
        st.session_state.current_messages = []


def call_chat_api_sync(message: str, session_id: str = None) -> dict:
    """同步调用聊天API"""
    try:
        response = requests.post(
            f"{API_BASE}/chat",
            json={"message": message, "session_id": session_id},
            timeout=120
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def get_task_result(task_id: str) -> dict:
    """获取任务结果"""
    try:
        response = requests.get(f"{API_BASE}/task/{task_id}", timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def get_pending_reviews() -> list:
    """获取待审核任务"""
    try:
        response = requests.get(f"{API_BASE}/hitl/tasks", timeout=10)
        return response.json()
    except:
        return []


def submit_review(task_id: str, action: str, modified_answer: str = None, comments: str = None) -> dict:
    """提交审核"""
    try:
        response = requests.post(
            f"{API_BASE}/hitl/review",
            json={
                "task_id": task_id,
                "action": action,
                "modified_answer": modified_answer,
                "comments": comments
            },
            timeout=30
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}


# ============== 侧边栏 ==============
with st.sidebar:
    st.title("⚖️ LawBot+")
    st.markdown("---")
    
    # 新建会话按钮
    if st.button("➕ 新建会话", use_container_width=True):
        create_new_conversation()
        st.rerun()
    
    st.markdown("---")
    
    # 会话历史
    st.subheader("📜 历史对话")
    
    with st.spinner("加载历史..."):
        conversations = get_conversation_list()
    
    if conversations:
        for conv in conversations[:20]:
            session_id = conv.get("session_id", "")
            title = conv.get("title", "新会话")
            is_active = session_id == st.session_state.current_session_id
            
            col1, col2 = st.columns([4, 1])
            with col1:
                btn_label = f"📄 {title[:20]}{'...' if len(title) > 20 else ''}"
                if st.button(btn_label, key=f"conv_{session_id}", use_container_width=True, type="primary" if is_active else "secondary"):
                    # 保存当前会话
                    if st.session_state.current_messages and st.session_state.current_session_id:
                        save_conversation(st.session_state.current_session_id, st.session_state.current_messages)
                    load_conversation(session_id)
                    st.rerun()
            
            with col2:
                if st.button("🗑️", key=f"del_{session_id}", help="删除会话"):
                    delete_conversation(session_id)
                    if is_active:
                        create_new_conversation()
                    st.rerun()
    else:
        st.caption("暂无历史对话")
    
    st.markdown("---")
    
    # 当前会话ID
    if st.session_state.current_session_id:
        st.caption(f"会话ID: {st.session_state.current_session_id[:16]}...")
    
    st.markdown("---")
    
    # HITL审核入口
    st.subheader("📋 待审核任务")
    pending = get_pending_reviews()
    if pending:
        st.info(f"有 {len(pending)} 个任务待审核")
    else:
        st.success("暂无待审核任务")


# ============== 主界面 ==============
st.title("🔍 法律咨询助手")

# 聊天区域
chat_container = st.container()

with chat_container:
    messages = st.session_state.current_messages
    
    if not messages:
        # 欢迎消息
        st.info("👋 欢迎使用 LawBot+ 法律咨询助手！请在下方输入您的法律问题。")
        st.markdown("""
        **支持的功能：**
        - 💬 智能法律问答
        - 📚 引用法律条文来源
        - 🤔 查看思考过程
        - ⚠️ 高风险问题人工审核
        """)
    
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            # 展示思考过程（可收起）
            if "thinking" in msg and msg["thinking"]:
                with st.expander("🤔 查看思考过程", expanded=False):
                    st.markdown(msg["thinking"])
            
            # 展示引用来源
            if "sources" in msg and msg["sources"]:
                with st.expander("📚 引用来源"):
                    for i, source in enumerate(msg["sources"], 1):
                        st.markdown(f"**{i}. {source.get('title', '未知来源')}**")
                        st.caption(source.get("content", "")[:200])


# ============== 输入区域 ==============
if prompt := st.chat_input("请输入您的法律问题..."):
    # 添加用户消息
    st.session_state.current_messages.append({
        "role": "user",
        "content": prompt
    })
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 调用API
    with st.spinner("LawBot+ 正在分析您的问题..."):
        result = call_chat_api_sync(prompt, st.session_state.current_session_id)
    
    if "error" in result:
        with st.chat_message("assistant"):
            st.error(f"处理失败: {result['error']}")
    else:
        st.session_state.current_session_id = result.get("session_id", st.session_state.current_session_id)
        task_id = result.get("task_id")

        if result.get("status") == "completed":
            # 直接从 ChatResponse.result 中取 answer（无需再查 /task）
            if result.get("result"):
                answer = result["result"].get("answer", "处理完成")
                sources = result["result"].get("sources", [])
                reasoning_chain = result["result"].get("reasoning_chain", [])
                
                # 将推理链转换为思考过程
                thinking = ""
                in_thinking = False
                for item in reasoning_chain:
                    if "=== 详细分析过程 ===" in str(item):
                        in_thinking = True
                        continue
                    if "=== 法律依据 ===" in str(item):
                        in_thinking = False
                        continue
                    if in_thinking and item:
                        thinking += str(item) + "\n\n"
                
                # 添加助手消息
                st.session_state.current_messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "thinking": thinking.strip() if thinking else ""
                })
                
                with st.chat_message("assistant"):
                    st.markdown(answer)
                    if thinking:
                        with st.expander("🤔 查看思考过程"):
                            st.markdown(thinking)
                    if sources:
                        with st.expander("📚 引用来源"):
                            for i, source in enumerate(sources, 1):
                                st.markdown(f"**{i}. {source.get('title', '未知来源')}**")
                                st.caption(source.get("content", "")[:200])
        else:
            # 需要审核
            st.session_state.pending_review[task_id] = True
            
            with st.chat_message("assistant"):
                st.warning("⏳ 您的咨询已提交，需要专业律师审核后返回结果。")
                st.info(f"任务ID: {task_id}")
        
        # 保存当前会话到 Redis
        save_conversation(st.session_state.current_session_id, st.session_state.current_messages)


# ============== 审核面板 ==============
with st.expander("🔍 审核面板", expanded=False):
    st.subheader("待审核任务")
    
    pending = get_pending_reviews()
    if pending:
        for task in pending[:5]:
            with st.container():
                st.markdown(f"**问题**: {task.get('user_question', '')[:100]}...")
                st.markdown(f"**AI回答**: {task.get('suggested_answer', '')[:100]}...")
                st.markdown(f"**风险等级**: {task.get('risk_level', 'unknown')} | **知识匹配度**: {task.get('confidence_score', 0):.2f}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✅ 批准", key=f"approve_{task['task_id'][:8]}"):
                        result = submit_review(task["task_id"], "approve")
                        if result.get("status") == "success":
                            st.success("已批准")
                            st.rerun()
                
                with col2:
                    modified = st.text_input("修改内容", key=f"modify_text_{task['task_id'][:8]}")
                    if st.button("💾 提交修改", key=f"submit_{task['task_id'][:8]}"):
                        if modified:
                            result = submit_review(task["task_id"], "modify", modified_answer=modified)
                            if result.get("status") == "success":
                                st.success("已修改并批准")
                                st.rerun()
                
                st.markdown("---")
    else:
        st.info("暂无待审核任务")


# ============== 工具和技能管理面板 ==============
with st.expander("🛠️ 工具与技能管理", expanded=False):
    
    # Tab切换
    tab_tools, tab_skills = st.tabs(["🧰 工具", "📝 技能"])
    
    with tab_tools:
        # 工具卡片式展示
        try:
            tools_response = requests.get(f"{API_BASE}/tools/", timeout=5)
            if tools_response.status_code == 200:
                tools = tools_response.json()
                
                # 添加按钮
                with st.expander("➕ 添加工具", expanded=False):
                    with st.form("add_tool_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            tool_name = st.text_input("名称", placeholder="天气查询")
                            tool_type = st.selectbox("类型", ["weather", "search", "calculator", "translator", "custom"])
                        with col2:
                            tool_desc = st.text_input("描述", placeholder="查询城市天气信息")
                            api_key = st.text_input("API密钥", type="password", placeholder="可选")
                        
                        if st.form_submit_button("确认添加"):
                            if tool_name:
                                resp = requests.post(
                                    f"{API_BASE}/tools/",
                                    json={
                                        "name": tool_name,
                                        "description": tool_desc,
                                        "tool_type": tool_type,
                                        "config": {"api_key": api_key} if api_key else {},
                                        "enabled": True
                                    }
                                )
                                if resp.status_code == 200:
                                    st.success("添加成功！")
                                    st.rerun()
                
                # 工具卡片列表
                if tools:
                    for i in range(0, len(tools), 2):
                        cols = st.columns(2)
                        for j, col in enumerate(cols):
                            if i + j < len(tools):
                                tool = tools[i + j]
                                with col:
                                    with st.container():
                                        # 卡片头部
                                        type_icons = {
                                            "weather": "🌤️",
                                            "search": "🔍",
                                            "calculator": "🧮",
                                            "translator": "🌐",
                                            "custom": "⚙️"
                                        }
                                        icon = type_icons.get(tool.get("tool_type"), "📦")
                                        
                                        # 工具卡片
                                        st.markdown(f"""
                                        <div style="
                                            background: {'#1a1a2e' if tool.get('enabled') else '#2d2d3d'};
                                            border-radius: 10px;
                                            padding: 15px;
                                            margin: 5px 0;
                                            border-left: 4px solid {'#4ade80' if tool.get('enabled') else '#6b7280'};
                                        ">
                                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                                <div>
                                                    <span style="font-size: 20px;">{icon}</span>
                                                    <span style="font-size: 16px; font-weight: bold; margin-left: 8px;">{tool['name']}</span>
                                                </div>
                                                <span style="
                                                    background: {'#22c55e' if tool.get('enabled') else '#6b7280'};
                                                    color: white;
                                                    padding: 2px 8px;
                                                    border-radius: 10px;
                                                    font-size: 12px;
                                                ">{'已启用' if tool.get('enabled') else '已禁用'}</span>
                                            </div>
                                            <div style="color: #9ca3af; font-size: 13px; margin-top: 8px;">{tool.get('description', '')}</div>
                                            <div style="color: #6b7280; font-size: 11px; margin-top: 5px;">类型: {tool.get('tool_type', 'custom')}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                        
                                        # 开关和删除按钮
                                        btn_col1, btn_col2 = st.columns([3, 1])
                                        with btn_col1:
                                            new_state = st.toggle(
                                                "启用/禁用",
                                                value=tool.get("enabled", False),
                                                key=f"tool_toggle_{tool['id']}"
                                            )
                                            if new_state != tool.get("enabled"):
                                                requests.patch(
                                                    f"{API_BASE}/tools/{tool['id']}/toggle",
                                                    json={"enabled": new_state}
                                                )
                                                st.rerun()
                                        with btn_col2:
                                            if st.button("🗑️", key=f"del_tool_{tool['id']}", use_container_width=True):
                                                requests.delete(f"{API_BASE}/tools/{tool['id']}")
                                                st.rerun()
                                        st.markdown("---")
                else:
                    st.info("暂无工具，点击上方添加或初始化")
        except Exception as e:
            st.error(f"连接失败: {e}")
    
    with tab_skills:
        # 技能卡片式展示
        try:
            skills_response = requests.get(f"{API_BASE}/skills/", timeout=5)
            if skills_response.status_code == 200:
                skills = skills_response.json()
                
                # 添加按钮
                with st.expander("➕ 添加技能", expanded=False):
                    with st.form("add_skill_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            skill_name = st.text_input("名称", placeholder="法律分析")
                            skill_type = st.selectbox("类型", ["legal_analysis", "contract_draft", "case_search", "custom"])
                        with col2:
                            skill_desc = st.text_input("描述", placeholder="专业法律问题分析")
                            skill_prompt = st.text_area("提示词", height=60, placeholder="系统提示词...")
                        
                        if st.form_submit_button("确认添加"):
                            if skill_name:
                                resp = requests.post(
                                    f"{API_BASE}/skills/",
                                    json={
                                        "name": skill_name,
                                        "description": skill_desc,
                                        "skill_type": skill_type,
                                        "prompt": skill_prompt,
                                        "enabled": True
                                    }
                                )
                                if resp.status_code == 200:
                                    st.success("添加成功！")
                                    st.rerun()
                
                st.markdown("---")
                
                # 技能卡片列表
                if skills:
                    for i in range(0, len(skills), 2):
                        cols = st.columns(2)
                        for j, col in enumerate(cols):
                            if i + j < len(skills):
                                skill = skills[i + j]
                                with col:
                                    with st.container():
                                        st.markdown(f"""
                                        <div style="
                                            background: {'#1a1a2e' if skill.get('enabled') else '#2d2d3d'};
                                            border-radius: 10px;
                                            padding: 15px;
                                            margin: 5px 0;
                                            border-left: 4px solid {'#60a5fa' if skill.get('enabled') else '#6b7280'};
                                        ">
                                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                                <div>
                                                    <span style="font-size: 16px; font-weight: bold;">📋 {skill['name']}</span>
                                                </div>
                                                <span style="
                                                    background: {'#3b82f6' if skill.get('enabled') else '#6b7280'};
                                                    color: white;
                                                    padding: 2px 8px;
                                                    border-radius: 10px;
                                                    font-size: 12px;
                                                ">{'已启用' if skill.get('enabled') else '已禁用'}</span>
                                            </div>
                                            <div style="color: #9ca3af; font-size: 13px; margin-top: 8px;">{skill.get('description', '')}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                        
                                        # 开关和删除按钮
                                        btn_col1, btn_col2 = st.columns([3, 1])
                                        with btn_col1:
                                            new_state = st.toggle(
                                                "启用/禁用",
                                                value=skill.get("enabled", False),
                                                key=f"skill_toggle_{skill['id']}"
                                            )
                                            if new_state != skill.get("enabled"):
                                                requests.patch(
                                                    f"{API_BASE}/skills/{skill['id']}/toggle",
                                                    json={"enabled": new_state}
                                                )
                                                st.rerun()
                                        with btn_col2:
                                            if st.button("🗑️", key=f"del_skill_{skill['id']}", use_container_width=True):
                                                requests.delete(f"{API_BASE}/skills/{skill['id']}")
                                                st.rerun()
                                        st.markdown("---")
                else:
                    st.info("暂无技能，点击上方添加")
        except Exception as e:
            st.error(f"连接失败: {e}")


# ============== 页脚 ==============
st.markdown("---")
st.caption("LawBot+ 法律咨询系统 | Powered by LangGraph + 阿里百炼")
