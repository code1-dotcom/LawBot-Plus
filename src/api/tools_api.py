"""工具和技能管理API"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.agents.tools.tool_manager import (
    Tool, Skill, ToolType, SkillType,
    tool_manager, skill_manager,
    init_default_tools, init_default_skills
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tools", tags=["工具管理"])


# ============== 请求模型 ==============

class ToolCreateRequest(BaseModel):
    name: str
    description: str
    tool_type: str
    config: dict = {}
    enabled: bool = True


class ToolUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[dict] = None


class ToolToggleRequest(BaseModel):
    enabled: bool


class SkillCreateRequest(BaseModel):
    name: str
    description: str
    skill_type: str
    prompt: str
    enabled: bool = True


class SkillUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    prompt: Optional[str] = None


class SkillToggleRequest(BaseModel):
    enabled: bool


# ============== 工具API ==============

@router.get("/", response_model=List[dict])
async def list_tools():
    """获取所有工具"""
    tools = await tool_manager.list_tools(include_disabled=True)
    return [t.to_dict() for t in tools]


@router.get("/enabled", response_model=List[dict])
async def list_enabled_tools():
    """获取已启用的工具"""
    tools = await tool_manager.get_enabled_tools()
    return [t.to_dict() for t in tools]


@router.get("/{tool_id}", response_model=dict)
async def get_tool(tool_id: str):
    """获取指定工具"""
    tool = await tool_manager.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    return tool.to_dict()


@router.post("/", response_model=dict)
async def create_tool(request: ToolCreateRequest):
    """创建工具"""
    tool = Tool(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        tool_type=request.tool_type,
        config=request.config,
        enabled=request.enabled
    )
    await tool_manager.add_tool(tool)
    logger.info(f"创建工具: {tool.name} ({tool.id})")
    return tool.to_dict()


@router.put("/{tool_id}", response_model=dict)
async def update_tool(tool_id: str, request: ToolUpdateRequest):
    """更新工具"""
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    tool = await tool_manager.update_tool(tool_id, updates)
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    logger.info(f"更新工具: {tool.name} ({tool_id})")
    return tool.to_dict()


@router.patch("/{tool_id}/toggle", response_model=dict)
async def toggle_tool(tool_id: str, request: ToolToggleRequest):
    """切换工具状态"""
    tool = await tool_manager.toggle_tool(tool_id, request.enabled)
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    status = "启用" if request.enabled else "禁用"
    logger.info(f"{status}工具: {tool.name} ({tool_id})")
    return tool.to_dict()


@router.delete("/{tool_id}")
async def delete_tool(tool_id: str):
    """删除工具"""
    success = await tool_manager.delete_tool(tool_id)
    if not success:
        raise HTTPException(status_code=404, detail="工具不存在")
    logger.info(f"删除工具: {tool_id}")
    return {"message": "删除成功"}


@router.post("/init-defaults")
async def init_defaults():
    """初始化默认工具和技能"""
    await init_default_tools()
    await init_default_skills()
    return {"message": "默认工具和技能已初始化"}


# ============== 技能API ==============

skill_router = APIRouter(prefix="/skills", tags=["技能管理"])


@skill_router.get("/", response_model=List[dict])
async def list_skills():
    """获取所有技能"""
    skills = await skill_manager.list_skills(include_disabled=True)
    return [s.to_dict() for s in skills]


@skill_router.get("/enabled", response_model=List[dict])
async def list_enabled_skills():
    """获取已启用的技能"""
    skills = await skill_manager.get_enabled_skills()
    return [s.to_dict() for s in skills]


@skill_router.get("/{skill_id}", response_model=dict)
async def get_skill(skill_id: str):
    """获取指定技能"""
    skill = await skill_manager.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    return skill.to_dict()


@skill_router.post("/", response_model=dict)
async def create_skill(request: SkillCreateRequest):
    """创建技能"""
    skill = Skill(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        skill_type=request.skill_type,
        prompt=request.prompt,
        enabled=request.enabled
    )
    await skill_manager.add_skill(skill)
    logger.info(f"创建技能: {skill.name} ({skill.id})")
    return skill.to_dict()


@skill_router.put("/{skill_id}", response_model=dict)
async def update_skill(skill_id: str, request: SkillUpdateRequest):
    """更新技能"""
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    skill = await skill_manager.update_skill(skill_id, updates)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    logger.info(f"更新技能: {skill.name} ({skill_id})")
    return skill.to_dict()


@skill_router.patch("/{skill_id}/toggle", response_model=dict)
async def toggle_skill(skill_id: str, request: SkillToggleRequest):
    """切换技能状态"""
    skill = await skill_manager.toggle_skill(skill_id, request.enabled)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    status = "启用" if request.enabled else "禁用"
    logger.info(f"{status}技能: {skill.name} ({skill_id})")
    return skill.to_dict()


@skill_router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    """删除技能"""
    success = await skill_manager.delete_skill(skill_id)
    if not success:
        raise HTTPException(status_code=404, detail="技能不存在")
    logger.info(f"删除技能: {skill_id}")
    return {"message": "删除成功"}
