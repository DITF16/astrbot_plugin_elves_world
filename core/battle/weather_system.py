"""
天气系统

负责处理天气相关的逻辑，包括：
- 天气伤害
- 天气回合衰减
"""

from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import BattleState
    from ..config_manager import ConfigManager


class WeatherSystem:
    """
    天气系统
    
    处理天气对战斗的影响。
    """
    
    def __init__(self, config_manager: "ConfigManager"):
        """
        初始化天气系统
        
        Args:
            config_manager: 配置管理器
        """
        self.config = config_manager
    
    def apply_weather_damage(self, battle: "BattleState") -> List[str]:
        """
        应用天气伤害
        
        Args:
            battle: 战斗状态
            
        Returns:
            消息列表
        """
        messages = []
        weather_config = self.config.get_item("weathers", battle.weather)

        if not weather_config:
            return messages

        dot_damage_percent = weather_config.get("dot_damage", 0)
        if dot_damage_percent <= 0:
            return messages

        immune_types = weather_config.get("dot_immune_types", [])
        weather_name = weather_config.get("name", battle.weather)

        for monster, name_prefix in [
            (battle.player_monster, ""),
            (battle.enemy_monster, "野生 " if battle.enemy_is_wild else "")
        ]:
            if not monster or monster.get("current_hp", 0) <= 0:
                continue

            monster_types = monster.get("types", [])
            is_immune = any(t in immune_types for t in monster_types)

            if not is_immune:
                damage = max(1, int(monster["max_hp"] * dot_damage_percent / 100))
                monster["current_hp"] = max(0, monster["current_hp"] - damage)
                monster_name = monster.get("nickname") or monster.get("name", "???")
                messages.append(f"{name_prefix}{monster_name} 受到了{weather_name}的伤害！(-{damage})")

        return messages
    
    def process_weather_turn(self, battle: "BattleState") -> List[str]:
        """
        处理天气回合衰减
        
        Args:
            battle: 战斗状态
            
        Returns:
            消息列表
        """
        messages = []
        
        if battle.weather_turns > 0:
            battle.weather_turns -= 1
            if battle.weather_turns <= 0:
                messages.append("天气恢复正常了。")
                battle.weather = "clear"
                
        return messages
    
    def get_weather_display(self, battle: "BattleState") -> str:
        """
        获取天气显示文本
        
        Args:
            battle: 战斗状态
            
        Returns:
            天气显示文本，如果是晴天则返回空字符串
        """
        if battle.weather == "clear":
            return ""
            
        weather_config = self.config.get_item("weathers", battle.weather)
        if not weather_config:
            return ""
            
        weather_icon = weather_config.get("icon", "")
        weather_name = weather_config.get("name", battle.weather)
        return f"{weather_icon} {weather_name}\n"
