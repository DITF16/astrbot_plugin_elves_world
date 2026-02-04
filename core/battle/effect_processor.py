"""
技能效果处理器

负责处理技能的附加效果，包括：
- 状态效果（烧伤、麻痹、中毒等）
- 能力变化（攻击提升、防御降低等）
- 治疗效果
- 护盾效果
- Buff/Debuff效果
"""

import random
from typing import Dict, List, TYPE_CHECKING

from .constants import (
    STAT_STAGE_MIN,
    STAT_STAGE_MAX,
    STAT_NAMES_CN,
    STATUS_NAMES_CN,
    STATUS_IMMUNITY,
    DEFAULT_REGEN_DURATION,
    DEFAULT_SHIELD_DURATION,
    DEFAULT_CONFUSE_DURATION,
    DEFAULT_BUFF_DURATION,
)

if TYPE_CHECKING:
    from .models import BattleState


class EffectProcessor:
    """
    技能效果处理器
    
    处理技能的所有附加效果。
    """
    
    def process_skill_effects(
        self,
        battle: "BattleState",
        attacker: Dict,
        defender: Dict,
        effects: List[Dict],
        is_player: bool
    ) -> List[str]:
        """
        处理技能附加效果
        
        Args:
            battle: 战斗状态
            attacker: 攻击方精灵
            defender: 防御方精灵
            effects: 效果列表
            is_player: 攻击方是否为玩家
            
        Returns:
            效果消息列表
        """
        messages = []
        attacker_name = attacker.get("nickname") or attacker.get("name", "???")
        defender_name = defender.get("nickname") or defender.get("name", "???")

        for effect in effects:
            effect_type = effect.get("type", "")
            chance = effect.get("chance", 100)
            value = effect.get("value", 0)

            # 概率判定
            if random.random() * 100 > chance:
                continue

            # 根据效果类型分发处理
            effect_messages = self._process_single_effect(
                battle, attacker, defender, effect_type, value, effect,
                is_player, attacker_name, defender_name
            )
            messages.extend(effect_messages)

        return messages
    
    def _process_single_effect(
        self,
        battle: "BattleState",
        attacker: Dict,
        defender: Dict,
        effect_type: str,
        value: int,
        effect: Dict,
        is_player: bool,
        attacker_name: str,
        defender_name: str
    ) -> List[str]:
        """处理单个效果"""
        messages = []
        
        # 状态效果
        if effect_type in STATUS_NAMES_CN:
            msg = self._apply_status_effect(defender, effect_type, defender_name)
            if msg:
                messages.append(msg)
                
        # 能力等级变化
        elif effect_type.endswith("_up") or effect_type.endswith("_down"):
            msg = self._apply_stat_stage_change(
                battle, attacker, defender, effect_type, value, effect,
                is_player, attacker_name, defender_name
            )
            if msg:
                messages.append(msg)
                
        # 治疗效果
        elif effect_type == "heal":
            msg = self._apply_heal(attacker, value, attacker_name)
            if msg:
                messages.append(msg)
                
        # 回复状态
        elif effect_type == "regen":
            msg = self._apply_regen(attacker, value, effect, attacker_name)
            if msg:
                messages.append(msg)
                
        # 护盾效果
        elif effect_type == "shield":
            msg = self._apply_shield(attacker, value, effect, attacker_name)
            if msg:
                messages.append(msg)
                
        # 吸血效果
        elif effect_type == "drain":
            attacker["_drain_percent"] = value
            messages.append(f"{attacker_name} 的攻击将吸取生命！")
            
        # 百分比Buff效果
        elif effect_type in [
            "attack_up", "defense_up", "sp_attack_up", "sp_defense_up",
            "speed_up", "accuracy_up", "evasion_up", "critical_up"
        ]:
            msg = self._apply_percent_buff(attacker, effect_type, value, effect, attacker_name)
            if msg:
                messages.append(msg)
                
        # 百分比Debuff效果
        elif effect_type in [
            "attack_down", "defense_down", "sp_attack_down", "sp_defense_down",
            "speed_down", "accuracy_down", "evasion_down"
        ]:
            msg = self._apply_percent_debuff(defender, effect_type, value, effect, defender_name)
            if msg:
                messages.append(msg)
                
        # 混乱效果
        elif effect_type == "confuse":
            msg = self._apply_confuse(defender, effect, defender_name)
            if msg:
                messages.append(msg)

        return messages
    
    def _apply_status_effect(
        self,
        defender: Dict,
        status: str,
        defender_name: str
    ) -> str:
        """应用状态效果"""
        if defender["current_hp"] <= 0 or defender.get("status"):
            return ""
            
        # 属性免疫检查
        defender_types = defender.get("types", [])
        immune_type = STATUS_IMMUNITY.get(status)
        
        if immune_type and immune_type in defender_types:
            return ""
            
        defender["status"] = status
        return f"{defender_name} 陷入了{STATUS_NAMES_CN[status]}状态！"
    
    def _apply_stat_stage_change(
        self,
        battle: "BattleState",
        attacker: Dict,
        defender: Dict,
        effect_type: str,
        value: int,
        effect: Dict,
        is_player: bool,
        attacker_name: str,
        defender_name: str
    ) -> str:
        """应用能力等级变化"""
        is_up = effect_type.endswith("_up")
        stat_name = effect_type.replace("_up", "").replace("_down", "")
        
        stages = value if value else (1 if is_up else -1)
        target_is_self = effect.get("target", "enemy") == "self"
        
        if target_is_self:
            target_name = attacker_name
            stat_stages = battle.player_stat_stages if is_player else battle.enemy_stat_stages
        else:
            target_name = defender_name
            stat_stages = battle.enemy_stat_stages if is_player else battle.player_stat_stages
        
        if stat_name not in stat_stages:
            return ""
            
        old_stage = stat_stages[stat_name]
        new_stage = max(STAT_STAGE_MIN, min(STAT_STAGE_MAX, old_stage + stages))
        stat_stages[stat_name] = new_stage
        
        if new_stage != old_stage:
            change_text = "提高了" if is_up else "降低了"
            return f"{target_name} 的{STAT_NAMES_CN.get(stat_name, stat_name)}{change_text}！"
        
        return ""
    
    def _apply_heal(self, attacker: Dict, value: int, attacker_name: str) -> str:
        """应用治疗效果"""
        heal_amount = int(attacker.get("max_hp", 100) * value / 100)
        old_hp = attacker["current_hp"]
        attacker["current_hp"] = min(attacker["max_hp"], old_hp + heal_amount)
        actual_heal = attacker["current_hp"] - old_hp
        
        if actual_heal > 0:
            return f"{attacker_name} 恢复了 {actual_heal} HP！"
        return ""
    
    def _apply_regen(
        self,
        attacker: Dict,
        value: int,
        effect: Dict,
        attacker_name: str
    ) -> str:
        """应用回复状态"""
        duration = effect.get("duration", DEFAULT_REGEN_DURATION)
        attacker["_regen"] = value
        attacker["_regen_turns"] = duration
        return f"{attacker_name} 被治愈之力包围！（持续{duration}回合）"
    
    def _apply_shield(
        self,
        attacker: Dict,
        value: int,
        effect: Dict,
        attacker_name: str
    ) -> str:
        """应用护盾效果"""
        duration = effect.get("duration", DEFAULT_SHIELD_DURATION)
        shield_amount = int(attacker.get("max_hp", 100) * value / 100)
        attacker["_shield"] = attacker.get("_shield", 0) + shield_amount
        attacker["_shield_turns"] = duration
        return f"{attacker_name} 获得了 {shield_amount} 点护盾！（持续{duration}回合）"
    
    def _apply_percent_buff(
        self,
        attacker: Dict,
        effect_type: str,
        value: int,
        effect: Dict,
        attacker_name: str
    ) -> str:
        """应用百分比Buff"""
        stat_name = effect_type.replace("_up", "")
        duration = effect.get("duration", DEFAULT_BUFF_DURATION)
        
        buff_key = f"_buff_{stat_name}"
        buff_turns_key = f"_buff_{stat_name}_turns"
        
        attacker[buff_key] = attacker.get(buff_key, 0) + value
        attacker[buff_turns_key] = max(attacker.get(buff_turns_key, 0), duration)
        
        return f"{attacker_name} 的{STAT_NAMES_CN.get(stat_name, stat_name)}提升了{value}%！（持续{duration}回合）"
    
    def _apply_percent_debuff(
        self,
        defender: Dict,
        effect_type: str,
        value: int,
        effect: Dict,
        defender_name: str
    ) -> str:
        """应用百分比Debuff"""
        stat_name = effect_type.replace("_down", "")
        duration = effect.get("duration", DEFAULT_BUFF_DURATION)
        
        debuff_key = f"_debuff_{stat_name}"
        debuff_turns_key = f"_debuff_{stat_name}_turns"
        
        defender[debuff_key] = defender.get(debuff_key, 0) + value
        defender[debuff_turns_key] = max(defender.get(debuff_turns_key, 0), duration)
        
        return f"{defender_name} 的{STAT_NAMES_CN.get(stat_name, stat_name)}降低了{value}%！（持续{duration}回合）"
    
    def _apply_confuse(
        self,
        defender: Dict,
        effect: Dict,
        defender_name: str
    ) -> str:
        """应用混乱效果"""
        if defender["current_hp"] <= 0 or defender.get("_confused"):
            return ""
            
        duration = effect.get("duration", DEFAULT_CONFUSE_DURATION)
        defender["_confused"] = True
        defender["_confused_turns"] = duration
        return f"{defender_name} 陷入了混乱！（持续{duration}回合）"
