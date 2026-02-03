"""
消息追踪管理器
- 追踪游戏消息（地图、战斗）的 message_id
- 支持在发送新消息前撤回旧消息，防止刷屏
- 仅在支持撤回的平台（如 OneBot V11）上生效
"""

import time
from enum import Enum
from typing import Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from astrbot.api import logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent


class MessageType(Enum):
    """消息类型"""
    MAP = "map"           # 地图消息
    BATTLE = "battle"     # 战斗消息


@dataclass
class TrackedMessage:
    """被追踪的消息"""
    message_id: int
    message_type: MessageType
    timestamp: float = field(default_factory=time.time)
    platform: str = ""    # 平台类型，如 "aiocqhttp"
    session_id: str = ""  # 会话ID（群号或用户ID）
    
    def is_expired(self, ttl_seconds: float = 180.0) -> bool:
        """检查消息是否已过期（默认3分钟）"""
        return time.time() - self.timestamp > ttl_seconds


class MessageTracker:
    """
    消息追踪器
    
    功能：
    1. 记录每个用户最近发送的游戏消息（地图/战斗）
    2. 在发送新消息前，尝试撤回旧消息（如果在TTL内）
    3. 支持多平台，但撤回功能仅在支持的平台上生效
    """
    
    # 消息过期时间（秒），超过此时间不再撤回
    DEFAULT_TTL = 180.0  # 3分钟
    
    def __init__(self, ttl_seconds: float = DEFAULT_TTL):
        """
        初始化消息追踪器
        
        Args:
            ttl_seconds: 消息过期时间（秒），超过此时间不再撤回
        """
        self.ttl = ttl_seconds
        # 存储结构: {user_id: {MessageType: TrackedMessage}}
        self._messages: Dict[str, Dict[MessageType, TrackedMessage]] = {}
    
    def track(self, user_id: str, message_id: int, msg_type: MessageType,
              platform: str = "", session_id: str = "") -> None:
        """
        追踪一条消息
        
        Args:
            user_id: 用户ID
            message_id: 消息ID
            msg_type: 消息类型
            platform: 平台类型
            session_id: 会话ID
        """
        if user_id not in self._messages:
            self._messages[user_id] = {}
        
        self._messages[user_id][msg_type] = TrackedMessage(
            message_id=message_id,
            message_type=msg_type,
            platform=platform,
            session_id=session_id
        )
        logger.debug(f"[MessageTracker] 追踪消息: user={user_id}, type={msg_type.value}, msg_id={message_id}")
    
    def get_tracked(self, user_id: str, msg_type: MessageType) -> Optional[TrackedMessage]:
        """
        获取用户的被追踪消息
        
        Args:
            user_id: 用户ID
            msg_type: 消息类型
            
        Returns:
            TrackedMessage 或 None
        """
        if user_id not in self._messages:
            return None
        return self._messages[user_id].get(msg_type)
    
    def clear(self, user_id: str, msg_type: Optional[MessageType] = None) -> None:
        """
        清除用户的追踪记录
        
        Args:
            user_id: 用户ID
            msg_type: 消息类型，None 表示清除所有类型
        """
        if user_id not in self._messages:
            return
        
        if msg_type is None:
            del self._messages[user_id]
        elif msg_type in self._messages[user_id]:
            del self._messages[user_id][msg_type]
    
    async def recall_if_exists(self, user_id: str, msg_type: MessageType,
                                event: "AstrMessageEvent") -> bool:
        """
        如果存在未过期的消息，尝试撤回
        
        Args:
            user_id: 用户ID
            msg_type: 消息类型
            event: 消息事件（用于获取 bot 客户端）
            
        Returns:
            是否成功撤回
        """
        tracked = self.get_tracked(user_id, msg_type)
        if not tracked:
            return False
        
        # 检查是否过期
        if tracked.is_expired(self.ttl):
            logger.debug(f"[MessageTracker] 消息已过期，不撤回: user={user_id}, type={msg_type.value}")
            self.clear(user_id, msg_type)
            return False
        
        # 尝试撤回
        success = await self._do_recall(tracked, event)
        if success:
            self.clear(user_id, msg_type)
        return success
    
    async def _do_recall(self, tracked: TrackedMessage, 
                         event: "AstrMessageEvent") -> bool:
        """
        执行撤回操作
        
        Args:
            tracked: 被追踪的消息
            event: 消息事件
            
        Returns:
            是否成功撤回
        """
        try:
            platform_name = event.get_platform_name()
            
            # 目前只支持 aiocqhttp (OneBot V11)
            if platform_name == "aiocqhttp":
                return await self._recall_onebot(tracked, event)
            else:
                logger.debug(f"[MessageTracker] 平台 {platform_name} 不支持撤回")
                return False
                
        except Exception as e:
            logger.warning(f"[MessageTracker] 撤回消息失败: {e}")
            return False
    
    async def _recall_onebot(self, tracked: TrackedMessage,
                             event: "AstrMessageEvent") -> bool:
        """
        OneBot V11 撤回消息
        
        Args:
            tracked: 被追踪的消息
            event: 消息事件
            
        Returns:
            是否成功撤回
        """
        try:
            # 获取 bot 客户端
            bot = getattr(event, 'bot', None)
            if not bot:
                logger.debug("[MessageTracker] 无法获取 bot 客户端")
                return False
            
            # 调用 OneBot API 撤回消息
            await bot.call_action("delete_msg", message_id=tracked.message_id)
            logger.debug(f"[MessageTracker] 成功撤回消息: msg_id={tracked.message_id}")
            return True
            
        except Exception as e:
            # 撤回失败可能是因为：消息已被删除、超时、权限不足等
            logger.debug(f"[MessageTracker] OneBot 撤回失败: {e}")
            return False
    
    def cleanup_expired(self) -> int:
        """
        清理所有过期的追踪记录
        
        Returns:
            清理的记录数
        """
        count = 0
        users_to_remove = []
        
        for user_id, messages in self._messages.items():
            types_to_remove = []
            for msg_type, tracked in messages.items():
                if tracked.is_expired(self.ttl):
                    types_to_remove.append(msg_type)
                    count += 1
            
            for msg_type in types_to_remove:
                del messages[msg_type]
            
            if not messages:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self._messages[user_id]
        
        if count > 0:
            logger.debug(f"[MessageTracker] 清理了 {count} 条过期记录")
        
        return count


# 全局单例
_tracker_instance: Optional[MessageTracker] = None


def get_message_tracker() -> MessageTracker:
    """获取全局消息追踪器实例"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = MessageTracker()
    return _tracker_instance


def init_message_tracker(ttl_seconds: float = MessageTracker.DEFAULT_TTL) -> MessageTracker:
    """初始化全局消息追踪器"""
    global _tracker_instance
    _tracker_instance = MessageTracker(ttl_seconds)
    return _tracker_instance
