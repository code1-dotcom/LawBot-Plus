"""Agent工作流测试"""
import pytest
import asyncio
from src.agents.state import AgentState
from src.agents.workflow import run_legal_consultation


class TestAgentWorkflow:
    """测试多智能体工作流"""
    
    @pytest.mark.asyncio
    async def test_simple_consultation(self):
        """测试简单咨询"""
        result = await run_legal_consultation(
            user_input="民间借贷纠纷如何起诉？",
            session_id="test-session-001"
        )
        
        assert result is not None
        assert result.answer is not None
        assert isinstance(result.sources, list)
        assert isinstance(result.confidence, float)
    
    @pytest.mark.asyncio
    async def test_agent_state(self):
        """测试Agent状态"""
        state = AgentState(
            session_id="test-001",
            user_input="离婚后孩子抚养费怎么算？"
        )
        
        assert state.session_id == "test-001"
        assert state.current_agent == "planner"
        assert state.needs_review is False
