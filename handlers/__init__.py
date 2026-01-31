"""
指令处理器模块
将所有Handler类导出，供main.py注册使用
"""

from .player_handlers import PlayerHandlers
from .monster_handlers import MonsterHandlers
from .battle_handlers import BattleHandlers
from .explore_handlers import ExploreHandlers

__all__ = [
    "PlayerHandlers",
    "MonsterHandlers",
    "BattleHandlers",
    "ExploreHandlers",
]
