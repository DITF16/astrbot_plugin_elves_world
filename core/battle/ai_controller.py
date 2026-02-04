"""
AI控制器

负责敌方AI的行动决策，包括：
- 普通野怪AI（随机选择）
- BOSS AI（智能选择克制技能）
"""

import random
from typing import List, TYPE_CHECKING

from .models import ActionType, BattleAction, BattleType

if TYPE_CHECKING:
    from .models import BattleState
    from ..config_manager import ConfigManager


class AIController:
    """
    AI控制器
    
    负责生成敌方的行动决策。
    """
    
    def __init__(self, config_manager: "ConfigManager"):
        """
        初始化AI控制器
        
        Args:
            config_manager: 配置管理器
        """
        self.config = config_manager
    
    def generate_enemy_action(self, battle: "BattleState") -> BattleAction:
        """
        生成敌方AI行动
        
        Args:
            battle: 战斗状态
            
        Returns:
            敌方行动
        """
        enemy_monster = battle.enemy_monster

        if not enemy_monster:
            return BattleAction(action_type=ActionType.SKILL, actor_id="")

        # 获取可用技能
        skills = enemy_monster.get("skills", [])
        if not skills:
            skills = ["struggle"]  # 默认挣扎

        # AI策略：BOSS更智能
        if battle.battle_type == BattleType.BOSS:
            skill_id = self._boss_ai_select_skill(battle, skills)
        else:
            # 普通AI：随机选择
            skill_id = random.choice(skills)

        return BattleAction(
            action_type=ActionType.SKILL,
            actor_id=enemy_monster.get("instance_id", ""),
            target_id=battle.player_monster.get("instance_id", "") if battle.player_monster else "",
            skill_id=skill_id
        )
    
    def _boss_ai_select_skill(self, battle: "BattleState", skills: List[str]) -> str:
        """
        BOSS AI技能选择
        
        优先选择对玩家精灵克制的技能。
        
        Args:
            battle: 战斗状态
            skills: 可用技能列表
            
        Returns:
            选择的技能ID
        """
        from ..formulas import GameFormulas
        
        player_monster = battle.player_monster
        if not player_monster:
            return random.choice(skills)

        player_types = player_monster.get("types", [])
        type_chart = self.config.types

        # 优先选择克制技能
        best_skill = None
        best_score = 0

        for skill_id in skills:
            skill = self.config.get_item("skills", skill_id)
            if not skill:
                continue

            skill_type = skill.get("type", "normal")
            effectiveness = GameFormulas.get_type_effectiveness(
                skill_type, player_types, type_chart
            )

            power = skill.get("power", 0)
            score = effectiveness * power

            if score > best_score:
                best_score = score
                best_skill = skill_id

        return best_skill if best_skill else random.choice(skills)
