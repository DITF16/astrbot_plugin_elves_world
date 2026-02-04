"""
状态效果处理器

负责处理回合结束时的状态效果，包括：
- 状态伤害（烧伤、中毒）
- 回复效果
- 护盾衰减
- Buff/Debuff衰减
"""

from typing import Dict, List, TYPE_CHECKING

from .constants import (
    BURN_DAMAGE_FRACTION,
    POISON_DAMAGE_FRACTION,
    STAT_NAMES_CN,
    MODIFIABLE_STATS,
)

if TYPE_CHECKING:
    from .models import BattleState


class StatusHandler:
    """
    状态效果处理器
    
    处理回合结束时的各种持续效果。
    """
    
    def apply_status_damage(self, battle: "BattleState") -> List[str]:
        """
        应用状态伤害（烧伤、中毒）
        
        Args:
            battle: 战斗状态
            
        Returns:
            消息列表
        """
        messages = []

        for monster, name_prefix in [
            (battle.player_monster, ""),
            (battle.enemy_monster, "野生 " if battle.enemy_is_wild else "")
        ]:
            if not monster or monster.get("current_hp", 0) <= 0:
                continue

            status = monster.get("status")
            if not status:
                continue

            monster_name = monster.get("nickname") or monster.get("name", "???")
            full_name = f"{name_prefix}{monster_name}"

            if status == "burn":
                damage = max(1, monster["max_hp"] // BURN_DAMAGE_FRACTION)
                monster["current_hp"] = max(0, monster["current_hp"] - damage)
                messages.append(f"{full_name} 被烧伤折磨！(-{damage})")

            elif status == "poison":
                damage = max(1, monster["max_hp"] // POISON_DAMAGE_FRACTION)
                monster["current_hp"] = max(0, monster["current_hp"] - damage)
                messages.append(f"{full_name} 受到毒素侵蚀！(-{damage})")

        return messages
    
    def apply_regen_effects(self, battle: "BattleState") -> List[str]:
        """
        应用回复效果、护盾衰减、混乱等持续效果
        
        Args:
            battle: 战斗状态
            
        Returns:
            消息列表
        """
        messages = []

        for monster in [battle.player_monster, battle.enemy_monster]:
            if not monster or monster.get("current_hp", 0) <= 0:
                continue

            monster_name = monster.get("nickname") or monster.get("name", "???")

            # 回复效果
            regen_msgs = self._process_regen(monster, monster_name)
            messages.extend(regen_msgs)

            # 护盾衰减
            shield_msgs = self._process_shield_decay(monster, monster_name)
            messages.extend(shield_msgs)

            # 混乱效果衰减
            confuse_msgs = self._process_confuse_decay(monster, monster_name)
            messages.extend(confuse_msgs)

            # Buff/Debuff 衰减
            buff_msgs = self._process_buff_decay(monster, monster_name)
            messages.extend(buff_msgs)

        return messages
    
    def _process_regen(self, monster: Dict, monster_name: str) -> List[str]:
        """处理回复效果"""
        messages = []
        
        regen_percent = monster.get("_regen", 0)
        regen_turns = monster.get("_regen_turns", 0)
        
        if regen_percent > 0 and regen_turns > 0:
            heal = max(1, int(monster["max_hp"] * regen_percent / 100))
            old_hp = monster["current_hp"]
            monster["current_hp"] = min(monster["max_hp"], old_hp + heal)
            actual_heal = monster["current_hp"] - old_hp

            if actual_heal > 0:
                messages.append(f"{monster_name} 恢复了 {actual_heal} HP！")

            # 递减回合数
            monster["_regen_turns"] = regen_turns - 1
            if monster["_regen_turns"] <= 0:
                monster["_regen"] = 0
                messages.append(f"{monster_name} 的回复效果消失了。")
                
        return messages
    
    def _process_shield_decay(self, monster: Dict, monster_name: str) -> List[str]:
        """处理护盾衰减"""
        messages = []
        
        shield_turns = monster.get("_shield_turns", 0)
        if shield_turns > 0:
            monster["_shield_turns"] = shield_turns - 1
            if monster["_shield_turns"] <= 0:
                shield_left = monster.get("_shield", 0)
                monster["_shield"] = 0
                if shield_left > 0:
                    messages.append(f"{monster_name} 的护盾消失了。")
                    
        return messages
    
    def _process_confuse_decay(self, monster: Dict, monster_name: str) -> List[str]:
        """处理混乱效果衰减"""
        messages = []
        
        confused_turns = monster.get("_confused_turns", 0)
        if confused_turns > 0:
            monster["_confused_turns"] = confused_turns - 1
            if monster["_confused_turns"] <= 0:
                monster["_confused"] = False
                messages.append(f"{monster_name} 恢复了理智！")
                
        return messages
    
    def _process_buff_decay(self, monster: Dict, monster_name: str) -> List[str]:
        """处理Buff/Debuff衰减"""
        messages = []
        
        # Buff 衰减
        for stat in MODIFIABLE_STATS:
            buff_turns_key = f"_buff_{stat}_turns"
            buff_key = f"_buff_{stat}"
            buff_turns = monster.get(buff_turns_key, 0)
            
            if buff_turns > 0:
                monster[buff_turns_key] = buff_turns - 1
                if monster[buff_turns_key] <= 0:
                    if monster.get(buff_key, 0) > 0:
                        monster[buff_key] = 0
                        messages.append(
                            f"{monster_name} 的{STAT_NAMES_CN.get(stat, stat)}提升效果消失了。"
                        )
        
        # Debuff 衰减
        for stat in MODIFIABLE_STATS:
            debuff_turns_key = f"_debuff_{stat}_turns"
            debuff_key = f"_debuff_{stat}"
            debuff_turns = monster.get(debuff_turns_key, 0)
            
            if debuff_turns > 0:
                monster[debuff_turns_key] = debuff_turns - 1
                if monster[debuff_turns_key] <= 0:
                    if monster.get(debuff_key, 0) > 0:
                        monster[debuff_key] = 0
                        messages.append(
                            f"{monster_name} 的{STAT_NAMES_CN.get(stat, stat)}降低效果消失了。"
                        )

        return messages
