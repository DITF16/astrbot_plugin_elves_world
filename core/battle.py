"""
战斗系统
- 回合制战斗逻辑
- 伤害计算与属性克制
- 状态效果处理
- 天气影响
- AI行动选择
"""

import random
from enum import Enum
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field

from .formulas import GameFormulas

if TYPE_CHECKING:
    from .config_manager import ConfigManager
    from .monster import MonsterInstance


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
    """战斗行动"""
    action_type: ActionType
    actor_id: str           # 行动者精灵instance_id
    target_id: str = ""     # 目标精灵instance_id
    skill_id: str = ""      # 技能ID（如果是技能行动）
    item_id: str = ""       # 道具ID（如果是道具行动）
    switch_to_id: str = ""  # 换上的精灵ID（如果是换精灵）
    priority: int = 0       # 优先级（先制技能等）


@dataclass
class BattleResult:
    """单次行动结果"""
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
    """回合结果"""
    turn_number: int
    weather: str = "clear"
    actions: List[Dict] = field(default_factory=list)  # 行动记录
    messages: List[str] = field(default_factory=list)  # 战斗消息
    player_monster_fainted: bool = False
    enemy_monster_fainted: bool = False
    battle_ended: bool = False
    winner: str = ""  # "player" / "enemy" / "flee" / ""


@dataclass
class BattleState:
    """
    战斗状态
    保存整场战斗的状态信息
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


class BattleSystem:
    """
    战斗系统

    处理回合制战斗的所有逻辑
    """

    # 能力等级修正表 (-6 ~ +6)
    STAT_STAGE_MULTIPLIERS = {
        -6: 2/8, -5: 2/7, -4: 2/6, -3: 2/5, -2: 2/4, -1: 2/3,
        0: 1,
        1: 3/2, 2: 4/2, 3: 5/2, 4: 6/2, 5: 7/2, 6: 8/2
    }

    # 命中/闪避等级修正表
    ACCURACY_STAGE_MULTIPLIERS = {
        -6: 3/9, -5: 3/8, -4: 3/7, -3: 3/6, -2: 3/5, -1: 3/4,
        0: 1,
        1: 4/3, 2: 5/3, 3: 6/3, 4: 7/3, 5: 8/3, 6: 9/3
    }

    def __init__(self, config_manager: "ConfigManager"):
        """
        初始化战斗系统

        Args:
            config_manager: 配置管理器
        """
        self.config = config_manager

    # ==================== 战斗创建 ====================

    def create_wild_battle(self,
                           player_id: str,
                           player_team: List[Dict],
                           wild_monster: Dict,
                           weather: str = "clear") -> BattleState:
        """
        创建野外战斗

        Args:
            player_id: 玩家ID
            player_team: 玩家队伍
            wild_monster: 野生精灵数据
            weather: 天气
        """
        import uuid

        return BattleState(
            battle_id=str(uuid.uuid4())[:8],
            battle_type=BattleType.WILD,
            player_id=player_id,
            player_team=player_team,
            player_active_index=0,
            enemy_team=[wild_monster],
            enemy_active_index=0,
            enemy_is_wild=True,
            weather=weather,
            can_flee=True,
            can_catch=True,
        )

    def create_boss_battle(self,
                           player_id: str,
                           player_team: List[Dict],
                           boss_id: str,
                           weather: str = "clear") -> Optional[BattleState]:
        """
        创建BOSS战斗

        Args:
            player_id: 玩家ID
            player_team: 玩家队伍
            boss_id: BOSS ID
            weather: 天气
        """
        import uuid
        from .monster import MonsterInstance

        boss_config = self.config.get_item("bosses", boss_id)
        if not boss_config:
            return None

        # 从BOSS配置生成精灵
        # 支持两种方式：1. 使用 monster_template_id 引用现有精灵模板
        #              2. 直接使用 boss 配置中的 base_stats/types 创建
        template_id = boss_config.get("monster_template_id")
        
        if template_id:
            # 方式1：基于精灵模板
            monster_template = self.config.get_item("monsters", template_id)
            if not monster_template:
                return None
        else:
            # 方式2：直接使用 boss 配置作为模板
            # Boss 配置中需要有 base_stats, types, skills 等字段
            if not boss_config.get("base_stats"):
                return None
            monster_template = {
                "id": boss_id,
                "name": boss_config.get("name", boss_id),
                "types": boss_config.get("types", ["normal"]),
                "base_stats": boss_config.get("base_stats"),
                "skills": boss_config.get("skills", []),
                "evolution": None,
                "description": boss_config.get("description", "")
            }

        # 创建BOSS精灵实例
        boss_level = boss_config.get("level", 30)
        boss_nature = boss_config.get("fixed_nature", "hardy")

        boss_monster = MonsterInstance.from_template(
            template=monster_template,
            level=boss_level,
            config_manager=self.config,
            nature_id=boss_nature,
        )

        # 应用BOSS属性倍率
        stat_multipliers = boss_config.get("stat_multipliers", {})
        boss_data = boss_monster.to_dict()

        for stat, multiplier in stat_multipliers.items():
            if stat in boss_data["stats"]:
                boss_data["stats"][stat] = int(boss_data["stats"][stat] * multiplier)

        # HP特殊处理
        hp_mult = stat_multipliers.get("hp", 1.0)
        boss_data["max_hp"] = int(boss_data["max_hp"] * hp_mult)
        boss_data["current_hp"] = boss_data["max_hp"]

        # 覆盖技能
        override_skills = boss_config.get("override_skills")
        if override_skills:
            boss_data["skills"] = override_skills[:4]

        # BOSS名称
        boss_data["name"] = boss_config.get("name", boss_data["name"])

        # 强制天气
        forced_weather = weather
        special_ability = boss_config.get("special_ability", "")
        if "eternal_winter" in special_ability:
            forced_weather = "hail"
        elif "eternal_sun" in special_ability:
            forced_weather = "sunny"

        return BattleState(
            battle_id=str(uuid.uuid4())[:8],
            battle_type=BattleType.BOSS,
            player_id=player_id,
            player_team=player_team,
            player_active_index=0,
            enemy_team=[boss_data],
            enemy_active_index=0,
            enemy_is_wild=False,
            boss_id=boss_id,
            boss_config=boss_config,
            weather=forced_weather,
            weather_turns=0,  # BOSS天气永久
            can_flee=False,
            can_catch=False,
        )

    # ==================== 回合处理 ====================

    def process_turn(self,
                     battle: BattleState,
                     player_action: BattleAction) -> TurnResult:
        """
        处理一个完整回合

        Args:
            battle: 战斗状态
            player_action: 玩家行动

        Returns:
            回合结果
        """
        battle.turn_count += 1
        result = TurnResult(turn_number=battle.turn_count, weather=battle.weather)

        # 1. 检查逃跑
        if player_action.action_type == ActionType.FLEE:
            flee_result = self._process_flee(battle)
            result.messages.append(flee_result["message"])
            if flee_result["success"]:
                result.battle_ended = True
                result.winner = "flee"
                battle.is_active = False
            return result

        # 2. 检查捕捉
        if player_action.action_type == ActionType.CATCH:
            catch_result = self._process_catch(battle)
            result.messages.append(catch_result["message"])
            if catch_result["success"]:
                result.battle_ended = True
                result.winner = "player"
                battle.is_active = False
            return result

        # 3. 生成敌方行动
        enemy_action = self._generate_enemy_action(battle)

        # 4. 决定行动顺序
        first_action, second_action, first_is_player = self._determine_action_order(
            battle, player_action, enemy_action
        )

        # 5. 执行第一个行动
        first_result = self._execute_action(battle, first_action, first_is_player)
        result.messages.extend(first_result.get("messages", []))
        result.actions.append(first_result)

        # 检查战斗是否结束
        if self._check_battle_end(battle, result):
            return result

        # 6. 执行第二个行动
        second_result = self._execute_action(battle, second_action, not first_is_player)
        result.messages.extend(second_result.get("messages", []))
        result.actions.append(second_result)

        # 检查战斗是否结束
        if self._check_battle_end(battle, result):
            return result

        # 7. 回合结束处理
        end_turn_messages = self._process_turn_end(battle)
        result.messages.extend(end_turn_messages)

        # 再次检查战斗是否结束
        self._check_battle_end(battle, result)

        return result

    def _determine_action_order(self,
                                 battle: BattleState,
                                 player_action: BattleAction,
                                 enemy_action: BattleAction) -> Tuple[BattleAction, BattleAction, bool]:
        """
        决定行动顺序

        Returns:
            (先手行动, 后手行动, 先手是否为玩家)
        """
        # 换精灵永远优先
        if player_action.action_type == ActionType.SWITCH:
            return (player_action, enemy_action, True)
        if enemy_action.action_type == ActionType.SWITCH:
            return (enemy_action, player_action, False)

        # 获取技能优先度
        player_priority = 0
        enemy_priority = 0

        if player_action.action_type == ActionType.SKILL:
            skill = self.config.get_item("skills", player_action.skill_id)
            if skill:
                player_priority = skill.get("priority", 0)

        if enemy_action.action_type == ActionType.SKILL:
            skill = self.config.get_item("skills", enemy_action.skill_id)
            if skill:
                enemy_priority = skill.get("priority", 0)

        # 优先度不同，高优先度先手
        if player_priority != enemy_priority:
            if player_priority > enemy_priority:
                return (player_action, enemy_action, True)
            else:
                return (enemy_action, player_action, False)

        # 优先度相同，比较速度
        player_speed = self._get_effective_stat(battle, True, "speed")
        enemy_speed = self._get_effective_stat(battle, False, "speed")

        # 麻痹减速
        player_monster = battle.player_monster
        enemy_monster = battle.enemy_monster

        if player_monster and player_monster.get("status") == "paralyze":
            player_speed = int(player_speed * 0.5)
        if enemy_monster and enemy_monster.get("status") == "paralyze":
            enemy_speed = int(enemy_speed * 0.5)

        # 速度相同随机
        if player_speed == enemy_speed:
            player_first = random.random() < 0.5
        else:
            player_first = player_speed > enemy_speed

        if player_first:
            return (player_action, enemy_action, True)
        else:
            return (enemy_action, player_action, False)

    def _execute_action(self,
                        battle: BattleState,
                        action: BattleAction,
                        is_player: bool) -> Dict:
        """执行一个行动"""
        result = {"success": True, "messages": []}

        if action.action_type == ActionType.SKILL:
            result = self._execute_skill(battle, action, is_player)
        elif action.action_type == ActionType.SWITCH:
            result = self._execute_switch(battle, action, is_player)
        elif action.action_type == ActionType.ITEM:
            result = self._execute_item(battle, action, is_player)

        return result

    def _execute_skill(self,
                       battle: BattleState,
                       action: BattleAction,
                       is_player: bool) -> Dict:
        """执行技能"""
        result = {"success": True, "messages": [], "damage": 0}

        attacker = battle.player_monster if is_player else battle.enemy_monster
        defender = battle.enemy_monster if is_player else battle.player_monster

        if not attacker or not defender:
            result["success"] = False
            return result

        attacker_name = attacker.get("nickname") or attacker.get("name", "???")
        defender_name = defender.get("nickname") or defender.get("name", "???")

        # 检查状态是否允许行动
        status = attacker.get("status")
        if status in ["sleep", "freeze"]:
            # 尝试解除
            wake_chance = 0.33 if status == "sleep" else 0.20
            if random.random() < wake_chance:
                attacker["status"] = None
                status_name = "醒来了" if status == "sleep" else "解冻了"
                result["messages"].append(f"{attacker_name} {status_name}！")
            else:
                status_msg = "正在睡觉" if status == "sleep" else "被冻住了"
                result["messages"].append(f"{attacker_name} {status_msg}，无法行动！")
                return result

        if status == "paralyze":
            if random.random() < 0.25:
                result["messages"].append(f"{attacker_name} 麻痹了，无法行动！")
                return result

        # 获取技能数据
        skill = self.config.get_item("skills", action.skill_id)
        if not skill:
            result["success"] = False
            result["messages"].append("技能不存在！")
            return result

        skill_name = skill.get("name", action.skill_id)
        result["messages"].append(f"{attacker_name} 使用了 {skill_name}！")

        # 命中判定
        accuracy = skill.get("accuracy", 100)
        if not self._check_hit(battle, is_player, accuracy):
            result["messages"].append("但是没有命中！")
            result["is_missed"] = True
            return result

        # 计算伤害（如果是攻击技能）
        power = skill.get("power", 0)
        category = skill.get("category", "physical")

        if power > 0 and category in ["physical", "special"]:
            damage_result = self._calculate_skill_damage(
                battle, attacker, defender, skill, is_player
            )

            damage = damage_result["damage"]
            result["damage"] = damage
            result["is_critical"] = damage_result["is_critical"]
            result["effectiveness"] = damage_result["effectiveness"]


            # 护盾吸收伤害
            shield = defender.get("_shield", 0)
            absorbed_damage = 0
            if shield > 0:
                absorbed_damage = min(shield, damage)
                defender["_shield"] = shield - absorbed_damage
                damage = damage - absorbed_damage
                if absorbed_damage > 0:
                    result["messages"].append(f"护盾吸收了 {absorbed_damage} 点伤害！")
                if defender["_shield"] <= 0:
                    defender["_shield"] = 0
                    defender["_shield_turns"] = 0
                    result["messages"].append(f"{defender_name} 的护盾被击碎了！")

            # 应用伤害
            defender["current_hp"] = max(0, defender["current_hp"] - damage)

            # 伤害消息
            if damage_result["is_critical"]:
                result["messages"].append("击中要害！")

            if damage_result["effectiveness"] > 1:
                result["messages"].append("效果拔群！")
            elif damage_result["effectiveness"] < 1:
                result["messages"].append("效果不佳...")

            result["messages"].append(f"造成了 {damage} 点伤害！")

            # 吸血效果处理
            drain_percent = attacker.get("_drain_percent", 0)
            if drain_percent > 0 and damage > 0:
                drain_amount = int(damage * drain_percent / 100)
                if drain_amount > 0:
                    old_hp = attacker["current_hp"]
                    attacker["current_hp"] = min(attacker["max_hp"], old_hp + drain_amount)
                    actual_drain = attacker["current_hp"] - old_hp
                    if actual_drain > 0:
                        result["messages"].append(f"{attacker_name} 吸取了 {actual_drain} HP！")


            # 检查击倒
            if defender["current_hp"] <= 0:
                result["messages"].append(f"{defender_name} 倒下了！")
                result["target_fainted"] = True

        # 处理技能效果
        effects = skill.get("effects", [])
        effect_messages = self._process_skill_effects(
            battle, attacker, defender, effects, is_player
        )
        result["messages"].extend(effect_messages)

        return result

    def _calculate_skill_damage(self,
                                 battle: BattleState,
                                 attacker: Dict,
                                 defender: Dict,
                                 skill: Dict,
                                 is_player: bool) -> Dict:
        """计算技能伤害"""
        category = skill.get("category", "physical")
        power = skill.get("power", 0)
        skill_type = skill.get("type", "normal")

        # 选择攻击/防御属性
        if category == "physical":
            attack_stat = self._get_effective_stat(battle, is_player, "attack")
            defense_stat = self._get_effective_stat(battle, not is_player, "defense")
        else:
            attack_stat = self._get_effective_stat(battle, is_player, "sp_attack")
            defense_stat = self._get_effective_stat(battle, not is_player, "sp_defense")

        # 灼伤降低物理攻击
        if category == "physical" and attacker.get("status") == "burn":
            attack_stat = int(attack_stat * 0.5)

        # 属性克制
        defender_types = defender.get("types", ["normal"])
        type_chart = self.config.types
        effectiveness = GameFormulas.get_type_effectiveness(
            skill_type, defender_types, type_chart
        )

        # 天气修正
        weather_mod = self._get_weather_modifier(battle.weather, skill_type)

        # 暴击判定
        crit_chance = 0.0625  # 基础6.25%
        crit_effects = [e for e in skill.get("effects", []) if e.get("type") == "crit_up"]
        if crit_effects:
            crit_chance = 0.25  # 提高到25%
        # 应用暴击 buff
        crit_buff = attacker.get("_buff_critical", 0)
        if crit_buff > 0:
            crit_chance = min(1.0, crit_chance + crit_buff / 100)  # 暴击率上限100%
        is_critical = random.random() < crit_chance

        is_critical = random.random() < crit_chance

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

    def _process_skill_effects(self,
                                battle: BattleState,
                                attacker: Dict,
                                defender: Dict,
                                effects: List[Dict],
                                is_player: bool) -> List[str]:
        """处理技能附加效果"""
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

            # 状态效果
            if effect_type in ["burn", "paralyze", "poison", "sleep", "freeze"]:
                if defender["current_hp"] > 0 and not defender.get("status"):
                    # 属性免疫检查
                    defender_types = defender.get("types", [])
                    immune = False
                    if effect_type == "burn" and "fire" in defender_types:
                        immune = True
                    if effect_type == "freeze" and "ice" in defender_types:
                        immune = True
                    if effect_type == "paralyze" and "electric" in defender_types:
                        immune = True
                    if effect_type == "poison" and "poison" in defender_types:
                        immune = True

                    if not immune:
                        defender["status"] = effect_type
                        status_names = {
                            "burn": "烧伤", "paralyze": "麻痹",
                            "poison": "中毒", "sleep": "睡眠", "freeze": "冰冻"
                        }
                        messages.append(f"{defender_name} 陷入了{status_names[effect_type]}状态！")

            # 能力变化
            elif effect_type.endswith("_up") or effect_type.endswith("_down"):
                is_up = effect_type.endswith("_up")
                stat_name = effect_type.replace("_up", "").replace("_down", "")

                stages = value if value else (1 if is_up else -1)
                target_is_self = effect.get("target", "enemy") == "self"

                if target_is_self:
                    target = attacker
                    target_name = attacker_name
                    stat_stages = battle.player_stat_stages if is_player else battle.enemy_stat_stages
                else:
                    target = defender
                    target_name = defender_name
                    stat_stages = battle.enemy_stat_stages if is_player else battle.player_stat_stages

                if stat_name in stat_stages:
                    old_stage = stat_stages[stat_name]
                    new_stage = max(-6, min(6, old_stage + stages))
                    stat_stages[stat_name] = new_stage

                    stat_display = {
                        "attack": "攻击", "defense": "防御",
                        "sp_attack": "特攻", "sp_defense": "特防",
                        "speed": "速度", "accuracy": "命中", "evasion": "闪避"
                    }

                    if new_stage != old_stage:
                        change_text = "提高了" if is_up else "降低了"
                        messages.append(f"{target_name} 的{stat_display.get(stat_name, stat_name)}{change_text}！")

            # 治疗效果
            elif effect_type == "heal":
                heal_amount = int(attacker.get("max_hp", 100) * value / 100)
                old_hp = attacker["current_hp"]
                attacker["current_hp"] = min(attacker["max_hp"], old_hp + heal_amount)
                actual_heal = attacker["current_hp"] - old_hp
                if actual_heal > 0:
                    messages.append(f"{attacker_name} 恢复了 {actual_heal} HP！")

            # 回复状态（每回合恢复）
            # 回复状态（每回合恢复）
            elif effect_type == "regen":
                duration = effect.get("duration", 3)
                attacker["_regen"] = value
                attacker["_regen_turns"] = duration
                messages.append(f"{attacker_name} 被治愈之力包围！（持续{duration}回合）")

            # 护盾效果
            elif effect_type == "shield":
                duration = effect.get("duration", 3)
                shield_amount = int(attacker.get("max_hp", 100) * value / 100)
                attacker["_shield"] = attacker.get("_shield", 0) + shield_amount
                attacker["_shield_turns"] = duration
                messages.append(f"{attacker_name} 获得了 {shield_amount} 点护盾！（持续{duration}回合）")

            # 吸血效果（造成伤害时回血）
            elif effect_type == "drain":
                # drain 效果在伤害计算时处理，这里只做标记
                attacker["_drain_percent"] = value
                messages.append(f"{attacker_name} 的攻击将吸取生命！")

            # 属性提升效果 (自身)
            elif effect_type in ["attack_up", "defense_up", "sp_attack_up", "sp_defense_up", 
                                 "speed_up", "accuracy_up", "evasion_up", "critical_up"]:
                stat_name = effect_type.replace("_up", "")
                duration = effect.get("duration", 3)
                boost_percent = value
                # 存储属性加成
                buff_key = f"_buff_{stat_name}"
                buff_turns_key = f"_buff_{stat_name}_turns"
                attacker[buff_key] = attacker.get(buff_key, 0) + boost_percent
                attacker[buff_turns_key] = max(attacker.get(buff_turns_key, 0), duration)
                stat_names_cn = {
                    "attack": "攻击", "defense": "防御", "sp_attack": "特攻",
                    "sp_defense": "特防", "speed": "速度", "accuracy": "命中",
                    "evasion": "闪避", "critical": "暴击"
                }
                messages.append(f"{attacker_name} 的{stat_names_cn.get(stat_name, stat_name)}提升了{boost_percent}%！（持续{duration}回合）")

            # 属性降低效果 (对敌方)
            elif effect_type in ["attack_down", "defense_down", "sp_attack_down", "sp_defense_down",
                                 "speed_down", "accuracy_down", "evasion_down"]:
                stat_name = effect_type.replace("_down", "")
                duration = effect.get("duration", 3)
                debuff_percent = value
                debuff_key = f"_debuff_{stat_name}"
                debuff_turns_key = f"_debuff_{stat_name}_turns"
                defender[debuff_key] = defender.get(debuff_key, 0) + debuff_percent
                defender[debuff_turns_key] = max(defender.get(debuff_turns_key, 0), duration)
                stat_names_cn = {
                    "attack": "攻击", "defense": "防御", "sp_attack": "特攻",
                    "sp_defense": "特防", "speed": "速度", "accuracy": "命中",
                    "evasion": "闪避"
                }
                messages.append(f"{defender_name} 的{stat_names_cn.get(stat_name, stat_name)}降低了{debuff_percent}%！（持续{duration}回合）")


            # 混乱效果
            elif effect_type == "confuse":
                if defender["current_hp"] > 0 and not defender.get("_confused"):
                    duration = effect.get("duration", 3)
                    defender["_confused"] = True
                    defender["_confused_turns"] = duration
                    messages.append(f"{defender_name} 陷入了混乱！（持续{duration}回合）")



        return messages

    def _execute_switch(self,
                        battle: BattleState,
                        action: BattleAction,
                        is_player: bool) -> Dict:
        """执行换精灵"""
        result = {"success": True, "messages": []}

        team = battle.player_team if is_player else battle.enemy_team

        # 找到要换上的精灵
        switch_index = -1
        for i, m in enumerate(team):
            if m.get("instance_id") == action.switch_to_id:
                switch_index = i
                break

        if switch_index < 0:
            result["success"] = False
            result["messages"].append("找不到要换上的精灵！")
            return result

        new_monster = team[switch_index]
        if new_monster.get("current_hp", 0) <= 0:
            result["success"] = False
            result["messages"].append("无法换上已倒下的精灵！")
            return result

        # 执行交换
        old_monster = battle.player_monster if is_player else battle.enemy_monster
        old_name = old_monster.get("nickname") or old_monster.get("name", "???") if old_monster else "???"
        new_name = new_monster.get("nickname") or new_monster.get("name", "???")

        if is_player:
            battle.player_active_index = switch_index
            # 重置能力变化
            battle.player_stat_stages = {
                "attack": 0, "defense": 0, "sp_attack": 0,
                "sp_defense": 0, "speed": 0, "accuracy": 0, "evasion": 0
            }
        else:
            battle.enemy_active_index = switch_index
            # 重置能力变化
            battle.enemy_stat_stages = {
                "attack": 0, "defense": 0, "sp_attack": 0,
                "sp_defense": 0, "speed": 0, "accuracy": 0, "evasion": 0
            }

        result["messages"].append(f"{old_name} 退下了！")
        result["messages"].append(f"去吧，{new_name}！")

        return result

    def _execute_item(self,
                      battle: BattleState,
                      action: BattleAction,
                      is_player: bool) -> Dict:
        """执行使用道具"""
        result = {"success": True, "messages": []}

        item = self.config.get_item("items", action.item_id)
        if not item:
            result["success"] = False
            result["messages"].append("道具不存在！")
            return result

        item_name = item.get("name", action.item_id)
        target_monster = battle.player_monster if is_player else battle.enemy_monster

        if not target_monster:
            result["success"] = False
            return result

        target_name = target_monster.get("nickname") or target_monster.get("name", "???")
        item_type = item.get("type", "")

        result["messages"].append(f"使用了 {item_name}！")

        # 治疗道具
        if item_type == "heal":
            heal_amount = item.get("heal_amount", 50)
            old_hp = target_monster["current_hp"]
            max_hp = target_monster["max_hp"]
            target_monster["current_hp"] = min(max_hp, old_hp + heal_amount)
            actual_heal = target_monster["current_hp"] - old_hp
            result["messages"].append(f"{target_name} 恢复了 {actual_heal} HP！")

        # 状态恢复道具
        elif item_type == "cure_status":
            if target_monster.get("status"):
                target_monster["status"] = None
                target_monster["status_turns"] = 0
                result["messages"].append(f"{target_name} 的异常状态解除了！")
            else:
                result["messages"].append(f"{target_name} 没有异常状态。")

        # 全恢复道具
        elif item_type == "full_restore":
            target_monster["current_hp"] = target_monster["max_hp"]
            target_monster["status"] = None
            target_monster["status_turns"] = 0
            result["messages"].append(f"{target_name} 完全恢复了！")

        return result

    def _process_flee(self, battle: BattleState) -> Dict:
        """处理逃跑"""
        if not battle.can_flee:
            return {"success": False, "message": "无法从这场战斗中逃跑！"}

        player_monster = battle.player_monster
        enemy_monster = battle.enemy_monster

        if not player_monster or not enemy_monster:
            return {"success": True, "message": "成功逃跑了！"}

        # 逃跑概率 = (我方速度 * 32 / 敌方速度) + 30
        player_speed = player_monster.get("stats", {}).get("speed", 50)
        enemy_speed = enemy_monster.get("stats", {}).get("speed", 50)

        flee_chance = (player_speed * 32 / max(1, enemy_speed) + 30) / 100
        flee_chance = min(0.95, max(0.1, flee_chance))  # 10% ~ 95%

        if random.random() < flee_chance:
            return {"success": True, "message": "成功逃跑了！"}
        else:
            return {"success": False, "message": "逃跑失败！"}

    def _process_catch(self, battle: BattleState) -> Dict:
        """处理捕捉"""
        if not battle.can_catch:
            return {"success": False, "message": "无法捕捉这只精灵！"}

        enemy_monster = battle.enemy_monster
        if not enemy_monster:
            return {"success": False, "message": "没有目标！"}

        monster_template = self.config.get_item("monsters", enemy_monster.get("template_id", ""))
        base_catch_rate = 45
        if monster_template:
            base_catch_rate = monster_template.get("catch_rate", 45)

        catch_chance = GameFormulas.calculate_catch_rate(
            base_catch_rate=base_catch_rate,
            current_hp=enemy_monster.get("current_hp", 1),
            max_hp=enemy_monster.get("max_hp", 1),
            status=enemy_monster.get("status"),
            ball_bonus=1.0
        )

        enemy_name = enemy_monster.get("nickname") or enemy_monster.get("name", "???")

        if random.random() < catch_chance:
            return {
                "success": True,
                "message": f"捕捉成功！{enemy_name} 成为了你的伙伴！",
                "caught_monster": enemy_monster
            }
        else:
            return {"success": False, "message": f"捕捉失败！{enemy_name} 挣脱了！"}

    def _generate_enemy_action(self, battle: BattleState) -> BattleAction:
        """生成敌方AI行动"""
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

    def _boss_ai_select_skill(self, battle: BattleState, skills: List[str]) -> str:
        """BOSS AI技能选择"""
        player_monster = battle.player_monster
        if not player_monster:
            return random.choice(skills)

        player_types = player_monster.get("types", [])
        type_chart = self.config.types

        # 优先选择克制技能
        best_skill = None
        best_effectiveness = 0

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

            if score > best_effectiveness:
                best_effectiveness = score
                best_skill = skill_id

        return best_skill if best_skill else random.choice(skills)

    def _process_turn_end(self, battle: BattleState) -> List[str]:
        """处理回合结束效果"""
        messages = []

        # 天气伤害
        weather_messages = self._apply_weather_damage(battle)
        messages.extend(weather_messages)

        # 状态伤害（烧伤、中毒）
        status_messages = self._apply_status_damage(battle)
        messages.extend(status_messages)

        # 回复效果
        regen_messages = self._apply_regen_effects(battle)
        messages.extend(regen_messages)

        # 天气回合减少
        if battle.weather_turns > 0:
            battle.weather_turns -= 1
            if battle.weather_turns <= 0:
                messages.append("天气恢复正常了。")
                battle.weather = "clear"

        return messages

    def _apply_weather_damage(self, battle: BattleState) -> List[str]:
        """应用天气伤害"""
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

    def _apply_status_damage(self, battle: BattleState) -> List[str]:
        """应用状态伤害"""
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
                damage = max(1, monster["max_hp"] // 16)
                monster["current_hp"] = max(0, monster["current_hp"] - damage)
                messages.append(f"{full_name} 被烧伤折磨！(-{damage})")

            elif status == "poison":
                damage = max(1, monster["max_hp"] // 8)
                monster["current_hp"] = max(0, monster["current_hp"] - damage)
                messages.append(f"{full_name} 受到毒素侵蚀！(-{damage})")

        return messages

    def _apply_regen_effects(self, battle: BattleState) -> List[str]:
        """应用回复效果、护盾衰减、混乱等持续效果"""
        messages = []

        for monster in [battle.player_monster, battle.enemy_monster]:
            if not monster or monster.get("current_hp", 0) <= 0:
                continue

            monster_name = monster.get("nickname") or monster.get("name", "???")

            # 回复效果
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

            # 护盾衰减
            shield_turns = monster.get("_shield_turns", 0)
            if shield_turns > 0:
                monster["_shield_turns"] = shield_turns - 1
                if monster["_shield_turns"] <= 0:
                    shield_left = monster.get("_shield", 0)
                    monster["_shield"] = 0
                    if shield_left > 0:
                        messages.append(f"{monster_name} 的护盾消失了。")

            # 混乱效果衰减
            confused_turns = monster.get("_confused_turns", 0)
            if confused_turns > 0:
                monster["_confused_turns"] = confused_turns - 1
                if monster["_confused_turns"] <= 0:
                    monster["_confused"] = False
                    messages.append(f"{monster_name} 恢复了理智！")

            # Buff/Debuff 衰减
            stat_types = ["attack", "defense", "sp_attack", "sp_defense", "speed", "accuracy", "evasion", "critical"]
            stat_names_cn = {
                "attack": "攻击", "defense": "防御", "sp_attack": "特攻",
                "sp_defense": "特防", "speed": "速度", "accuracy": "命中",
                "evasion": "闪避", "critical": "暴击"
            }
            
            # Buff 衰减
            for stat in stat_types:
                buff_turns_key = f"_buff_{stat}_turns"
                buff_key = f"_buff_{stat}"
                buff_turns = monster.get(buff_turns_key, 0)
                if buff_turns > 0:
                    monster[buff_turns_key] = buff_turns - 1
                    if monster[buff_turns_key] <= 0:
                        if monster.get(buff_key, 0) > 0:
                            monster[buff_key] = 0
                            messages.append(f"{monster_name} 的{stat_names_cn.get(stat, stat)}提升效果消失了。")
            
            # Debuff 衰减
            for stat in stat_types:
                debuff_turns_key = f"_debuff_{stat}_turns"
                debuff_key = f"_debuff_{stat}"
                debuff_turns = monster.get(debuff_turns_key, 0)
                if debuff_turns > 0:
                    monster[debuff_turns_key] = debuff_turns - 1
                    if monster[debuff_turns_key] <= 0:
                        if monster.get(debuff_key, 0) > 0:
                            monster[debuff_key] = 0
                            messages.append(f"{monster_name} 的{stat_names_cn.get(stat, stat)}降低效果消失了。")



        return messages



    def _check_battle_end(self, battle: BattleState, result: TurnResult) -> bool:
        """检查战斗是否结束"""
        # 检查玩家队伍
        player_available = battle.get_player_available_monsters()
        if not player_available:
            result.battle_ended = True
            result.winner = "enemy"
            battle.is_active = False
            result.messages.append("你的精灵全部倒下了...")
            return True

        # 检查敌方队伍
        enemy_available = battle.get_enemy_available_monsters()
        if not enemy_available:
            result.battle_ended = True
            result.winner = "player"
            battle.is_active = False

            # 计算奖励
            self._calculate_battle_rewards(battle)
            result.messages.append("战斗胜利！")
            return True

        # 当前精灵倒下，需要换人
        if battle.player_monster and battle.player_monster.get("current_hp", 0) <= 0:
            result.player_monster_fainted = True

        if battle.enemy_monster and battle.enemy_monster.get("current_hp", 0) <= 0:
            result.enemy_monster_fainted = True
            # 敌方自动换下一只
            for i, m in enumerate(battle.enemy_team):
                if m.get("current_hp", 0) > 0:
                    battle.enemy_active_index = i
                    enemy_name = m.get("nickname") or m.get("name", "???")
                    result.messages.append(f"对手派出了 {enemy_name}！")
                    break

        return False

    def _calculate_battle_rewards(self, battle: BattleState):
        """计算战斗奖励"""
        # 经验计算
        total_exp = 0
        for enemy in battle.enemy_team:
            template = self.config.get_item("monsters", enemy.get("template_id", ""))
            base_exp = template.get("base_exp", 100) if template else 100

            exp = GameFormulas.calculate_exp_gain(
                base_exp=base_exp,
                enemy_level=enemy.get("level", 1),
                player_level=battle.player_monster.get("level", 1) if battle.player_monster else 1,
                is_wild=battle.enemy_is_wild,
                is_boss=(battle.battle_type == BattleType.BOSS)
            )
            total_exp += exp

        battle.exp_gained = total_exp

        # 金币计算
        base_coins = 50
        for enemy in battle.enemy_team:
            base_coins += enemy.get("level", 1) * 10

        if battle.battle_type == BattleType.BOSS:
            base_coins *= 5

        battle.coins_gained = base_coins

        # BOSS掉落
        if battle.battle_type == BattleType.BOSS and battle.boss_config:
            rewards = battle.boss_config.get("rewards", {})
            drops = rewards.get("drops", [])

            for drop in drops:
                if random.random() < drop.get("chance", 0):
                    battle.items_dropped.append({
                        "item_id": drop.get("item_id"),
                        "amount": drop.get("amount", 1)
                    })

    # ==================== 辅助方法 ====================

    def _get_effective_stat(self, battle: BattleState, is_player: bool, stat_name: str) -> int:
        """获取经过能力等级修正后的属性值"""
        monster = battle.player_monster if is_player else battle.enemy_monster
        if not monster:
            return 0

        base_value = monster.get("stats", {}).get(stat_name, 0)
        stat_stages = battle.player_stat_stages if is_player else battle.enemy_stat_stages
        stage = stat_stages.get(stat_name, 0)

        if stat_name in ["accuracy", "evasion"]:
            multiplier = self.ACCURACY_STAGE_MULTIPLIERS.get(stage, 1)
        else:
            multiplier = self.STAT_STAGE_MULTIPLIERS.get(stage, 1)

        effective_value = int(base_value * multiplier)
        
        # 应用技能效果产生的 buff/debuff
        buff_percent = monster.get(f"_buff_{stat_name}", 0)
        debuff_percent = monster.get(f"_debuff_{stat_name}", 0)
        
        if buff_percent > 0:
            effective_value = int(effective_value * (1 + buff_percent / 100))
        if debuff_percent > 0:
            effective_value = int(effective_value * (1 - debuff_percent / 100))
        
        return max(1, effective_value)  # 确保属性值至少为1


    def _check_hit(self, battle: BattleState, is_player: bool, base_accuracy: int) -> bool:
        """检查技能是否命中"""
        if base_accuracy >= 100:
            return True

        # 命中 = 基础命中 * (攻击方命中等级 / 防守方闪避等级)
        attacker_stages = battle.player_stat_stages if is_player else battle.enemy_stat_stages
        defender_stages = battle.enemy_stat_stages if is_player else battle.player_stat_stages

        acc_stage = attacker_stages.get("accuracy", 0)
        eva_stage = defender_stages.get("evasion", 0)

        acc_mult = self.ACCURACY_STAGE_MULTIPLIERS.get(acc_stage, 1)
        eva_mult = self.ACCURACY_STAGE_MULTIPLIERS.get(eva_stage, 1)

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

    def _get_weather_modifier(self, weather: str, skill_type: str) -> float:
        """获取天气对技能的修正"""
        weather_config = self.config.get_item("weathers", weather)
        if not weather_config:
            return 1.0

        effects = weather_config.get("effects", {})
        type_effects = effects.get(skill_type, {})

        return type_effects.get("power_mod", 1.0)

    # ==================== 战斗信息展示 ====================

    def get_battle_status_text(self, battle: BattleState) -> str:
        """获取战斗状态文本"""
        player_monster = battle.player_monster
        enemy_monster = battle.enemy_monster

        if not player_monster or not enemy_monster:
            return "战斗数据异常"

        # 天气
        weather_config = self.config.get_item("weathers", battle.weather)
        weather_text = ""
        if weather_config and battle.weather != "clear":
            weather_icon = weather_config.get("icon", "")
            weather_name = weather_config.get("name", battle.weather)
            weather_text = f"{weather_icon} {weather_name}\n"

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
            f"{'═' * 24}\n"
            f"{enemy_prefix}{enemy_name} Lv.{enemy_monster.get('level', 1)} {enemy_status}\n"
            f"HP: {enemy_hp_bar} {enemy_monster.get('current_hp', 0)}/{enemy_monster.get('max_hp', 1)}\n"
            f"{'─' * 24}\n"
            f"{player_name} Lv.{player_monster.get('level', 1)} {player_status}\n"
            f"HP: {player_hp_bar} {player_monster.get('current_hp', 0)}/{player_monster.get('max_hp', 1)}\n"
            f"{'═' * 24}"
        )

        return text

    def get_skill_menu_text(self, battle: BattleState) -> str:
        """获取技能选择菜单"""
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

    def _get_hp_bar(self, monster: Dict, length: int = 10) -> str:
        """生成HP条"""
        current = monster.get("current_hp", 0)
        maximum = monster.get("max_hp", 1)

        ratio = current / maximum if maximum > 0 else 0
        filled = int(ratio * length)
        empty = length - filled

        if ratio > 0.5:
            char = "█"
        elif ratio > 0.2:
            char = "▓"
        else:
            char = "░"

        return char * filled + "·" * empty

    def _get_status_icon(self, status: str) -> str:
        """获取状态图标"""
        status_icons = {
            "burn": "🔥",
            "paralyze": "⚡",
            "poison": "☠️",
            "sleep": "💤",
            "freeze": "❄️",
        }
        return status_icons.get(status, "")

