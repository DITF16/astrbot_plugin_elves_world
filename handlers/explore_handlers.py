"""
探索相关指令处理器
- 区域探索、地图移动、事件处理等
"""

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger
from astrbot.core.utils.session_waiter import session_waiter, SessionController

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import MonsterGamePlugin


class ExploreHandlers:
    """探索相关指令处理器"""

    def __init__(self, plugin: "MonsterGamePlugin"):
        self.plugin = plugin
        self.config = plugin.game_config
        self.pm = plugin.player_manager
        self.wm = plugin.world_manager
        self.battle_handlers = None  # 稍后注入

    def set_battle_handlers(self, battle_handlers):
        """注入战斗处理器（避免循环引用）"""
        self.battle_handlers = battle_handlers

    def _get_imports(self):
        from ..core import CellType, EventType
        return CellType, EventType

    async def cmd_regions(self, event: AstrMessageEvent):
        """
        查看可探索区域
        指令: /精灵 区域
        """
        user_id = event.get_sender_id()

        player = self.pm.get_player(user_id)
        if not player:
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        regions = self.wm.get_all_regions()

        if not regions:
            yield event.plain_result("❌ 暂无可探索区域")
            return

        lines = ["🗺️ 可探索区域", "━━━━━━━━━━━━━━━━━━━━"]

        for rid, region in regions.items():
            name = region.get("name", rid)
            level_range = region.get("level_range", [1, 10])
            stamina = region.get("stamina_cost", 10)
            description = region.get("description", "")[:20]

            # 检查是否可进入
            can_enter, reason = self.pm.can_enter_region(user_id, rid)
            lock_icon = "🔓" if can_enter else "🔒"

            lines.append(f"{lock_icon} {name}")
            lines.append(f"　 Lv.{level_range[0]}-{level_range[1]} | ⚡{stamina}")
            if not can_enter:
                lines.append(f"　 ({reason})")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("发送 /精灵 探索 [区域名] 进入")

        yield event.plain_result("\n".join(lines))

    async def cmd_explore(self, event: AstrMessageEvent, region_name: str = ""):
        """
        探索区域
        指令:
        /精灵 探索 - 查看当前地图
        /精灵 探索 [区域名] - 进入区域
        """
        CellType, EventType = self._get_imports()

        user_id = event.get_sender_id()
        umo = event.unified_msg_origin

        player = self.pm.get_player(user_id)
        if not player:
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        # 检查是否在战斗中
        if self.battle_handlers and self.battle_handlers.get_active_battle(umo):
            yield event.plain_result(
                "⚔️ 你正在战斗中！\n"
                "请先完成战斗"
            )
            return

        # 检查是否有活跃地图
        active_map = self.wm.get_active_map(user_id)

        if active_map and not region_name:
            # 显示当前地图
            map_text = self.wm.render_map(active_map)
            yield event.plain_result(map_text)

            # 进入探索会话
            async for _ in self._exploration_session(event, user_id, umo):
                pass
            return

        if not region_name:
            # 显示区域列表
            async for result in self.cmd_regions(event):
                yield result
            return

        # 查找区域（支持区域名或ID）
        region_id = None
        for rid, region in self.wm.get_all_regions().items():
            if rid == region_name or region.get("name") == region_name:
                region_id = rid
                break

        if not region_id:
            yield event.plain_result(
                f"❌ 未找到区域: {region_name}\n"
                f"发送 /精灵 区域 查看所有区域"
            )
            return

        region = self.wm.get_region(region_id)

        # 检查进入条件
        can_enter, reason = self.pm.can_enter_region(user_id, region_id)
        if not can_enter:
            yield event.plain_result(f"🔒 无法进入: {reason}")
            return

        # 检查体力
        stamina_cost = region.get("stamina_cost", 10)
        if player["stamina"] < stamina_cost:
            yield event.plain_result(
                f"❌ 体力不足！\n"
                f"需要 ⚡{stamina_cost}，当前 ⚡{player['stamina']}"
            )
            return

        # 检查队伍
        team = self.pm.get_team(user_id)
        if not team:
            yield event.plain_result(
                "❌ 队伍为空！\n"
                "发送 /精灵 队伍 设置 组建队伍"
            )
            return

        available_team = [m for m in team if m.get("current_hp", 0) > 0]
        if not available_team:
            yield event.plain_result(
                "❌ 队伍中没有可战斗的精灵！\n"
                "发送 /精灵 治疗 恢复精灵"
            )
            return

        # 如果有旧地图，先结算
        if active_map:
            self.wm.complete_exploration(user_id)

        # 消耗体力
        self.pm.consume_stamina(user_id, stamina_cost)

        # 生成地图
        exp_map = self.wm.generate_map(
            region_id=region_id,
            player_id=user_id,
            player_level=player["level"]
        )

        # 显示地图
        region_name = region.get("name", region_id)
        map_text = self.wm.render_map(exp_map)

        yield event.plain_result(
            f"🗺️ 进入了【{region_name}】！\n\n"
            f"{map_text}"
        )

        # 进入探索会话
        async for _ in self._exploration_session(event, user_id, umo):
            pass

    async def _exploration_session(self, event: AstrMessageEvent, user_id: str, umo: str):
        """探索会话"""
        CellType, EventType = self._get_imports()

        @session_waiter(timeout=self.plugin.explore_timeout, record_history_chains=False)
        async def explore_loop(controller: SessionController, ev: AstrMessageEvent):
            msg = ev.message_str.strip()

            exp_map = self.wm.get_active_map(user_id)
            if not exp_map:
                await ev.send(ev.plain_result("❌ 探索已结束"))
                controller.stop()
                return

            # 离开地图
            if msg in ["离开", "退出", "结束", "exit", "quit"]:
                result = self.wm.complete_exploration(user_id)

                # 发放奖励
                rewards = result.get("rewards", {})
                if rewards.get("coins", 0) > 0:
                    self.pm.add_currency(user_id, coins=rewards["coins"])
                if rewards.get("exp", 0) > 0:
                    self.pm.add_exp(user_id, rewards["exp"])

                await ev.send(ev.plain_result(result["message"]))
                controller.stop()
                return

            # 显示地图
            if msg in ["地图", "map", "查看"]:
                map_text = self.wm.render_map(exp_map)
                await ev.send(ev.plain_result(map_text))
                controller.keep(timeout=self.plugin.explore_timeout, reset_timeout=True)
                return

            # 解析坐标
            coord = self.wm.parse_coordinate(msg, exp_map)
            if not coord:
                await ev.send(ev.plain_result(
                    "❓ 无效输入\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "输入坐标移动，如: A1、B2\n"
                    "输入「地图」查看当前地图\n"
                    "输入「离开」结束探索"
                ))
                controller.keep(timeout=self.plugin.explore_timeout, reset_timeout=True)
                return

            target_x, target_y = coord

            # 执行探索
            result = self.wm.explore_cell(
                player_id=user_id,
                target_x=target_x,
                target_y=target_y,
                player_level=self.pm.get_player(user_id).get("level", 1)
            )

            if not result.success:
                await ev.send(ev.plain_result(f"❌ {result.message}"))
                controller.keep(timeout=self.plugin.explore_timeout, reset_timeout=True)
                return

            # 处理探索结果
            if result.encounter_battle:
                # 遭遇战斗
                await ev.send(ev.plain_result(result.message))

                # 暂停探索会话，进入战斗
                controller.stop()

                # 触发战斗
                if self.battle_handlers:
                    await self.battle_handlers.start_battle_from_explore(
                        event=ev,
                        user_id=user_id,
                        umo=umo,
                        monster_data=result.monster_data,
                        weather=exp_map.weather,
                        is_boss=result.is_boss,
                        boss_id=result.boss_id
                    )
                return

            # 非战斗结果 - 处理奖励
            if result.coins_gained > 0:
                self.pm.add_currency(user_id, coins=result.coins_gained)

            for item in result.items_gained:
                item_id = item.get("item_id", "")
                amount = item.get("amount", 1)
                if item_id == "_diamonds":
                    self.pm.add_currency(user_id, diamonds=amount)
                elif item_id:
                    self.pm.add_item(user_id, item_id, amount)

            if result.exp_gained > 0:
                self.pm.add_exp(user_id, result.exp_gained)

            # 处理事件效果
            if result.event_type == EventType.HEAL:
                healed = self.pm.heal_team(user_id)
            elif result.event_type == EventType.TRAP:
                # 简化处理：队伍受到伤害
                team = self.pm.get_team(user_id)
                for m_data in team:
                    if m_data.get("current_hp", 0) > 0:
                        damage = int(m_data["max_hp"] * 0.15)
                        m_data["current_hp"] = max(1, m_data["current_hp"] - damage)
                        self.pm.update_monster_from_dict(m_data["instance_id"], m_data)

            # 检查是否到达出口
            if result.can_exit:
                await ev.send(ev.plain_result(result.message))
                controller.keep(timeout=self.plugin.explore_timeout, reset_timeout=True)
                return

            # 显示更新后的地图
            exp_map = self.wm.get_active_map(user_id)
            if exp_map:
                map_text = self.wm.render_map(exp_map)
                await ev.send(ev.plain_result(f"{result.message}\n\n{map_text}"))

            controller.keep(timeout=self.plugin.explore_timeout, reset_timeout=True)

        try:
            await explore_loop(event)
        except TimeoutError:
            self.wm.clear_active_map(user_id)
            yield event.plain_result("⏰ 探索超时，已自动退出")
        finally:
            event.stop_event()

    async def cmd_map(self, event: AstrMessageEvent):
        """
        查看当前地图
        指令: /精灵 地图
        """
        user_id = event.get_sender_id()

        exp_map = self.wm.get_active_map(user_id)
        if not exp_map:
            yield event.plain_result(
                "❌ 你当前没有在探索中\n"
                "发送 /精灵 探索 开始探索"
            )
            return

        map_text = self.wm.render_map(exp_map)
        yield event.plain_result(map_text)

    async def cmd_leave(self, event: AstrMessageEvent):
        """
        离开当前探索
        指令: /精灵 离开
        """
        user_id = event.get_sender_id()

        exp_map = self.wm.get_active_map(user_id)
        if not exp_map:
            yield event.plain_result("❌ 你当前没有在探索中")
            return

        result = self.wm.complete_exploration(user_id)

        # 发放奖励
        rewards = result.get("rewards", {})
        if rewards.get("coins", 0) > 0:
            self.pm.add_currency(user_id, coins=rewards["coins"])
        if rewards.get("exp", 0) > 0:
            self.pm.add_exp(user_id, rewards["exp"])

        yield event.plain_result(result["message"])


