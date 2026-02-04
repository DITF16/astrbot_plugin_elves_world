"""
战斗系统数据模型

定义战斗中使用的所有数据类和枚举类型。
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class BattleType(Enum):
    """战斗类型"""
    WILD = "wild"           # 野外遭遇
    BOSS = "boss"           # BOSS战
    PVP = "pvp"             # 玩家对战
    TRAINER = "trainer"     # NPC训练师


class ActionType(Enum):
    """行动类型"""
    SKILL = "skill"         # 使用技能
    SWITCH = "switch"       # 换精灵
    ITEM = "item"           # 使用道具
    CATCH = "catch"         # 捕捉
    FLEE = "flee"           # 逃跑


@dataclass
class BattleAction:
    """
    战斗行动
    
    表示玩家或敌方的一次行动选择。
    """
    action_type: ActionType
    actor_id: str           # 行动者精灵instance_id
    target_id: str = ""     # 目标精灵instance_id
    skill_id: str = ""      # 技能ID（如果是技能行动）
    item_id: str = ""       # 道具ID（如果是道具行动）
    switch_to_id: str = ""  # 换上的精灵ID（如果是换精灵）
    ball_id: str = ""       # 精灵球ID（如果是捕捉行动）
    priority: int = 0       # 优先级（先制技能等）


@dataclass
class BattleResult:
    """
    单次行动结果
    
    记录一次技能/道具使用的详细结果。
    """
    success: bool = True
    damage: int = 0
    is_critical: bool = False
    effectiveness: float = 1.0  # 0.5=抵抗, 1=普通, 2=克制
    is_missed: bool = False
    status_applied: str = ""    # 施加的状态
    status_damage: int = 0      # 状态伤害
    healed: int = 0             # 治疗量
    message: str = ""           # 战斗信息
    target_fainted: bool = False
    actor_fainted: bool = False


@dataclass
class TurnResult:
    """
    回合结果
    
    记录一个完整回合的所有信息。
    """
    turn_number: int
    weather: str = "clear"
    actions: List[Dict] = field(default_factory=list)  # 行动记录
    messages: List[str] = field(default_factory=list)  # 战斗消息
    player_monster_fainted: bool = False
    enemy_monster_fainted: bool = False
    caught_monster: Dict = field(default_factory=dict)  # 捕获的精灵数据
    battle_ended: bool = False
    winner: str = ""  # "player" / "enemy" / "flee" / "catch" / ""


@dataclass
class BattleState:
    """
    战斗状态
    
    保存整场战斗的状态信息，是战斗系统的核心数据结构。
    """
    battle_id: str = ""
    battle_type: BattleType = BattleType.WILD

    # 玩家方
    player_id: str = ""
    player_team: List[Dict] = field(default_factory=list)
    player_active_index: int = 0

    # 敌方
    enemy_team: List[Dict] = field(default_factory=list)
    enemy_active_index: int = 0
    enemy_is_wild: bool = True
    enemy_trainer_name: str = ""

    # BOSS特殊配置
    boss_id: str = ""
    boss_config: Dict = field(default_factory=dict)

    # 战斗环境
    weather: str = "clear"
    weather_turns: int = 0  # 天气剩余回合，0=永久

    # 战斗状态
    turn_count: int = 0
    is_active: bool = True
    can_flee: bool = True
    can_catch: bool = True

    # 临时状态修正（战斗中的能力变化）
    player_stat_stages: Dict[str, int] = field(default_factory=lambda: {
        "attack": 0, "defense": 0, "sp_attack": 0,
        "sp_defense": 0, "speed": 0, "accuracy": 0, "evasion": 0
    })
    enemy_stat_stages: Dict[str, int] = field(default_factory=lambda: {
        "attack": 0, "defense": 0, "sp_attack": 0,
        "sp_defense": 0, "speed": 0, "accuracy": 0, "evasion": 0
    })

    # 战斗记录
    exp_gained: int = 0
    coins_gained: int = 0
    items_dropped: List[Dict] = field(default_factory=list)

    @property
    def player_monster(self) -> Optional[Dict]:
        """当前出战的玩家精灵"""
        if 0 <= self.player_active_index < len(self.player_team):
            return self.player_team[self.player_active_index]
        return None

    @property
    def enemy_monster(self) -> Optional[Dict]:
        """当前出战的敌方精灵"""
        if 0 <= self.enemy_active_index < len(self.enemy_team):
            return self.enemy_team[self.enemy_active_index]
        return None

    def get_player_available_monsters(self) -> List[Tuple[int, Dict]]:
        """获取玩家可用精灵列表 [(index, monster), ...]"""
        available = []
        for i, m in enumerate(self.player_team):
            if m.get("current_hp", 0) > 0:
                available.append((i, m))
        return available

    def get_enemy_available_monsters(self) -> List[Tuple[int, Dict]]:
        """获取敌方可用精灵列表"""
        available = []
        for i, m in enumerate(self.enemy_team):
            if m.get("current_hp", 0) > 0:
                available.append((i, m))
        return available

    def reset_player_stat_stages(self) -> None:
        """重置玩家能力等级"""
        self.player_stat_stages = {
            "attack": 0, "defense": 0, "sp_attack": 0,
            "sp_defense": 0, "speed": 0, "accuracy": 0, "evasion": 0
        }

    def reset_enemy_stat_stages(self) -> None:
        """重置敌方能力等级"""
        self.enemy_stat_stages = {
            "attack": 0, "defense": 0, "sp_attack": 0,
            "sp_defense": 0, "speed": 0, "accuracy": 0, "evasion": 0
        }
