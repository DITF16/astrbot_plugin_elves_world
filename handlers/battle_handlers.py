"""
战斗相关指令处理器
- 战斗、捕捉、技能使用等
"""

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger
# 不再需要 session_waiter，改用数据库状态 + 前缀触发
# from astrbot.core.utils.session_waiter import session_waiter, SessionController

from typing import TYPE_CHECKING, Dict, Optional
from ..core.message_tracker import get_message_tracker, MessageType

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
        self.explore_handlers = None  # 稍后注入，用于复用地图渲染

    def set_explore_handlers(self, explore_handlers):
        """注入探索处理器（避免循环引用）"""
        self.explore_handlers = explore_handlers

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



    async def _send_battle_message(self, event: AstrMessageEvent, text: str,
                                    recall_previous: bool = True) -> Optional[int]:
        """
        发送战斗消息并追踪，支持撤回上一条战斗消息
        
        Args:
            event: 消息事件
            text: 消息文本
            recall_previous: 是否撤回上一条战斗消息
            
        Returns:
            发送成功返回 message_id，失败返回 None
        """
        user_id = event.get_sender_id()
        tracker = get_message_tracker()
        
        # 尝试撤回上一条战斗消息
        if recall_previous:
            await tracker.recall_if_exists(user_id, MessageType.BATTLE, event)
        
        # 发送新消息并获取 message_id
        message_id = await self._send_and_get_id(event, text)
        
        # 追踪新消息
        if message_id:
            tracker.track(
                user_id=user_id,
                message_id=message_id,
                msg_type=MessageType.BATTLE,
                platform=event.get_platform_name(),
                session_id=event.get_group_id() or user_id
            )
        
        return message_id
    
    async def _send_and_get_id(self, event: AstrMessageEvent, text: str) -> Optional[int]:
        """
        发送文本消息并获取 message_id
        
        Args:
            event: 消息事件
            text: 消息文本
            
        Returns:
            message_id 或 None
        """
        try:
            platform_name = event.get_platform_name()
            
            # OneBot V11 (aiocqhttp) 平台
            if platform_name == "aiocqhttp":
                return await self._send_onebot_text(event, text)
            
            # 其他平台：无法获取 message_id
            return None
            
        except Exception as e:
            logger.debug(f"发送消息失败: {e}")
            return None
    
    async def _send_onebot_text(self, event: AstrMessageEvent, text: str) -> Optional[int]:
        """
        OneBot V11 发送文本消息并获取 message_id
        """
        try:
            bot = getattr(event, 'bot', None)
            if not bot:
                return None
            
            messages = [{"type": "text", "data": {"text": text}}]
            
            group_id = event.get_group_id()
            if group_id:
                result = await bot.send_group_msg(group_id=int(group_id), message=messages)
            else:
                user_id = event.get_sender_id()
                result = await bot.send_private_msg(user_id=int(user_id), message=messages)
            
            if isinstance(result, dict):
                return result.get("message_id")
            return None
            
        except Exception as e:
            logger.debug(f"OneBot 发送消息失败: {e}")
            return None
    
    async def _recall_map_message(self, event: AstrMessageEvent, user_id: str) -> bool:
        """
        撤回地图消息（进入战斗时调用）
        
        Args:
            event: 消息事件
            user_id: 用户ID
            
        Returns:
            是否成功撤回
        """
        tracker = get_message_tracker()
        return await tracker.recall_if_exists(user_id, MessageType.MAP, event)
    
    async def _recall_battle_message(self, event: AstrMessageEvent, user_id: str) -> bool:
        """
        撤回战斗消息（战斗结束时调用）
        
        Args:
            event: 消息事件
            user_id: 用户ID
            
        Returns:
            是否成功撤回
        """
        tracker = get_message_tracker()
        return await tracker.recall_if_exists(user_id, MessageType.BATTLE, event)



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

        player = await self.pm.get_player(user_id)
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
        team = await self.pm.get_team(user_id)
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

        await self.pm.consume_stamina(user_id, stamina_cost)

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

        team = await self.pm.get_team(user_id)

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
                await self.pm.update_monster_from_dict(
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
            exp_buff = await self.pm.get_buff_multiplier(user_id, "exp_rate")
            coin_buff = await self.pm.get_buff_multiplier(user_id, "coin_rate")
            exp_gained = int(battle.exp_gained * self.plugin.exp_multiplier * exp_buff)
            coins_gained = int(battle.coins_gained * self.plugin.coin_multiplier * coin_buff)

            # 发放奖励
            await self.pm.add_currency(user_id, coins=coins_gained)
            await self.pm.record_battle(user_id, is_win=True)

            # 精灵获得经验
            team = await self.pm.get_team(user_id)
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

                    await self.pm.update_monster(monster)

            # 更新探索地图状态
            exp_map = self.world_manager.get_active_map(user_id)
            if exp_map:
                if battle.battle_type == BattleType.BOSS:
                    self.world_manager.mark_boss_defeated(user_id)
                    await self.pm.record_boss_clear(user_id, battle.boss_id)
                else:
                    self.world_manager.mark_monster_defeated(user_id)
            
            level_up_text = "\n".join(level_up_messages)
            if level_up_text:
                level_up_text = "\n" + level_up_text
            
            # 🔄 战斗结束，撤回最后的战斗消息，只保留战斗结果
            await self._recall_battle_message(event, user_id)
            


            yield event.plain_result(
                f"{turn_messages}\n\n"
                f"🏆 战斗胜利！\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"获得 ✨{exp_gained} 经验\n"
                f"获得 💰{coins_gained} 金币"
                f"{level_up_text}"
            )
        
        elif turn_result.winner == "flee":
            # 🔄 战斗结束，撤回最后的战斗消息
            await self._recall_battle_message(event, user_id)
            yield event.plain_result(f"{turn_messages}")
        

        
        elif turn_result.winner == "enemy":
            await self.pm.record_battle(user_id, is_win=False)
            await self._recall_battle_message(event, user_id)
            yield event.plain_result(
                f"{turn_messages}\n\n"
                f"💀 战斗失败...\n"
                f"发送 /精灵 治疗 恢复精灵"
            )



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
        team = await self.pm.get_team(user_id)
        
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
        
        # 🔄 进入战斗时撤回地图消息
        await self._recall_map_message(event, user_id)
        
        # 发送战斗开始消息并追踪
        battle_start_text = (
            f"{battle_type_text}\n\n"
            f"{battle_text}\n\n"
            f"{skill_menu}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"输入技能序号(1-4)攻击\n"
            f"输入「{prefix}逃跑」逃离 | 输入「{prefix}捕捉」捕捉"
        )
        
        message_id = await self._send_battle_message(event, battle_start_text, recall_previous=False)
        if message_id is None:
            # 平台不支持获取 message_id，使用传统方式
            yield event.plain_result(battle_start_text)

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
        

        # 使用物品（格式: 用 物品名 或 use 物品名）
        elif action.startswith("用 ") or action.startswith("用") or action.lower().startswith("use "):
            # 解析物品名
            if action.lower().startswith("use "):
                item_name = action[4:].strip()
            elif action.startswith("用 "):
                item_name = action[2:].strip()
            else:
                item_name = action[1:].strip()
            
            if not item_name:
                # 显示可用物品列表
                inventory = await self.pm.get_inventory(user_id)
                usable_items = []
                for item_id, count in inventory.items():
                    item = self.config.get_item("items", item_id)
                    if item and item.get("type") in ["heal", "cure_status", "full_restore"]:
                        usable_items.append((item, count))
                
                if not usable_items:
                    yield event.plain_result("❌ 你没有可在战斗中使用的物品")
                    return
                
                lines = ["🎒 可使用的物品：", "━━━━━━━━━━━━━━━━━━━━"]
                for item, count in usable_items:
                    lines.append(f"• {item['name']} x{count}")
                lines.append(f"\n发送 \"{prefix}用 物品名\" 使用物品")
                yield event.plain_result("\n".join(lines))
                return
            
            # 查找物品
            item = self.config.get_item("items", item_name)
            if not item:
                for k, v in self.config.items.items():
                    if item_name in k or item_name in v.get("name", ""):
                        item = v
                        break
            
            if not item:
                yield event.plain_result(f"❌ 找不到物品: {item_name}")
                return
            
            # 检查是否拥有该物品
            if not await self.pm.has_item(user_id, item["id"]):
                yield event.plain_result(f"❌ 你没有 {item['name']}")
                return
            
            # 检查物品是否可在战斗中使用
            item_type = item.get("type", "")
            if item_type not in ["heal", "cure_status", "full_restore"]:
                yield event.plain_result(f"❌ {item['name']} 不能在战斗中使用")
                return
            
            # 扣除物品
            await self.pm.use_item(user_id, item["id"])
            
            # 构建使用物品的行动
            battle_action = BattleAction(
                action_type=ActionType.ITEM,
                actor_id=player_monster.get("instance_id", ""),
                item_id=item["id"]
            )
        
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
                    yield event.plain_result(f"❌ 请输入正确的序号，如: \"{prefix}换 2\"")
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
                lines.append(f"发送 \"{prefix}换 序号\" 切换，如: \"{prefix}换 2\"")
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
                f"发送 \"{prefix}用 物品名\" 使用物品\n"
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
            await self.pm.update_monster_from_dict(m_data.get("instance_id", ""), m_data)
        
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
        
        # 显示战斗状态（撤回上一条战斗消息，发送新状态）
        battle_text = self.battle_system.get_battle_status_text(battle)
        skill_menu = self.battle_system.get_skill_menu_text(battle)
        
        battle_status_text = (
            f"{turn_messages}\n\n"
            f"{battle_text}\n\n"
            f"{skill_menu}"
        )
        
        # 🔄 撤回上一条战斗消息，发送新状态并追踪
        message_id = await self._send_battle_message(event, battle_status_text, recall_previous=True)
        if message_id is None:
            # 平台不支持，使用传统方式
            yield event.plain_result(battle_status_text)


    async def _handle_battle_end_with_state(self, event, user_id, umo, battle, turn_result, turn_messages, state_data):
        """处理战斗结束（带状态管理）"""
        MonsterInstance, BattleState, BattleAction, ActionType, BattleType = self._get_imports()
        
        self.clear_active_battle(umo)
        prefix = self.plugin.game_action_prefix
        from_explore = state_data.get("from_explore", False)
        
        if turn_result.winner == "player":
            # 胜利
            exp_buff = await self.pm.get_buff_multiplier(user_id, "exp_rate")
            coin_buff = await self.pm.get_buff_multiplier(user_id, "coin_rate")
            exp_gained = int(battle.exp_gained * self.plugin.exp_multiplier * exp_buff)
            coins_gained = int(battle.coins_gained * self.plugin.coin_multiplier * coin_buff)
            
            # 发放奖励
            await self.pm.add_currency(user_id, coins=coins_gained)
            await self.pm.record_battle(user_id, is_win=True)
            
            # 精灵获得经验
            team = await self.pm.get_team(user_id)
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
                    
                    await self.pm.update_monster(monster)
            
            # 更新探索地图状态
            exp_map = self.world_manager.get_active_map(user_id)
            if exp_map:
                if battle.battle_type == BattleType.BOSS:
                    self.world_manager.mark_boss_defeated(user_id)
                    await self.pm.record_boss_clear(user_id, battle.boss_id)
                else:
                    self.world_manager.mark_monster_defeated(user_id)
            
            level_up_text = "\n".join(level_up_messages)
            if level_up_text:
                level_up_text = "\n" + level_up_text

            
            # 🔄 战斗结束，撤回最后的战斗消息，只保留战斗结果
            await self._recall_battle_message(event, user_id)
            

            yield event.plain_result(
                f"{turn_messages}\n\n"
                f"🏆 战斗胜利！\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"获得 ✨{exp_gained} 经验\n"
                f"获得 💰{coins_gained} 金币"
                f"{level_up_text}"
            )
        
        elif turn_result.winner == "flee":
            # 🔄 战斗结束，撤回最后的战斗消息
            await self._recall_battle_message(event, user_id)
            yield event.plain_result(f"{turn_messages}")
        
        elif turn_result.winner == "enemy":
            await self.pm.record_battle(user_id, is_win=False)
            # 🔄 战斗结束，撤回最后的战斗消息
            await self._recall_battle_message(event, user_id)
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
                
                region_name = state_data.get("region_name", "")
                
                # 复用 explore_handlers 的图片渲染方法
                if self.explore_handlers:
                    async for result in self.explore_handlers._send_map_image(
                        event, exp_map, 
                        region_name=region_name,
                        extra_text=f"\n📍 继续探索中..."
                    ):
                        yield result
                else:
                    # 回退到文字地图（explore_handlers 未注入时）
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

