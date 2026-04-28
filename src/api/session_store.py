"""会话历史存储服务

三层存储策略：
1. Redis（优先）：高性能，30天TTL
2. PostgreSQL（降级）：持久化存储，永久保留
3. 内存（最终兜底）：进程生命周期

Redis 不可用时自动降级到 PostgreSQL，不丢失数据。
"""
import json
import threading
from datetime import datetime
from typing import List, Optional

from src.db.database import SyncSessionLocal
from src.db.models import Conversation, Message
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============== 内存兜底层 ==============

class InMemoryStore:
    """内存存储（最终兜底）"""
    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()

    def save(self, session_id: str, data: dict):
        with self._lock:
            self._sessions[session_id] = data

    def get(self, session_id: str) -> Optional[dict]:
        with self._lock:
            return self._sessions.get(session_id)

    def list_all(self) -> List[dict]:
        with self._lock:
            return list(self._sessions.values())

    def delete(self, session_id: str):
        with self._lock:
            self._sessions.pop(session_id, None)


# ============== PostgreSQL 存储层 ==============

class PostgresSessionStore:
    """PostgreSQL 会话存储"""

    def save_conversation(self, session_id: str, messages: List[dict], title: str = None):
        """保存会话到 PostgreSQL"""
        db = SyncSessionLocal()
        try:
            # 查找或创建会话
            conv = db.query(Conversation).filter_by(session_id=session_id).first()
            if not conv:
                conv = Conversation(session_id=session_id, status="active")
                db.add(conv)
                db.flush()

            # 更新标题和时间
            if title:
                conv.title = title
            conv.updated_at = datetime.now()
            if conv.extra_data is None:
                conv.extra_data = {}

            # 删除旧消息，重新插入
            db.query(Message).filter_by(conversation_id=conv.id).delete()

            for msg in messages:
                message = Message(
                    conversation_id=conv.id,
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    sources=msg.get("sources"),
                    reasoning_chain=msg.get("reasoning_chain"),
                    token_count=msg.get("token_count"),
                    extra_data=msg.get("extra_data"),
                    rewritten_query=msg.get("rewritten_query"),
                    tokenized_query=msg.get("tokenized_query"),
                )
                db.add(message)

            db.commit()
            logger.info(f"PostgreSQL: 会话已保存 session_id={session_id}, {len(messages)} 条消息")
        except Exception as e:
            db.rollback()
            logger.error(f"PostgreSQL: 保存会话失败 session_id={session_id}: {e}")
            raise
        finally:
            db.close()

    def get_conversation(self, session_id: str) -> Optional[dict]:
        """从 PostgreSQL 获取会话"""
        db = SyncSessionLocal()
        try:
            conv = db.query(Conversation).filter_by(session_id=session_id).first()
            if not conv:
                return None

            messages = db.query(Message).filter_by(
                conversation_id=conv.id
            ).order_by(Message.created_at).all()

            return {
                "session_id": conv.session_id,
                "title": conv.title or "新会话",
                "messages": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "sources": msg.sources,
                        "reasoning_chain": msg.reasoning_chain,
                        "token_count": msg.token_count,
                        "extra_data": msg.extra_data,
                        "rewritten_query": msg.rewritten_query,
                        "tokenized_query": msg.tokenized_query,
                    }
                    for msg in messages
                ],
                "created_at": conv.created_at.isoformat() if conv.created_at else datetime.now().isoformat(),
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"PostgreSQL: 获取会话失败 session_id={session_id}: {e}")
            return None
        finally:
            db.close()

    def list_conversations(self, limit: int = 20, offset: int = 0) -> List[dict]:
        """从 PostgreSQL 获取会话列表"""
        db = SyncSessionLocal()
        try:
            convs = (
                db.query(Conversation)
                .filter_by(status="active")
                .order_by(Conversation.updated_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            result = []
            for conv in convs:
                # 获取首条消息作为标题回退
                first_msg = (
                    db.query(Message)
                    .filter_by(conversation_id=conv.id)
                    .order_by(Message.created_at)
                    .first()
                )
                title = conv.title
                if not title and first_msg:
                    title = first_msg.content[:30] + ("..." if len(first_msg.content) > 30 else "")

                result.append({
                    "session_id": conv.session_id,
                    "title": title or "新会话",
                    "messages": [],
                    "created_at": conv.created_at.isoformat() if conv.created_at else datetime.now().isoformat(),
                    "updated_at": conv.updated_at.isoformat() if conv.updated_at else datetime.now().isoformat(),
                })
            return result
        except Exception as e:
            logger.error(f"PostgreSQL: 获取会话列表失败: {e}")
            return []
        finally:
            db.close()

    def delete_conversation(self, session_id: str):
        """从 PostgreSQL 删除会话"""
        db = SyncSessionLocal()
        try:
            conv = db.query(Conversation).filter_by(session_id=session_id).first()
            if conv:
                db.delete(conv)
                db.commit()
                logger.info(f"PostgreSQL: 会话已删除 session_id={session_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"PostgreSQL: 删除会话失败 session_id={session_id}: {e}")
        finally:
            db.close()

    def update_conversation(self, session_id: str, messages: List[dict]):
        """更新会话"""
        conv = self.get_conversation(session_id)
        title = conv.get("title") if conv else None
        self.save_conversation(session_id, messages, title)


# ============== SessionStore 主类 ==============

class SessionStore:
    """三层会话存储（Redis优先 → PostgreSQL降级 → 内存兜底）"""
    KEY_PREFIX = "lawbot:session:"
    LIST_KEY = "lawbot:sessions:list"

    def __init__(self):
        self.redis = None
        self._use_redis = None  # None=未检测, True=使用Redis, False=不使用Redis
        self.pg_store = PostgresSessionStore()
        self.memory = InMemoryStore()

    async def connect(self):
        """检测并连接 Redis"""
        if self._use_redis is not None:
            return

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
            self._use_redis = True
            logger.info("SessionStore: Redis连接成功，会话将持久化存储到Redis")
        except Exception as e:
            self._use_redis = False
            logger.warning(f"SessionStore: Redis不可用，将降级到PostgreSQL: {e}")
            if self.redis:
                try:
                    await self.redis.close()
                except Exception:
                    pass
                self.redis = None

    def _auto_title(self, messages: List[dict]) -> str:
        """自动生成会话标题"""
        if not messages:
            return "新会话"
        for msg in messages:
            if msg.get("role") == "user":
                content = msg["content"]
                return content[:30] + ("..." if len(content) > 30 else "")
        return "新会话"

    def _build_data(self, session_id: str, messages: List[dict], title: str = None) -> dict:
        """构建存储数据"""
        title = title or self._auto_title(messages)
        return {
            "session_id": session_id,
            "title": title,
            "messages": messages,
            "updated_at": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
        }

    async def save_conversation(self, session_id: str, messages: List[dict], title: str = None):
        """保存会话"""
        await self.connect()

        data = self._build_data(session_id, messages, title)

        if self._use_redis:
            try:
                key = f"{self.KEY_PREFIX}{session_id}"
                await self.redis.set(
                    key, json.dumps(data, ensure_ascii=False), ex=86400 * 30
                )
                await self.redis.zadd(self.LIST_KEY, {session_id: datetime.now().timestamp()})
                logger.info(f"Redis: 会话已保存 session_id={session_id}")
                return
            except Exception as e:
                logger.warning(f"Redis写入失败，降级到PostgreSQL: {e}")
                self._use_redis = False

        # PostgreSQL 降级
        try:
            self.pg_store.save_conversation(session_id, messages, title)
        except Exception as e:
            logger.warning(f"PostgreSQL写入失败，降级到内存: {e}")
            self.memory.save(session_id, data)

    async def get_conversation(self, session_id: str) -> Optional[dict]:
        """获取会话"""
        await self.connect()

        if self._use_redis:
            try:
                key = f"{self.KEY_PREFIX}{session_id}"
                data = await self.redis.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Redis读取失败，降级到PostgreSQL: {e}")

        # PostgreSQL 降级
        result = self.pg_store.get_conversation(session_id)
        if result:
            return result

        return self.memory.get(session_id)

    async def list_conversations(self, limit: int = 20, offset: int = 0) -> List[dict]:
        """获取会话列表"""
        await self.connect()

        if self._use_redis:
            try:
                session_ids = await self.redis.zrevrange(
                    self.LIST_KEY, offset, offset + limit - 1
                )
                conversations = []
                for sid in session_ids:
                    conv = await self.get_conversation(sid)
                    if conv:
                        conversations.append(conv)
                return conversations
            except Exception as e:
                logger.warning(f"Redis列表读取失败，降级到PostgreSQL: {e}")

        # PostgreSQL 降级
        result = self.pg_store.list_conversations(limit, offset)
        if result:
            return result

        sessions = self.memory.list_all()
        sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return sessions[offset:offset + limit]

    async def delete_conversation(self, session_id: str):
        """删除会话"""
        await self.connect()

        # 三个存储层都删除
        self.memory.delete(session_id)

        if self._use_redis and self.redis:
            try:
                key = f"{self.KEY_PREFIX}{session_id}"
                await self.redis.delete(key)
                await self.redis.zrem(self.LIST_KEY, session_id)
            except Exception as e:
                logger.warning(f"Redis删除失败: {e}")

        try:
            self.pg_store.delete_conversation(session_id)
        except Exception as e:
            logger.warning(f"PostgreSQL删除失败: {e}")

    async def update_conversation(self, session_id: str, messages: List[dict]):
        """更新会话"""
        conv = await self.get_conversation(session_id)
        title = conv.get("title") if conv else None
        await self.save_conversation(session_id, messages, title)


session_store = SessionStore()
