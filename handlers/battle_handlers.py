"""
战斗相关指令处理器
- 战斗、捕捉、技能使用等
"""

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger
# 不再需要 session_waiter，改用数据库状态 + 前缀触发
# from astrbot.core.utils.session_waiter import session_waiter, SessionController

from typing import TYPE_CHECKING, Dict
import random

from astrbot.core.utils.session_waiter import session_waiter, SessionController

if TYPE_CHECKING:
    from ..main import MonsterGamePlugin


class BattleHandlers:
    """战斗相关指令处理器"""

    def __init__(self, plugin: "MonsterGamePlugin"):
        self.plugin = plugin
        self.config = plugin.game_config
        self.pm = plugin.player_manager
        self.battle_system = plugin.battle_system
        self.world_manager = plugin.world_manager

        # 活跃战斗 {unified_msg_origin: BattleState}
        self._active_battles: Dict[str, "BattleState"] = {}

    def _get_imports(self):
        """延迟导入"""
        from ..core import (
            MonsterInstance, BattleState, BattleAction,
            ActionType, BattleType
        )
        return MonsterInstance, BattleState, BattleAction, ActionType, BattleType

    def _make_hp_bar(self, current: int, maximum: int, length: int = 10) -> str:
        """生成HP条"""
        if maximum <= 0:
            return "?" * length
        ratio = current / maximum
        filled = int(ratio * length)
        empty = length - filled
        if ratio > 0.5:
            char = "█"
        elif ratio > 0.2:
            char = "▓"
        else:
            char = "░"
        return char * filled + "·" * empty

    def get_active_battle(self, umo: str):
        """获取活跃战斗"""
        return self._active_battles.get(umo)

    def set_active_battle(self, umo: str, battle):
        """设置活跃战斗"""
        self._active_battles[umo] = battle

    def clear_active_battle(self, umo: str):
        """清除活跃战斗"""
        if umo in self._active_battles:
            del self._active_battles[umo]

    async def cmd_battle(self, event: AstrMessageEvent):
        """
        快速野外战斗
        指令: /精灵 战斗
        """
        MonsterInstance, BattleState, BattleAction, ActionType, BattleType = self._get_imports()

        user_id = event.get_sender_id()
        umo = event.unified_msg_origin

        player = self.pm.get_player(user_id)
        if not player:
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        # 检查是否已在战斗
        if umo in self._active_battles:
            battle = self._active_battles[umo]
            battle_text = self.battle_system.get_battle_status_text(battle)
            skill_menu = self.battle_system.get_skill_menu_text(battle)
            yield event.plain_result(
                f"⚔️ 你正在战斗中！\n\n"
                f"{battle_text}\n\n"
                f"{skill_menu}\n\n"
                f"输入技能序号继续战斗"
            )
            await self._battle_session(event, user_id, umo)
            return

        # 检查队伍
        team = self.pm.get_team(user_id)
        if not team:
            yield event.plain_result(
                "❌ 队伍为空！\n"
                "发送 /精灵 队伍 设置 来组建队伍"
            )
            return

        available = [m for m in team if m.get("current_hp", 0) > 0]
        if not available:
            yield event.plain_result(
                "❌ 队伍中没有可战斗的精灵！\n"
                "发送 /精灵 治疗 恢复精灵"
            )
            return

        stamina_cost = self.plugin.battle_stamina_cost
        # 检查体力
        if player["stamina"] < stamina_cost:
            yield event.plain_result(
                f"❌ 体力不足！\n"
                f"当前体力: {player['stamina']}/100\n"
                f"战斗需要 {stamina_cost} 体力"
            )
            return

        self.pm.consume_stamina(user_id, stamina_cost)

        # 随机生成野生精灵
        monsters = self.config.monsters
        if not monsters:
            yield event.plain_result("❌ 没有配置精灵数据")
            return

        template_id = random.choice(list(monsters.keys()))
        template = monsters[template_id]

        avg_level = sum(m.get("level", 1) for m in available) // len(available)
        wild_level = max(1, avg_level + random.randint(-3, 3))

        wild_monster = MonsterInstance.from_template(
            template=template,
            level=wild_level,
            config_manager=self.config
        )

        # 创建战斗
        battle = self.battle_system.create_wild_battle(
            player_id=user_id,
            player_team=team,
            wild_monster=wild_monster.to_dict()
        )

        self._active_battles[umo] = battle

        # 显示战斗界面
        wild_name = wild_monster.get_display_name()
        battle_text = self.battle_system.get_battle_status_text(battle)
        skill_menu = self.battle_system.get_skill_menu_text(battle)

        yield event.plain_result(
            f"🐾 野生的 {wild_name} 出现了！\n\n"
            f"{battle_text}\n\n"
            f"{skill_menu}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"输入技能序号(1-4)进行攻击\n"
            f"输入「逃跑」逃离战斗\n"
            f"输入「捕捉」尝试捕捉"
        )

        # 进入战斗会话
        await self._battle_session(event, user_id, umo)

    async def start_battle_from_explore(self,
                                        event: AstrMessageEvent,
                                        user_id: str,
                                        umo: str,
                                        monster_data: Dict,
                                        weather: str = "clear",
                                        is_boss: bool = False,
                                        boss_id: str = ""):
        """
        从探索触发战斗（供explore_handlers调用）
        """
        MonsterInstance, BattleState, BattleAction, ActionType, BattleType = self._get_imports()

        team = self.pm.get_team(user_id)

        if is_boss:
            battle = self.battle_system.create_boss_battle(
                player_id=user_id,
                player_team=team,
                boss_id=boss_id,
                weather=weather
            )
        else:
            battle = self.battle_system.create_wild_battle(
                player_id=user_id,
                player_team=team,
                wild_monster=monster_data,
                weather=weather
            )

        if not battle:
            return  # 改为 return，无需返回值

        self._active_battles[umo] = battle

        # 显示战斗界面
        battle_text = self.battle_system.get_battle_status_text(battle)
        skill_menu = self.battle_system.get_skill_menu_text(battle)

        prefix = "👹 BOSS战！" if is_boss else "⚔️ 战斗开始！"

        # ✅ 使用 yield 让这个方法变成异步生成器
        yield event.plain_result(
            f"{prefix}\n\n"
            f"{battle_text}\n\n"
            f"{skill_menu}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"输入技能序号(1-4)攻击\n"
            f"输入「逃跑」逃离 | 输入「捕捉」捕捉"
        )

        # 进入战斗会话
        async for resp in self._battle_session(event, user_id, umo):
            yield resp

    async def _battle_session(self, event: AstrMessageEvent, user_id: str, umo: str):
        """战斗会话处理"""
        MonsterInstance, BattleState, BattleAction, ActionType, BattleType = self._get_imports()

        @session_waiter(timeout=self.plugin.battle_timeout, record_history_chains=False)
        async def battle_loop(controller: SessionController, ev: AstrMessageEvent):
            msg = ev.message_str.strip()

            battle = self._active_battles.get(umo)
            if not battle or not battle.is_active:
                await ev.send(ev.plain_result("❌ 战斗已结束"))
                controller.stop()
                return

            player_monster = battle.player_monster
            if not player_monster:
                await ev.send(ev.plain_result("❌ 战斗数据异常"))
                self.clear_active_battle(umo)
                controller.stop()
                return

            # 构建玩家行动
            action = None

            # 逃跑
            if msg in ["逃跑", "逃", "跑", "run", "flee", "逃走"]:
                action = BattleAction(action_type=ActionType.FLEE, actor_id="")

            # 捕捉
            elif msg in ["捕捉", "捕", "抓", "catch", "捕获"]:
                action = BattleAction(action_type=ActionType.CATCH, actor_id="")

            # 换精灵（输入"换 2"或"switch 2"）
            elif msg.startswith("换") or msg.lower().startswith("switch"):
                parts = msg.split()
                if len(parts) >= 2:
                    try:
                        switch_idx = int(parts[1]) - 1
                        available = battle.get_player_available_monsters()

                        for idx, m in available:
                            if idx == switch_idx:
                                action = BattleAction(
                                    action_type=ActionType.SWITCH,
                                    actor_id=player_monster.get("instance_id", ""),
                                    switch_to_id=m.get("instance_id", "")
                                )
                                break

                        if not action:
                            await ev.send(ev.plain_result("❌ 无效的精灵序号"))
                            controller.keep(timeout=180, reset_timeout=True)
                            return
                    except ValueError:
                        await ev.send(ev.plain_result("❌ 请输入正确的序号，如: 换 2"))
                        controller.keep(timeout=180, reset_timeout=True)
                        return
                else:
                    # 显示可换的精灵
                    available = battle.get_player_available_monsters()
                    lines = ["可切换的精灵："]
                    for idx, m in available:
                        if idx != battle.player_active_index:
                            name = m.get("nickname") or m.get("name", "???")
                            hp = m.get("current_hp", 0)
                            max_hp = m.get("max_hp", 1)
                            lines.append(f"{idx + 1}. {name} HP:{hp}/{max_hp}")
                    lines.append("输入「换 序号」切换，如: 换 2")
                    await ev.send(ev.plain_result("\n".join(lines)))
                    controller.keep(timeout=180, reset_timeout=True)
                    return

            # 技能（数字）
            elif msg.isdigit():
                skill_index = int(msg)
                skills = player_monster.get("skills", [])

                if skill_index < 1 or skill_index > len(skills):
                    await ev.send(ev.plain_result(f"❌ 请输入 1 到 {len(skills)} 的技能序号"))
                    controller.keep(timeout=180, reset_timeout=True)
                    return

                skill_id = skills[skill_index - 1]
                action = BattleAction(
                    action_type=ActionType.SKILL,
                    actor_id=player_monster.get("instance_id", ""),
                    skill_id=skill_id
                )

            else:
                await ev.send(ev.plain_result(
                    "❓ 无效输入\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "输入 1-4 使用技能\n"
                    "输入「逃跑」逃离战斗\n"
                    "输入「捕捉」捕捉精灵\n"
                    "输入「换 序号」切换精灵"
                ))
                controller.keep(timeout=180, reset_timeout=True)
                return

            # 执行回合
            turn_result = self.battle_system.process_turn(battle, action)

            # 构建回合消息
            turn_messages = "\n".join(turn_result.messages)

            # 战斗结束判定
            if turn_result.battle_ended:
                await self._handle_battle_end(ev, user_id, umo, battle, turn_result, turn_messages)
                controller.stop()
                return

            # 战斗继续 - 保存精灵状态
            for m_data in battle.player_team:
                self.pm.update_monster_from_dict(
                    m_data.get("instance_id", ""),
                    m_data
                )

            # 检查是否需要换精灵
            if turn_result.player_monster_fainted:
                available = battle.get_player_available_monsters()

                if available:
                    lines = [f"{turn_messages}\n", "💀 你的精灵倒下了！请选择下一只："]
                    for idx, m in available:
                        name = m.get("nickname") or m.get("name", "???")
                        hp = m.get("current_hp", 0)
                        max_hp = m.get("max_hp", 1)
                        lines.append(f"{idx + 1}. {name} HP:{hp}/{max_hp}")
                    lines.append("输入「换 序号」切换精灵")

                    await ev.send(ev.plain_result("\n".join(lines)))
                    controller.keep(timeout=180, reset_timeout=True)
                    return

            # 显示战斗状态
            battle_text = self.battle_system.get_battle_status_text(battle)
            skill_menu = self.battle_system.get_skill_menu_text(battle)

            await ev.send(ev.plain_result(
                f"{turn_messages}\n\n"
                f"{battle_text}\n\n"
                f"{skill_menu}"
            ))

            controller.keep(timeout=self.plugin.battle_timeout, reset_timeout=True)

        try:
            await battle_loop(event)
        except TimeoutError:
            self.clear_active_battle(umo)
            yield event.plain_result("⏰ 战斗超时，已自动退出")
        finally:
            event.stop_event()

    async def _handle_battle_end(self, event, user_id, umo, battle, turn_result, turn_messages):
        """处理战斗结束"""
        MonsterInstance, BattleState, BattleAction, ActionType, BattleType = self._get_imports()

        self.clear_active_battle(umo)

        if turn_result.winner == "player":
            # 胜利
            # 应用经验和金币倍率（包括玩家buff）
            exp_buff = self.pm.get_buff_multiplier(user_id, "exp_rate")
            coin_buff = self.pm.get_buff_multiplier(user_id, "coin_rate")
            exp_gained = int(battle.exp_gained * self.plugin.exp_multiplier * exp_buff)
            coins_gained = int(battle.coins_gained * self.plugin.coin_multiplier * coin_buff)

            # 发放奖励
            self.pm.add_currency(user_id, coins=coins_gained)
            self.pm.record_battle(user_id, is_win=True)

            # 精灵获得经验
            team = self.pm.get_team(user_id)
            level_up_messages = []
            active_count = sum(1 for m in team if m.get("current_hp", 0) > 0)
            exp_each = exp_gained // max(1, active_count)

            for m_data in team:
                if m_data.get("current_hp", 0) > 0:
                    monster = MonsterInstance.from_dict(m_data, self.config)
                    result = monster.add_exp(exp_each, self.config)

                    if result["leveled_up"]:
                        level_up_messages.append(
                            f"🎉 {monster.get_display_name()} 升到了 Lv.{monster.level}！"
                        )
                        if result["can_evolve"]:
                            level_up_messages.append(
                                f"✨ {monster.get_display_name()} 可以进化了！"
                            )

                    self.pm.update_monster(monster)

            # 更新探索地图状态
            exp_map = self.world_manager.get_active_map(user_id)
            if exp_map:
                if battle.battle_type == BattleType.BOSS:
                    self.world_manager.mark_boss_defeated(user_id)
                    self.pm.record_boss_clear(user_id, battle.boss_id)
                else:
                    self.world_manager.mark_monster_defeated(user_id)

            level_up_text = "\n".join(level_up_messages)
            if level_up_text:
                level_up_text = "\n" + level_up_text

            await event.send(event.plain_result(
                f"{turn_messages}\n\n"
                f"🏆 战斗胜利！\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"获得 ✨{exp_gained} 经验\n"
                f"获得 💰{coins_gained} 金币"
                f"{level_up_text}"
            ))

        elif turn_result.winner == "flee":
            await event.send(event.plain_result(f"{turn_messages}"))

        elif turn_result.winner == "enemy":
            self.pm.record_battle(user_id, is_win=False)
            await event.send(event.plain_result(
                f"{turn_messages}\n\n"
                f"💀 战斗失败...\n"
                f"发送 /精灵 治疗 恢复精灵"
            ))

        # 如果在探索中，显示地图
        exp_map = self.world_manager.get_active_map(user_id)
        if exp_map:
            map_text = self.world_manager.render_map(exp_map)
            await event.send(event.plain_result(f"\n{map_text}"))

    # ==================== 前缀触发的战斗处理 ====================

    async def start_battle_from_state(self, event: AstrMessageEvent, user_id: str):
        """
        从数据库状态启动战斗（由探索触发）
        """
        MonsterInstance, BattleState, BattleAction, ActionType, BattleType = self._get_imports()
        
        # 获取战斗状态数据
        state, state_data = self.plugin.db.get_game_state(user_id)
        if state != "battling" or not state_data:
            yield event.plain_result("❌ 战斗状态异常")
            return
        
        umo = event.unified_msg_origin
        team = self.pm.get_team(user_id)
        
        monster_data = state_data.get("monster_data", {})
        weather = state_data.get("weather", "clear")
        is_boss = state_data.get("is_boss", False)
        boss_id = state_data.get("boss_id", "")
        
        # 创建战斗
        if is_boss:
            battle = self.battle_system.create_boss_battle(
                player_id=user_id,
                player_team=team,
                boss_id=boss_id,
                weather=weather
            )
        else:
            battle = self.battle_system.create_wild_battle(
                player_id=user_id,
                player_team=team,
                wild_monster=monster_data,
                weather=weather
            )
        
        if not battle:
            self.plugin.db.clear_game_state(user_id)
            yield event.plain_result("❌ 创建战斗失败")
            return
        
        self._active_battles[umo] = battle
        
        # 显示战斗界面
        battle_text = self.battle_system.get_battle_status_text(battle)
        skill_menu = self.battle_system.get_skill_menu_text(battle)
        prefix = self.plugin.game_action_prefix
        
        battle_type_text = "👹 BOSS战！" if is_boss else "⚔️ 战斗开始！"
        
        yield event.plain_result(
            f"{battle_type_text}\n\n"
            f"{battle_text}\n\n"
            f"{skill_menu}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 发送 \"{prefix}数字\" 使用技能（如 {prefix}1）\n"
            f"💡 发送 \"{prefix}逃跑\" 逃离战斗\n"
            f"💡 发送 \"{prefix}捕捉\" 尝试捕捉"
        )

    async def handle_battle_action(self, event: AstrMessageEvent, user_id: str, action: str, state_data: dict):
        """
        处理前缀触发的战斗操作
        
        Args:
            event: 消息事件
            user_id: 用户ID
            action: 去掉前缀后的操作内容（如 "1", "逃跑", "捕捉"）
            state_data: 游戏状态数据
        """
        MonsterInstance, BattleState, BattleAction, ActionType, BattleType = self._get_imports()
        prefix = self.plugin.game_action_prefix
        umo = event.unified_msg_origin
        
        # 获取活跃战斗
        battle = self._active_battles.get(umo)
        if not battle or not battle.is_active:
            # 战斗不存在，清除状态
            self.plugin.db.clear_game_state(user_id)
            yield event.plain_result("❌ 战斗已结束")
            return
        
        player_monster = battle.player_monster
        if not player_monster:
            self.clear_active_battle(umo)
            self.plugin.db.clear_game_state(user_id)
            yield event.plain_result("❌ 战斗数据异常")
            return
        
        # 构建玩家行动
        battle_action = None
        
        # 逃跑
        if action in ["逃跑", "逃", "跑", "run", "flee", "逃走"]:
            battle_action = BattleAction(action_type=ActionType.FLEE, actor_id="")
        
        # 捕捉
        elif action in ["捕捉", "捕", "抓", "catch", "捕获"]:
            battle_action = BattleAction(action_type=ActionType.CATCH, actor_id="")
        
        # 换精灵
        elif action.startswith("换") or action.lower().startswith("switch"):
            parts = action.split()
            if len(parts) >= 2:
                try:
                    switch_idx = int(parts[1]) - 1
                    available = battle.get_player_available_monsters()
                    
                    for idx, m in available:
                        if idx == switch_idx:
                            battle_action = BattleAction(
                                action_type=ActionType.SWITCH,
                                actor_id=player_monster.get("instance_id", ""),
                                switch_to_id=m.get("instance_id", "")
                            )
                            break
                    
                    if not battle_action:
                        yield event.plain_result("❌ 无效的精灵序号")
                        return
                except ValueError:
                    yield event.plain_result(f"❌ 请输入正确的序号，如: {prefix}换 2")
                    return
            else:
                # 显示可换的精灵
                available = battle.get_player_available_monsters()
                lines = ["可切换的精灵："]
                for idx, m in available:
                    if idx != battle.player_active_index:
                        name = m.get("nickname") or m.get("name", "???")
                        hp = m.get("current_hp", 0)
                        max_hp = m.get("max_hp", 1)
                        lines.append(f"{idx + 1}. {name} HP:{hp}/{max_hp}")
                lines.append(f"发送 {prefix}换 序号 切换，如: {prefix}换 2")
                yield event.plain_result("\n".join(lines))
                return
        
        # 技能（数字）
        elif action.isdigit():
            skill_index = int(action)
            skills = player_monster.get("skills", [])
            
            if skill_index < 1 or skill_index > len(skills):
                yield event.plain_result(f"❌ 请输入 1 到 {len(skills)} 的技能序号")
                return
            
            skill_id = skills[skill_index - 1]
            battle_action = BattleAction(
                action_type=ActionType.SKILL,
                actor_id=player_monster.get("instance_id", ""),
                skill_id=skill_id
            )
        
        else:
            yield event.plain_result(
                f"❓ 无效输入: {action}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"发送 \"{prefix}1-4\" 使用技能\n"
                f"发送 \"{prefix}逃跑\" 逃离战斗\n"
                f"发送 \"{prefix}捕捉\" 捕捉精灵\n"
                f"发送 \"{prefix}换 序号\" 切换精灵"
            )
            return
        
        # 执行回合
        turn_result = self.battle_system.process_turn(battle, battle_action)
        turn_messages = "\n".join(turn_result.messages)
        
        # 战斗结束判定
        if turn_result.battle_ended:
            async for resp in self._handle_battle_end_with_state(event, user_id, umo, battle, turn_result, turn_messages, state_data):
                yield resp
            return
        
        # 战斗继续 - 保存精灵状态
        for m_data in battle.player_team:
            self.pm.update_monster_from_dict(m_data.get("instance_id", ""), m_data)
        
        # 检查是否需要换精灵
        if turn_result.player_monster_fainted:
            available = battle.get_player_available_monsters()
            if available:
                lines = [f"{turn_messages}\n", "💀 你的精灵倒下了！请选择下一只："]
                for idx, m in available:
                    name = m.get("nickname") or m.get("name", "???")
                    hp = m.get("current_hp", 0)
                    max_hp = m.get("max_hp", 1)
                    lines.append(f"{idx + 1}. {name} HP:{hp}/{max_hp}")
                lines.append(f"发送 \"{prefix}换 序号\" 切换精灵")
                yield event.plain_result("\n".join(lines))
                return
        
        # 显示战斗状态
        battle_text = self.battle_system.get_battle_status_text(battle)
        skill_menu = self.battle_system.get_skill_menu_text(battle)
        
        yield event.plain_result(
            f"{turn_messages}\n\n"
            f"{battle_text}\n\n"
            f"{skill_menu}"
        )

    async def _handle_battle_end_with_state(self, event, user_id, umo, battle, turn_result, turn_messages, state_data):
        """处理战斗结束（带状态管理）"""
        MonsterInstance, BattleState, BattleAction, ActionType, BattleType = self._get_imports()
        
        self.clear_active_battle(umo)
        prefix = self.plugin.game_action_prefix
        from_explore = state_data.get("from_explore", False)
        
        if turn_result.winner == "player":
            # 胜利
            exp_buff = self.pm.get_buff_multiplier(user_id, "exp_rate")
            coin_buff = self.pm.get_buff_multiplier(user_id, "coin_rate")
            exp_gained = int(battle.exp_gained * self.plugin.exp_multiplier * exp_buff)
            coins_gained = int(battle.coins_gained * self.plugin.coin_multiplier * coin_buff)
            
            # 发放奖励
            self.pm.add_currency(user_id, coins=coins_gained)
            self.pm.record_battle(user_id, is_win=True)
            
            # 精灵获得经验
            team = self.pm.get_team(user_id)
            level_up_messages = []
            active_count = sum(1 for m in team if m.get("current_hp", 0) > 0)
            exp_each = exp_gained // max(1, active_count)
            
            for m_data in team:
                if m_data.get("current_hp", 0) > 0:
                    monster = MonsterInstance.from_dict(m_data, self.config)
                    result = monster.add_exp(exp_each, self.config)
                    
                    if result["leveled_up"]:
                        level_up_messages.append(f"🎉 {monster.get_display_name()} 升到了 Lv.{monster.level}！")
                        if result["can_evolve"]:
                            level_up_messages.append(f"✨ {monster.get_display_name()} 可以进化了！")
                    
                    self.pm.update_monster(monster)
            
            # 更新探索地图状态
            exp_map = self.world_manager.get_active_map(user_id)
            if exp_map:
                if battle.battle_type == BattleType.BOSS:
                    self.world_manager.mark_boss_defeated(user_id)
                    self.pm.record_boss_clear(user_id, battle.boss_id)
                else:
                    self.world_manager.mark_monster_defeated(user_id)
            
            level_up_text = "\n".join(level_up_messages)
            if level_up_text:
                level_up_text = "\n" + level_up_text
            
            yield event.plain_result(
                f"{turn_messages}\n\n"
                f"🏆 战斗胜利！\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"获得 ✨{exp_gained} 经验\n"
                f"获得 💰{coins_gained} 金币"
                f"{level_up_text}"
            )
        
        elif turn_result.winner == "flee":
            yield event.plain_result(f"{turn_messages}")
        
        elif turn_result.winner == "enemy":
            self.pm.record_battle(user_id, is_win=False)
            yield event.plain_result(
                f"{turn_messages}\n\n"
                f"💀 战斗失败...\n"
                f"发送 /精灵 治疗 恢复精灵"
            )
        
        # 战斗结束后，恢复探索状态或清除状态
        if from_explore:
            exp_map = self.world_manager.get_active_map(user_id)
            if exp_map:
                # 恢复探索状态
                self.plugin.db.set_game_state(user_id, "exploring", {
                    "region_id": state_data.get("region_id", ""),
                    "region_name": state_data.get("region_name", "")
                })
                
                map_text = self.world_manager.render_map(exp_map)
                yield event.plain_result(
                    f"\n📍 继续探索中...\n\n"
                    f"{map_text}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💡 发送 \"{prefix}坐标\" 继续移动"
                )
            else:
                # 地图不存在，清除状态
                self.plugin.db.clear_game_state(user_id)
        else:
            # 非探索战斗，清除状态
            self.plugin.db.clear_game_state(user_id)

