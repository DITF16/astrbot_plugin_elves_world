"""
战斗渲染器

负责战斗UI的文本渲染，包括：
- 战斗状态显示
- 技能菜单
- HP条
- 状态图标
"""

from typing import Dict, TYPE_CHECKING

from .constants import (
    HP_BAR_LENGTH,
    HP_BAR_FULL,
    HP_BAR_MEDIUM,
    HP_BAR_LOW,
    HP_BAR_EMPTY,
    HP_THRESHOLD_HIGH,
    HP_THRESHOLD_LOW,
    STATUS_ICONS,
    SEPARATOR_DOUBLE,
    SEPARATOR_SINGLE,
    SEPARATOR_LENGTH,
)
from .models import BattleType

if TYPE_CHECKING:
    from .models import BattleState
    from ..config_manager import ConfigManager


class BattleRenderer:
    """
    战斗渲染器
    
    负责生成战斗相关的显示文本。
    """
    
    def __init__(self, config_manager: "ConfigManager"):
        """
        初始化战斗渲染器
        
        Args:
            config_manager: 配置管理器
        """
        self.config = config_manager
    
    def get_battle_status_text(self, battle: "BattleState") -> str:
        """
        获取战斗状态文本
        
        Args:
            battle: 战斗状态
            
        Returns:
            格式化的战斗状态文本
        """
        player_monster = battle.player_monster
        enemy_monster = battle.enemy_monster

        if not player_monster or not enemy_monster:
            return "战斗数据异常"

        # 天气
        weather_text = self._get_weather_text(battle)

        # 敌方信息
        enemy_prefix = "野生 " if battle.enemy_is_wild else ""
        if battle.battle_type == BattleType.BOSS:
            enemy_prefix = "👹 BOSS "

        enemy_name = enemy_monster.get("nickname") or enemy_monster.get("name", "???")
        enemy_hp_bar = self._get_hp_bar(enemy_monster)
        enemy_status = self._get_status_icon(enemy_monster.get("status"))

        # 玩家信息
        player_name = player_monster.get("nickname") or player_monster.get("name", "???")
        player_hp_bar = self._get_hp_bar(player_monster)
        player_status = self._get_status_icon(player_monster.get("status"))

        text = (
            f"{weather_text}"
            f"{SEPARATOR_DOUBLE * SEPARATOR_LENGTH}\n"
            f"{enemy_prefix}{enemy_name} Lv.{enemy_monster.get('level', 1)} {enemy_status}\n"
            f"HP: {enemy_hp_bar} {enemy_monster.get('current_hp', 0)}/{enemy_monster.get('max_hp', 1)}\n"
            f"{SEPARATOR_SINGLE * SEPARATOR_LENGTH}\n"
            f"{player_name} Lv.{player_monster.get('level', 1)} {player_status}\n"
            f"HP: {player_hp_bar} {player_monster.get('current_hp', 0)}/{player_monster.get('max_hp', 1)}\n"
            f"{SEPARATOR_DOUBLE * SEPARATOR_LENGTH}"
        )

        return text
    
    def get_skill_menu_text(self, battle: "BattleState") -> str:
        """
        获取技能选择菜单
        
        Args:
            battle: 战斗状态
            
        Returns:
            技能菜单文本
        """
        player_monster = battle.player_monster
        if not player_monster:
            return "无可用技能"

        skills = player_monster.get("skills", [])
        if not skills:
            return "无可用技能"

        lines = ["请选择技能："]
        for i, skill_id in enumerate(skills, 1):
            skill = self.config.get_item("skills", skill_id)
            if skill:
                skill_name = skill.get("name", skill_id)
                skill_type = skill.get("type", "normal")
                power = skill.get("power", 0)
                power_text = f"威力:{power}" if power > 0 else "辅助"

                type_config = self.config.get_item("types", skill_type)
                type_icon = type_config.get("icon", "") if type_config else ""

                lines.append(f"{i}. {skill_name} {type_icon} {power_text}")
            else:
                lines.append(f"{i}. {skill_id}")

        return "\n".join(lines)
    
    def _get_weather_text(self, battle: "BattleState") -> str:
        """获取天气显示文本"""
        if battle.weather == "clear":
            return ""
            
        weather_config = self.config.get_item("weathers", battle.weather)
        if not weather_config:
            return ""
            
        weather_icon = weather_config.get("icon", "")
        weather_name = weather_config.get("name", battle.weather)
        return f"{weather_icon} {weather_name}\n"
    
    def _get_hp_bar(self, monster: Dict, length: int = HP_BAR_LENGTH) -> str:
        """
        生成HP条
        
        Args:
            monster: 精灵数据
            length: HP条长度
            
        Returns:
            HP条字符串
        """
        current = monster.get("current_hp", 0)
        maximum = monster.get("max_hp", 1)

        ratio = current / maximum if maximum > 0 else 0
        filled = int(ratio * length)
        empty = length - filled

        # 根据HP比例选择字符
        if ratio > HP_THRESHOLD_HIGH:
            char = HP_BAR_FULL
        elif ratio > HP_THRESHOLD_LOW:
            char = HP_BAR_MEDIUM
        else:
            char = HP_BAR_LOW

        return char * filled + HP_BAR_EMPTY * empty
    
    def _get_status_icon(self, status: str) -> str:
        """
        获取状态图标
        
        Args:
            status: 状态名称
            
        Returns:
            状态图标
        """
        return STATUS_ICONS.get(status, "")
