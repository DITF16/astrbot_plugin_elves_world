"""
伤害计算器

负责所有伤害相关的计算，包括：
- 技能伤害计算
- 属性克制
- 暴击判定
- 天气修正
"""

import random
from typing import Dict, TYPE_CHECKING

from .constants import (
    STAT_STAGE_MULTIPLIERS,
    ACCURACY_STAGE_MULTIPLIERS,
    BASE_CRITICAL_RATE,
    HIGH_CRITICAL_RATE,
    MAX_CRITICAL_RATE,
    BURN_ATTACK_REDUCTION,
    MIN_STAT_VALUE,
)

if TYPE_CHECKING:
    from .models import BattleState
    from ..config_manager import ConfigManager


class DamageCalculator:
    """
    伤害计算器
    
    纯计算类，不修改任何状态，只负责数值计算。
    """
    
    def __init__(self, config_manager: "ConfigManager"):
        """
        初始化伤害计算器
        
        Args:
            config_manager: 配置管理器，用于获取属性克制表等
        """
        self.config = config_manager
    
    def calculate_skill_damage(
        self,
        battle: "BattleState",
        attacker: Dict,
        defender: Dict,
        skill: Dict,
        is_player: bool
    ) -> Dict:
        """
        计算技能伤害
        
        Args:
            battle: 战斗状态
            attacker: 攻击方精灵数据
            defender: 防御方精灵数据
            skill: 技能数据
            is_player: 攻击方是否为玩家
            
        Returns:
            包含 damage, is_critical, effectiveness 的字典
        """
        from ..formulas import GameFormulas
        
        category = skill.get("category", "physical")
        power = skill.get("power", 0)
        skill_type = skill.get("type", "normal")

        # 选择攻击/防御属性
        if category == "physical":
            attack_stat = self.get_effective_stat(battle, is_player, "attack")
            defense_stat = self.get_effective_stat(battle, not is_player, "defense")
        else:
            attack_stat = self.get_effective_stat(battle, is_player, "sp_attack")
            defense_stat = self.get_effective_stat(battle, not is_player, "sp_defense")

        # 灼伤降低物理攻击
        if category == "physical" and attacker.get("status") == "burn":
            attack_stat = int(attack_stat * BURN_ATTACK_REDUCTION)

        # 属性克制
        defender_types = defender.get("types", ["normal"])
        type_chart = self.config.types
        effectiveness = GameFormulas.get_type_effectiveness(
            skill_type, defender_types, type_chart
        )

        # 天气修正
        weather_mod = self.get_weather_modifier(battle.weather, skill_type)

        # 暴击判定
        is_critical = self._check_critical(skill, attacker)

        # STAB（属性一致加成）
        attacker_types = attacker.get("types", [])
        is_stab = skill_type in attacker_types

        # 计算伤害
        damage, _ = GameFormulas.calculate_damage(
            attacker_level=attacker.get("level", 1),
            attack_stat=attack_stat,
            defense_stat=defense_stat,
            skill_power=power,
            type_effectiveness=effectiveness,
            weather_mod=weather_mod,
            is_critical=is_critical,
            is_stab=is_stab,
            random_factor=True
        )

        return {
            "damage": damage,
            "is_critical": is_critical,
            "effectiveness": effectiveness
        }
    
    def _check_critical(self, skill: Dict, attacker: Dict) -> bool:
        """
        检查是否暴击
        
        Args:
            skill: 技能数据
            attacker: 攻击方精灵数据
            
        Returns:
            是否暴击
        """
        crit_chance = BASE_CRITICAL_RATE
        
        # 高暴击技能
        crit_effects = [e for e in skill.get("effects", []) if e.get("type") == "crit_up"]
        if crit_effects:
            crit_chance = HIGH_CRITICAL_RATE
            
        # 应用暴击 buff
        crit_buff = attacker.get("_buff_critical", 0)
        if crit_buff > 0:
            crit_chance = min(MAX_CRITICAL_RATE, crit_chance + crit_buff / 100)
            
        return random.random() < crit_chance
    
    def get_effective_stat(
        self,
        battle: "BattleState",
        is_player: bool,
        stat_name: str
    ) -> int:
        """
        获取经过能力等级修正后的属性值
        
        Args:
            battle: 战斗状态
            is_player: 是否为玩家方
            stat_name: 属性名称
            
        Returns:
            修正后的属性值
        """
        monster = battle.player_monster if is_player else battle.enemy_monster
        if not monster:
            return 0

        base_value = monster.get("stats", {}).get(stat_name, 0)
        stat_stages = battle.player_stat_stages if is_player else battle.enemy_stat_stages
        stage = stat_stages.get(stat_name, 0)

        # 选择修正表
        if stat_name in ["accuracy", "evasion"]:
            multiplier = ACCURACY_STAGE_MULTIPLIERS.get(stage, 1)
        else:
            multiplier = STAT_STAGE_MULTIPLIERS.get(stage, 1)

        effective_value = int(base_value * multiplier)
        
        # 应用技能效果产生的 buff/debuff
        buff_percent = monster.get(f"_buff_{stat_name}", 0)
        debuff_percent = monster.get(f"_debuff_{stat_name}", 0)
        
        if buff_percent > 0:
            effective_value = int(effective_value * (1 + buff_percent / 100))
        if debuff_percent > 0:
            effective_value = int(effective_value * (1 - debuff_percent / 100))
        
        return max(MIN_STAT_VALUE, effective_value)
    
    def check_hit(
        self,
        battle: "BattleState",
        is_player: bool,
        base_accuracy: int
    ) -> bool:
        """
        检查技能是否命中
        
        Args:
            battle: 战斗状态
            is_player: 攻击方是否为玩家
            base_accuracy: 技能基础命中率
            
        Returns:
            是否命中
        """
        if base_accuracy >= 100:
            return True

        # 获取能力等级
        attacker_stages = battle.player_stat_stages if is_player else battle.enemy_stat_stages
        defender_stages = battle.enemy_stat_stages if is_player else battle.player_stat_stages

        acc_stage = attacker_stages.get("accuracy", 0)
        eva_stage = defender_stages.get("evasion", 0)

        acc_mult = ACCURACY_STAGE_MULTIPLIERS.get(acc_stage, 1)
        eva_mult = ACCURACY_STAGE_MULTIPLIERS.get(eva_stage, 1)

        # 获取精灵对象以读取 buff/debuff
        attacker = battle.player_monster if is_player else battle.enemy_monster
        defender = battle.enemy_monster if is_player else battle.player_monster
        
        # 应用命中/闪避 buff/debuff
        acc_buff = attacker.get("_buff_accuracy", 0) if attacker else 0
        acc_debuff = attacker.get("_debuff_accuracy", 0) if attacker else 0
        eva_buff = defender.get("_buff_evasion", 0) if defender else 0
        eva_debuff = defender.get("_debuff_evasion", 0) if defender else 0
        
        # 计算最终修正
        acc_final_mult = acc_mult * (1 + acc_buff/100) * (1 - acc_debuff/100)
        eva_final_mult = eva_mult * (1 + eva_buff/100) * (1 - eva_debuff/100)
        
        final_accuracy = base_accuracy * acc_final_mult / max(0.01, eva_final_mult)

        return random.random() * 100 < final_accuracy
    
    def get_weather_modifier(self, weather: str, skill_type: str) -> float:
        """
        获取天气对技能的修正
        
        Args:
            weather: 当前天气
            skill_type: 技能属性
            
        Returns:
            伤害修正倍率
        """
        weather_config = self.config.get_item("weathers", weather)
        if not weather_config:
            return 1.0

        effects = weather_config.get("effects", {})
        type_effects = effects.get(skill_type, {})

        return type_effects.get("power_mod", 1.0)
