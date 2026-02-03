"""
核心模块统一导出
"""

from .config_manager import ConfigManager
from .formulas import GameFormulas
from .monster import MonsterInstance
from .player import PlayerManager
from .battle import (
    BattleSystem,
    BattleState,
    BattleAction,
    BattleResult,
    TurnResult,
    BattleType,
    ActionType,
)
from .message_tracker import (
    MessageTracker,
    MessageType,
    get_message_tracker,
)
from .world import (
    WorldManager,
    ExplorationMap,
    ExploreResult,
    MapCell,
    CellType,
    EventType,
)

__all__ = [
    # 配置
    "ConfigManager",

    # 公式
    "GameFormulas",

    # 精灵
    "MonsterInstance",

    # 玩家
    "PlayerManager",

    # 战斗
    "BattleSystem",
    "BattleState",
    "BattleAction",
    "BattleResult",
    "TurnResult",
    "BattleType",
    "ActionType",

    # 世界
    "WorldManager",
    "ExplorationMap",
    "ExploreResult",
    "MapCell",
    "CellType",
    "EventType",

    # 消息追踪
    "MessageTracker",
    "MessageType",
    "get_message_tracker",
]

