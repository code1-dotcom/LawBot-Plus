"""工具和技能管理系统"""
import json
from datetime import datetime
from enum import Enum
from typing import Any, Callable, List, Optional

import httpx

from src.config import get_settings


class ToolType(str, Enum):
    """工具类型"""
    WEATHER = "weather"           # 天气查询
    SEARCH = "search"            # 搜索
    CALCULATOR = "calculator"    # 计算器
    TRANSLATOR = "translator"   # 翻译
    CUSTOM = "custom"            # 自定义


class SkillType(str, Enum):
    """技能类型"""
    LEGAL_ANALYSIS = "legal_analysis"    # 法律分析
    CONTRACT_DRAFT = "contract_draft"    # 合同起草
    CASE_SEARCH = "case_search"          # 案例检索
    CUSTOM = "custom"                    # 自定义


class Tool:
    """工具定义"""
    
    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        tool_type: str,
        enabled: bool = True,
        config: dict = None,
        created_at: datetime = None,
        updated_at: datetime = None
    ):
        self.id = id
        self.name = name
        self.description = description
        self.tool_type = tool_type
        self.enabled = enabled
        self.config = config or {}
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tool_type": self.tool_type,
            "enabled": self.enabled,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Tool":
        data = data.copy()
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


class Skill:
    """技能定义"""
    
    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        skill_type: str,
        prompt: str,
        enabled: bool = True,
        created_at: datetime = None,
        updated_at: datetime = None
    ):
        self.id = id
        self.name = name
        self.description = description
        self.skill_type = skill_type
        self.prompt = prompt
        self.enabled = enabled
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "skill_type": self.skill_type,
            "prompt": self.prompt,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Skill":
        data = data.copy()
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


class ToolRegistry:
    """工具注册表"""
    
    # 内置工具执行器
    _executors: dict[str, Callable] = {}
    
    @classmethod
    def register_executor(cls, tool_type: str, executor: Callable):
        """注册工具执行器"""
        cls._executors[tool_type] = executor
    
    @classmethod
    def get_executor(cls, tool_type: str) -> Optional[Callable]:
        """获取工具执行器"""
        return cls._executors.get(tool_type)
    
    @classmethod
    async def execute_tool(cls, tool: Tool, params: dict) -> dict:
        """执行工具"""
        executor = cls.get_executor(tool.tool_type)
        if not executor:
            return {"success": False, "error": f"未找到执行器: {tool.tool_type}"}
        
        try:
            result = await executor(tool, params)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


# 内置工具执行器
async def weather_executor(tool: Tool, params: dict) -> dict:
    """天气查询执行器（使用高德MCP服务）"""
    settings = get_settings()
    api_key = tool.config.get("api_key") or settings.amap_api_key
    location = params.get("location", "")
    
    if not location:
        return {"error": "缺少位置参数"}
    
    # 使用高德天气API
    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params={
            "key": api_key,
            "city": location,
            "extensions": "all"
        })
        data = response.json()
        
        if data.get("status") == "1":
            lives = data.get("lives", [])
            if lives:
                weather_info = lives[0]
                return {
                    "location": weather_info.get("city", ""),
                    "weather": weather_info.get("weather", ""),
                    "temperature": weather_info.get("temperature", ""),
                    "winddirection": weather_info.get("winddirection", ""),
                    "windpower": weather_info.get("windpower", ""),
                    "humidity": weather_info.get("humidity", ""),
                    "reporttime": weather_info.get("reporttime", "")
                }
        
        return {"error": data.get("info", "获取天气信息失败")}


# 注册执行器
ToolRegistry.register_executor("weather", weather_executor)


class ToolManager:
    """工具管理器"""
    
    TOOLS_KEY = "lawbot:tools:list"
    TOOL_PREFIX = "lawbot:tool:"
    
    def __init__(self):
        self.redis = None
        self._memory_tools: dict[str, Tool] = {}
    
    async def _ensure_redis(self):
        """确保Redis连接"""
        if self.redis is None:
            try:
                import redis.asyncio as redis_async
                from src.config import get_settings
                settings = get_settings()
                
                self.redis = redis_async.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2
                )
                await self.redis.ping()
            except:
                self.redis = None
    
    async def add_tool(self, tool: Tool) -> Tool:
        """添加工具"""
        await self._ensure_redis()
        
        if self.redis:
            await self.redis.hset(
                f"{self.TOOL_PREFIX}{tool.id}",
                mapping={
                    "data": json.dumps(tool.to_dict(), ensure_ascii=False)
                }
            )
            await self.redis.sadd(self.TOOLS_KEY, tool.id)
        else:
            self._memory_tools[tool.id] = tool
        
        return tool
    
    async def get_tool(self, tool_id: str) -> Optional[Tool]:
        """获取工具"""
        await self._ensure_redis()
        
        if self.redis:
            data = await self.redis.hget(f"{self.TOOL_PREFIX}{tool_id}", "data")
            if data:
                return Tool.from_dict(json.loads(data))
        else:
            return self._memory_tools.get(tool_id)
        
        return None
    
    async def list_tools(self, include_disabled: bool = False) -> List[Tool]:
        """列出所有工具"""
        await self._ensure_redis()
        
        tools = []
        if self.redis:
            tool_ids = await self.redis.smembers(self.TOOLS_KEY)
            for tid in tool_ids:
                tool = await self.get_tool(tid)
                if tool and (include_disabled or tool.enabled):
                    tools.append(tool)
        else:
            tools = list(self._memory_tools.values())
            if not include_disabled:
                tools = [t for t in tools if t.enabled]
        
        return tools
    
    async def get_enabled_tools(self) -> List[Tool]:
        """获取已启用的工具"""
        return await self.list_tools(include_disabled=False)
    
    async def update_tool(self, tool_id: str, updates: dict) -> Optional[Tool]:
        """更新工具"""
        tool = await self.get_tool(tool_id)
        if not tool:
            return None
        
        for key, value in updates.items():
            if hasattr(tool, key):
                setattr(tool, key, value)
        tool.updated_at = datetime.now()
        
        await self._ensure_redis()
        if self.redis:
            await self.redis.hset(
                f"{self.TOOL_PREFIX}{tool.id}",
                mapping={"data": json.dumps(tool.to_dict(), ensure_ascii=False)}
            )
        else:
            self._memory_tools[tool.id] = tool
        
        return tool
    
    async def delete_tool(self, tool_id: str) -> bool:
        """删除工具"""
        await self._ensure_redis()
        
        if self.redis:
            await self.redis.delete(f"{self.TOOL_PREFIX}{tool_id}")
            await self.redis.srem(self.TOOLS_KEY, tool_id)
        else:
            if tool_id in self._memory_tools:
                del self._memory_tools[tool_id]
        
        return True
    
    async def toggle_tool(self, tool_id: str, enabled: bool) -> Optional[Tool]:
        """切换工具状态"""
        return await self.update_tool(tool_id, {"enabled": enabled})


# 全局工具管理器实例
tool_manager = ToolManager()


class SkillManager:
    """技能管理器"""
    
    SKILLS_KEY = "lawbot:skills:list"
    SKILL_PREFIX = "lawbot:skill:"
    
    def __init__(self):
        self.redis = None
        self._memory_skills: dict[str, Skill] = {}
    
    async def _ensure_redis(self):
        """确保Redis连接"""
        if self.redis is None:
            try:
                import redis.asyncio as redis_async
                from src.config import get_settings
                settings = get_settings()
                
                self.redis = redis_async.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2
                )
                await self.redis.ping()
            except:
                self.redis = None
    
    async def add_skill(self, skill: Skill) -> Skill:
        """添加技能"""
        await self._ensure_redis()
        
        if self.redis:
            await self.redis.hset(
                f"{self.SKILL_PREFIX}{skill.id}",
                mapping={
                    "data": json.dumps(skill.to_dict(), ensure_ascii=False)
                }
            )
            await self.redis.sadd(self.SKILLS_KEY, skill.id)
        else:
            self._memory_skills[skill.id] = skill
        
        return skill
    
    async def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取技能"""
        await self._ensure_redis()
        
        if self.redis:
            data = await self.redis.hget(f"{self.SKILL_PREFIX}{skill_id}", "data")
            if data:
                return Skill.from_dict(json.loads(data))
        else:
            return self._memory_skills.get(skill_id)
        
        return None
    
    async def list_skills(self, include_disabled: bool = False) -> List[Skill]:
        """列出所有技能"""
        await self._ensure_redis()
        
        skills = []
        if self.redis:
            skill_ids = await self.redis.smembers(self.SKILLS_KEY)
            for sid in skill_ids:
                skill = await self.get_skill(sid)
                if skill and (include_disabled or skill.enabled):
                    skills.append(skill)
        else:
            skills = list(self._memory_skills.values())
            if not include_disabled:
                skills = [s for s in skills if s.enabled]
        
        return skills
    
    async def get_enabled_skills(self) -> List[Skill]:
        """获取已启用的技能"""
        return await self.list_skills(include_disabled=False)
    
    async def update_skill(self, skill_id: str, updates: dict) -> Optional[Skill]:
        """更新技能"""
        skill = await self.get_skill(skill_id)
        if not skill:
            return None
        
        for key, value in updates.items():
            if hasattr(skill, key):
                setattr(skill, key, value)
        skill.updated_at = datetime.now()
        
        await self._ensure_redis()
        if self.redis:
            await self.redis.hset(
                f"{self.SKILL_PREFIX}{skill.id}",
                mapping={"data": json.dumps(skill.to_dict(), ensure_ascii=False)}
            )
        else:
            self._memory_skills[skill.id] = skill
        
        return skill
    
    async def delete_skill(self, skill_id: str) -> bool:
        """删除技能"""
        await self._ensure_redis()
        
        if self.redis:
            await self.redis.delete(f"{self.SKILL_PREFIX}{skill_id}")
            await self.redis.srem(self.SKILLS_KEY, skill_id)
        else:
            if skill_id in self._memory_skills:
                del self._memory_skills[skill_id]
        
        return True
    
    async def toggle_skill(self, skill_id: str, enabled: bool) -> Optional[Skill]:
        """切换技能状态"""
        return await self.update_skill(skill_id, {"enabled": enabled})


# 全局技能管理器实例
skill_manager = SkillManager()


async def init_default_tools():
    """初始化默认工具"""
    settings = get_settings()
    # 天气查询工具
    weather_tool = Tool(
        id="weather_query",
        name="天气查询",
        description="查询指定城市的天气信息，包括温度、湿度、风力等",
        tool_type="weather",
        enabled=False,
        config={
            "api_key": settings.amap_api_key
        }
    )
    await tool_manager.add_tool(weather_tool)


async def init_default_skills():
    """初始化默认技能"""
    # 法律分析技能
    legal_skill = Skill(
        id="legal_analysis",
        name="法律分析",
        description="专业的法律问题分析与解答",
        skill_type="legal_analysis",
        prompt="你是一位专业的法律顾问，擅长分析各类法律问题。请根据提供的信息进行专业的法律分析。"
    )
    await skill_manager.add_skill(legal_skill)
