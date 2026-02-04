"""
战斗系统主模块

BattleSystem 是战斗系统的核心协调者，负责：
- 创建战斗（野外、BOSS）
- 处理回合流程
- 协调各个子模块的工作

设计思想：
- 采用组合模式，将各个职责委托给专门的处理器
- BattleSystem 本身只负责协调和流程控制
- 各个子模块保持独立，易于测试和维护
"""

import random
import uuid
from typing import Dict, List, Optional, TYPE_CHECKING

from .models import (
    BattleType,
    ActionType,
    BattleAction,
    TurnResult,
    BattleState,
)
from .constants import (
    SLEEP_WAKE_CHANCE,
    FREEZE_THAW_CHANCE,
    PARALYZE_SKIP_CHANCE,
    PARALYZE_SPEED_REDUCTION,
    FLEE_BASE_CONSTANT,
    FLEE_SPEED_MULTIPLIER,
    FLEE_MIN_CHANCE,
    FLEE_MAX_CHANCE,
    DEFAULT_SPEED,
    BASE_COIN_REWARD,
    COIN_PER_LEVEL,
    BOSS_COIN_MULTIPLIER,
    DEFAULT_BASE_EXP,
)
from .damage_calculator import DamageCalculator
from .effect_processor import EffectProcessor
from .status_handler import StatusHandler
from .weather_system import WeatherSystem
from .ai_controller import AIController
from .battle_renderer import BattleRenderer

if TYPE_CHECKING:
    from ..config_manager import ConfigManager


class BattleSystem:
    """
    战斗系统
    
    处理回合制战斗的所有逻辑，作为协调者组织各个子模块。
    
    子模块：
    - DamageCalculator: 伤害计算
    - EffectProcessor: 技能效果处理
    - StatusHandler: 状态效果处理
    - WeatherSystem: 天气系统
    - AIController: AI控制
    - BattleRenderer: 渲染器
    """

    def __init__(self, config_manager: "ConfigManager", player_manager=None):
        """
        初始化战斗系统
        
        Args:
            config_manager: 配置管理器
            player_manager: 玩家管理器（用于获取玩家buff、消耗道具等）
        """
        self.config = config_manager
        self.player_manager = player_manager
        
        # 初始化子模块
        self.damage_calculator = DamageCalculator(config_manager)
        self.effect_processor = EffectProcessor()
        self.status_handler = StatusHandler()
        self.weather_system = WeatherSystem(config_manager)
        self.ai_controller = AIController(config_manager)
        self.renderer = BattleRenderer(config_manager)

    # ==================== 战斗创建 ====================

    def create_wild_battle(
        self,
        player_id: str,
        player_team: List[Dict],
        wild_monster: Dict,
        weather: str = "clear"
    ) -> BattleState:
        """
        创建野外战斗
        
        Args:
            player_id: 玩家ID
            player_team: 玩家队伍
            wild_monster: 野生精灵数据
            weather: 天气
            
        Returns:
            战斗状态
        """
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

    def create_boss_battle(
        self,
        player_id: str,
        player_team: List[Dict],
        boss_id: str,
        weather: str = "clear"
    ) -> Optional[BattleState]:
        """
        创建BOSS战斗
        
        Args:
            player_id: 玩家ID
            player_team: 玩家队伍
            boss_id: BOSS ID
            weather: 天气
            
        Returns:
            战斗状态，如果BOSS不存在则返回None
        """
        from ..monster import MonsterInstance

        boss_config = self.config.get_item("bosses", boss_id)
        if not boss_config:
            return None

        # 获取精灵模板
        template_id = boss_config.get("monster_template_id")
        
        if template_id:
            monster_template = self.config.get_item("monsters", template_id)
            if not monster_template:
                return None
        else:
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

    async def process_turn(
        self,
        battle: BattleState,
        player_action: BattleAction
    ) -> TurnResult:
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
            catch_result = await self._process_catch(battle, player_action)
            result.messages.append(catch_result["message"])
            if catch_result["success"]:
                result.battle_ended = True
                result.winner = "catch"
                result.caught_monster = catch_result.get("caught_monster", {})
                battle.is_active = False
            return result

        # 3. 生成敌方行动
        enemy_action = self.ai_controller.generate_enemy_action(battle)

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

    def _determine_action_order(
        self,
        battle: BattleState,
        player_action: BattleAction,
        enemy_action: BattleAction
    ) -> tuple:
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
        player_speed = self.damage_calculator.get_effective_stat(battle, True, "speed")
        enemy_speed = self.damage_calculator.get_effective_stat(battle, False, "speed")

        # 麻痹减速
        player_monster = battle.player_monster
        enemy_monster = battle.enemy_monster

        if player_monster and player_monster.get("status") == "paralyze":
            player_speed = int(player_speed * PARALYZE_SPEED_REDUCTION)
        if enemy_monster and enemy_monster.get("status") == "paralyze":
            enemy_speed = int(enemy_speed * PARALYZE_SPEED_REDUCTION)

        # 速度相同随机
        if player_speed == enemy_speed:
            player_first = random.random() < 0.5
        else:
            player_first = player_speed > enemy_speed

        if player_first:
            return (player_action, enemy_action, True)
        else:
            return (enemy_action, player_action, False)

    def _execute_action(
        self,
        battle: BattleState,
        action: BattleAction,
        is_player: bool
    ) -> Dict:
        """执行一个行动"""
        result = {"success": True, "messages": []}

        if action.action_type == ActionType.SKILL:
            result = self._execute_skill(battle, action, is_player)
        elif action.action_type == ActionType.SWITCH:
            result = self._execute_switch(battle, action, is_player)
        elif action.action_type == ActionType.ITEM:
            result = self._execute_item(battle, action, is_player)

        return result

    def _execute_skill(
        self,
        battle: BattleState,
        action: BattleAction,
        is_player: bool
    ) -> Dict:
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
            wake_chance = SLEEP_WAKE_CHANCE if status == "sleep" else FREEZE_THAW_CHANCE
            if random.random() < wake_chance:
                attacker["status"] = None
                status_name = "醒来了" if status == "sleep" else "解冻了"
                result["messages"].append(f"{attacker_name} {status_name}！")
            else:
                status_msg = "正在睡觉" if status == "sleep" else "被冻住了"
                result["messages"].append(f"{attacker_name} {status_msg}，无法行动！")
                return result

        if status == "paralyze":
            if random.random() < PARALYZE_SKIP_CHANCE:
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
        if not self.damage_calculator.check_hit(battle, is_player, accuracy):
            result["messages"].append("但是没有命中！")
            result["is_missed"] = True
            return result

        # 计算伤害
        power = skill.get("power", 0)
        category = skill.get("category", "physical")

        if power > 0 and category in ["physical", "special"]:
            damage_result = self.damage_calculator.calculate_skill_damage(
                battle, attacker, defender, skill, is_player
            )

            damage = damage_result["damage"]
            result["damage"] = damage
            result["is_critical"] = damage_result["is_critical"]
            result["effectiveness"] = damage_result["effectiveness"]

            # 护盾吸收伤害
            shield = defender.get("_shield", 0)
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
        effect_messages = self.effect_processor.process_skill_effects(
            battle, attacker, defender, effects, is_player
        )
        result["messages"].extend(effect_messages)

        return result

    def _execute_switch(
        self,
        battle: BattleState,
        action: BattleAction,
        is_player: bool
    ) -> Dict:
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
            battle.reset_player_stat_stages()
        else:
            battle.enemy_active_index = switch_index
            battle.reset_enemy_stat_stages()

        result["messages"].append(f"{old_name} 退下了！")
        result["messages"].append(f"去吧，{new_name}！")

        return result

    def _execute_item(
        self,
        battle: BattleState,
        action: BattleAction,
        is_player: bool
    ) -> Dict:
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
        player_speed = player_monster.get("stats", {}).get("speed", DEFAULT_SPEED)
        enemy_speed = enemy_monster.get("stats", {}).get("speed", DEFAULT_SPEED)

        flee_chance = (player_speed * FLEE_SPEED_MULTIPLIER / max(1, enemy_speed) + FLEE_BASE_CONSTANT) / 100
        flee_chance = min(FLEE_MAX_CHANCE, max(FLEE_MIN_CHANCE, flee_chance))

        if random.random() < flee_chance:
            return {"success": True, "message": "成功逃跑了！"}
        else:
            return {"success": False, "message": "逃跑失败！"}

    async def _process_catch(self, battle: BattleState, action: BattleAction) -> Dict:
        """处理捕捉行动"""
        if not battle.can_catch:
            return {"success": False, "message": "❌ 无法捕捉这只精灵！"}

        enemy_monster = battle.enemy_monster
        if not enemy_monster:
            return {"success": False, "message": "❌ 没有目标！"}

        ball_id = action.ball_id
        if not ball_id:
            return {"success": False, "message": "❌ 请选择要使用的精灵球！"}

        # 获取精灵球配置
        ball_config = self.config.get_item("items", ball_id)
        if not ball_config or ball_config.get("type") != "capture":
            return {"success": False, "message": f"❌ {ball_id} 不是有效的精灵球！"}

        # 消耗精灵球
        if self.player_manager and battle.player_id:
            has_ball = await self.player_manager.has_item(battle.player_id, ball_id, 1)
            if not has_ball:
                return {"success": False, "message": f"❌ 你没有 {ball_id}！"}
            await self.player_manager.use_item(battle.player_id, ball_id, 1)

        # 获取捕捉配置
        catch_config = self.config.catch_config or {}
        rarity_rates = catch_config.get("rarity_catch_rates", {})
        ball_multipliers = catch_config.get("ball_multipliers", {})
        rate_cap = catch_config.get("catch_rate_cap", {})
        hp_config = catch_config.get("hp_modifier", {"min_multiplier": 0.0, "max_multiplier": 1.0})

        # 获取精灵稀有度
        monster_rarity = enemy_monster.get("rarity", 3)
        
        # 1. 基础捕捉率
        base_catch_rate = rarity_rates.get(str(monster_rarity), 0.5)
        
        # 2. 血量修正
        hp_min = hp_config.get("min_multiplier", 0.0)
        hp_max = hp_config.get("max_multiplier", 1.0)
        
        current_hp = enemy_monster.get("current_hp", enemy_monster.get("hp", 100))
        max_hp = enemy_monster.get("stats", {}).get("hp", enemy_monster.get("hp", 100))
        hp_percent = max(0.01, current_hp / max_hp) if max_hp > 0 else 1.0
        hp_modifier = hp_max - (hp_max - hp_min) * hp_percent
        
        # 3. 精灵球加成
        ball_bonus = ball_multipliers.get(ball_id, ball_config.get("effect", {}).get("capture_rate", 1.0))
        
        # 4. 计算最终捕捉率
        catch_chance = base_catch_rate * hp_modifier * ball_bonus

        # 5. 应用玩家buff
        buff_multiplier = 1.0
        buff_msg = ""
        if self.player_manager and battle.player_id:
            buff_multiplier = await self.player_manager.get_buff_multiplier(battle.player_id, "catch_rate")
            if buff_multiplier > 1.0:
                buff_msg = f" (🍀+{int((buff_multiplier-1)*100)}%)"
        
        catch_chance = catch_chance * buff_multiplier

        # 6. 应用上下限
        min_rate = rate_cap.get("min", 0.05)
        max_rate = rate_cap.get("max", 0.95)
        catch_chance = max(min_rate, min(max_rate, catch_chance))

        enemy_name = enemy_monster.get("nickname") or enemy_monster.get("name", "???")
        rarity_stars = "⭐" * monster_rarity
        
        # 构建捕捉信息
        ball_name = ball_config.get("name", ball_id)
        hp_display = f"{current_hp}/{max_hp} ({hp_percent*100:.0f}%)"
        catch_info = f"🎯 使用了 {ball_name}！\n"
        catch_info += f"❤️ 目标血量: {hp_display} (修正×{hp_modifier:.2f})\n"
        catch_info += f"📊 捕捉率: {catch_chance*100:.1f}%{buff_msg}\n"

        if random.random() < catch_chance:
            return {
                "success": True,
                "message": f"{catch_info}✨ 捕捉成功！{enemy_name} {rarity_stars} 成为了你的伙伴！",
                "caught_monster": enemy_monster,
                "ball_used": ball_id,
                "catch_rate": catch_chance
            }
        else:
            return {
                "success": False, 
                "message": f"{catch_info}💨 捕捉失败！{enemy_name} 挣脱了！",
                "ball_used": ball_id,
                "catch_rate": catch_chance
            }

    def _process_turn_end(self, battle: BattleState) -> List[str]:
        """处理回合结束效果"""
        messages = []

        # 天气伤害
        weather_messages = self.weather_system.apply_weather_damage(battle)
        messages.extend(weather_messages)

        # 状态伤害（烧伤、中毒）
        status_messages = self.status_handler.apply_status_damage(battle)
        messages.extend(status_messages)

        # 回复效果
        regen_messages = self.status_handler.apply_regen_effects(battle)
        messages.extend(regen_messages)

        # 天气回合减少
        weather_decay_messages = self.weather_system.process_weather_turn(battle)
        messages.extend(weather_decay_messages)

        return messages

    def _check_battle_end(self, battle: BattleState, result: TurnResult) -> bool:
        """检查战斗是否结束"""
        from ..formulas import GameFormulas
        
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
        from ..formulas import GameFormulas
        
        # 经验计算
        total_exp = 0
        for enemy in battle.enemy_team:
            template = self.config.get_item("monsters", enemy.get("template_id", ""))
            base_exp = template.get("base_exp", DEFAULT_BASE_EXP) if template else DEFAULT_BASE_EXP

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
        base_coins = BASE_COIN_REWARD
        for enemy in battle.enemy_team:
            base_coins += enemy.get("level", 1) * COIN_PER_LEVEL

        if battle.battle_type == BattleType.BOSS:
            base_coins *= BOSS_COIN_MULTIPLIER

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

    # ==================== 渲染方法 ====================

    def get_battle_status_text(self, battle: BattleState) -> str:
        """获取战斗状态文本"""
        return self.renderer.get_battle_status_text(battle)

    def get_skill_menu_text(self, battle: BattleState) -> str:
        """获取技能选择菜单"""
        return self.renderer.get_skill_menu_text(battle)
