"""
探索相关指令处理器
- 区域探索、地图移动、事件处理等
"""

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.message_components import Image
from astrbot.api import logger
from ..core.message_tracker import get_message_tracker, MessageType
# 不再需要 session_waiter，改用数据库状态 + 前缀触发
# from astrbot.core.utils.session_waiter import session_waiter, SessionController

from typing import TYPE_CHECKING, Optional


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

    async def _render_map_image(self, exp_map, region_name: str = "") -> Optional[bytes]:
        """
        渲染地图为图片
        
        Args:
            exp_map: 探索地图对象
            region_name: 区域名称
            
        Returns:
            图片字节数据，失败返回 None
        """
        try:
            from ..core.world import get_map_renderer
            
            # 获取天气信息
            weather_info = None
            if hasattr(exp_map, 'weather') and exp_map.weather:
                weather_data = self.wm.get_weather_info(exp_map.weather)
                if weather_data:
                    weather_info = {
                        "icon": weather_data.get("icon", ""),
                        "name": weather_data.get("name", "")
                    }
            
            # 异步渲染地图图片
            renderer = get_map_renderer()
            # 获取动作前缀用于帮助提示
            action_prefix = self.plugin.game_action_prefix
            
            image_bytes = await renderer.render_map_async(
                exp_map, 
                region_name=region_name,
                weather_info=weather_info,
                action_prefix=action_prefix
            )
            return image_bytes
            
        except Exception as e:
            logger.warning(f"地图图片渲染失败: {e}")
            return None

    async def _send_with_recall(self, event: AstrMessageEvent, 
                                  message_chain: list, msg_type: MessageType,
                                  recall_previous: bool = True) -> Optional[int]:
        """
        发送消息并追踪，支持撤回上一条同类型消息
        
        Args:
            event: 消息事件
            message_chain: 消息链（AstrBot 消息组件列表）
            msg_type: 消息类型（用于追踪）
            recall_previous: 是否撤回上一条同类型消息
            
        Returns:
            发送成功返回 message_id，失败返回 None
        """
        user_id = event.get_sender_id()
        tracker = get_message_tracker()
        
        # 尝试撤回上一条同类型消息
        if recall_previous:
            await tracker.recall_if_exists(user_id, msg_type, event)
        
        # 发送新消息并获取 message_id
        message_id = await self._send_and_get_id(event, message_chain)
        
        # 追踪新消息
        if message_id:
            tracker.track(
                user_id=user_id,
                message_id=message_id,
                msg_type=msg_type,
                platform=event.get_platform_name(),
                session_id=event.get_group_id() or user_id
            )
        
        return message_id
    
    async def _send_and_get_id(self, event: AstrMessageEvent, 
                                message_chain: list) -> Optional[int]:
        """
        发送消息并获取 message_id（底层实现）
        
        Args:
            event: 消息事件
            message_chain: 消息链
            
        Returns:
            message_id 或 None
        """
        try:
            platform_name = event.get_platform_name()
            
            # OneBot V11 (aiocqhttp) 平台
            if platform_name == "aiocqhttp":
                return await self._send_onebot(event, message_chain)
            
            # 其他平台：使用默认方式发送（无法获取 message_id）
            from astrbot.api.event import MessageChain
            await event.send(MessageChain(message_chain))
            return None
            
        except Exception as e:
            logger.warning(f"发送消息失败: {e}")
            return None
    
    async def _send_onebot(self, event: AstrMessageEvent, 
                           message_chain: list) -> Optional[int]:
        """
        OneBot V11 发送消息并获取 message_id
        
        Args:
            event: 消息事件
            message_chain: 消息链
            
        Returns:
            message_id 或 None
        """
        try:
            bot = getattr(event, 'bot', None)
            if not bot:
                return None
            
            # 转换消息链为 OneBot 格式
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
            from astrbot.api.event import MessageChain
            
            messages = await AiocqhttpMessageEvent._parse_onebot_json(MessageChain(message_chain))
            if not messages:
                return None
            
            # 发送消息并获取返回值
            group_id = event.get_group_id()
            if group_id:
                result = await bot.send_group_msg(group_id=int(group_id), message=messages)
            else:
                user_id = event.get_sender_id()
                result = await bot.send_private_msg(user_id=int(user_id), message=messages)
            
            # 提取 message_id
            if isinstance(result, dict):
                return result.get("message_id")
            return None
            
        except Exception as e:
            logger.debug(f"OneBot 发送消息失败: {e}")
            return None

    async def _send_map_image(self, event: AstrMessageEvent, exp_map, 
                               region_name: str = "", extra_text: str = "",
                               recall_previous: bool = True):
        """
        发送地图图片（异步生成器），支持撤回上一条地图消息
        
        Args:
            event: 消息事件
            exp_map: 探索地图对象
            region_name: 区域名称
            extra_text: 额外的文字信息（会在图片前发送）
            recall_previous: 是否撤回上一条地图消息
        """
        # 先发送额外文字（不追踪，不撤回）
        if extra_text:
            yield event.plain_result(extra_text)
        
        # 尝试渲染图片
        image_bytes = await self._render_map_image(exp_map, region_name=region_name)
        
        if image_bytes:
            # 成功渲染，发送图片并追踪
            message_chain = [Image.fromBytes(image_bytes)]
            message_id = await self._send_with_recall(
                event, message_chain, MessageType.MAP, recall_previous
            )
            
            # 如果发送失败（无法获取 message_id），使用 yield 兜底
            if message_id is None:
                # 可能是不支持的平台，使用传统方式
                yield event.chain_result([Image.fromBytes(image_bytes)])
        else:
            # 渲染失败，回退到文字地图（不追踪）
            map_text = self.wm.render_map(exp_map)
            yield event.plain_result(map_text)






    async def cmd_regions(self, event: AstrMessageEvent):
        """
        查看可探索区域
        指令: /精灵 区域
        """
        user_id = event.get_sender_id()

        player = await self.pm.get_player(user_id)
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
            can_enter, reason = await self.pm.can_enter_region(user_id, rid)
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

        player = await self.pm.get_player(user_id)
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
        prefix = self.plugin.game_action_prefix

        if active_map and not region_name:
            # 显示当前地图（图片）
            region_info = self.wm.get_region(active_map.region_id)
            region_display = region_info.get("name", "") if region_info else ""
            async for msg in self._send_map_image(event, active_map, region_name=region_display):
                yield msg
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
        can_enter, reason = await self.pm.can_enter_region(user_id, region_id)
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
        team = await self.pm.get_team(user_id)
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
        await self.pm.consume_stamina(user_id, stamina_cost)
        # 生成地图
        exp_map = self.wm.generate_map(
            region_id=region_id,
            player_id=user_id,
            player_level=player["level"]
        )

        # 显示地图（图片）
        region_display_name = region.get("name", region_id)
        yield event.plain_result(f"🗺️ 进入了【{region_display_name}】！")
        async for msg in self._send_map_image(event, exp_map, region_name=region_display_name):
            yield msg



        # 设置游戏状态为探索中（存储到数据库）
        self.plugin.db.set_game_state(user_id, "exploring", {
            "region_id": region_id,
            "region_name": region_display_name
        })

    async def handle_explore_action(self, event: AstrMessageEvent, user_id: str, action: str, state_data: dict):
        """
        处理前缀触发的探索操作
        
        Args:
            event: 消息事件
            user_id: 用户ID
            action: 去掉前缀后的操作内容（如 "B2", "离开", "地图"）
            state_data: 游戏状态数据
        """
        CellType, EventType = self._get_imports()
        prefix = self.plugin.game_action_prefix
        
        # 获取活跃地图
        exp_map = self.wm.get_active_map(user_id)
        if not exp_map:
            # 地图不存在，清除状态
            self.plugin.db.clear_game_state(user_id)
            yield event.plain_result("❌ 探索已结束，地图数据丢失")
            return
        
        # 离开地图
        if action in ["离开", "退出", "结束", "exit", "quit"]:
            result = self.wm.complete_exploration(user_id)
            
            # 发放奖励
            rewards = result.get("rewards", {})
            if rewards.get("coins", 0) > 0:
                await self.pm.add_currency(user_id, coins=rewards["coins"])
            if rewards.get("exp", 0) > 0:
                await self.pm.add_exp(user_id, rewards["exp"])
            
            # 清除游戏状态
            self.plugin.db.clear_game_state(user_id)
            
            yield event.plain_result(result["message"])
            return
        
        # 显示地图（图片）
        if action in ["地图", "map", "查看"]:
            region_name = state_data.get("region_name", "")
            async for msg in self._send_map_image(event, exp_map, region_name=region_name):
                yield msg
            return

        
        # 解析坐标
        coord = self.wm.parse_coordinate(action, exp_map)
        if not coord:
            yield event.plain_result(
                f"❓ 无效输入: {action}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"发送 \"{prefix}坐标\" 移动（如 \"{prefix}B2\"）\n"
                f"发送 \"{prefix}地图\" 查看当前地图\n"
                f"发送 \"{prefix}离开\" 结束探索"
            )
            return
        
        target_x, target_y = coord
        
        # 执行探索
        player_data = await self.pm.get_player(user_id)
        result = self.wm.explore_cell(
            player_id=user_id,
            target_x=target_x,
            target_y=target_y,
            player_level=player_data.get("level", 1) if player_data else 1
        )
        
        if not result.success:
            yield event.plain_result(f"❌ {result.message}")
            return
        
        # 处理探索结果
        if result.encounter_battle:
            # 遭遇战斗 - 切换到战斗状态
            yield event.plain_result(result.message)
            
            # 设置战斗状态
            self.plugin.db.set_game_state(user_id, "battling", {
                "monster_data": result.monster_data,
                "weather": exp_map.weather,
                "is_boss": result.is_boss,
                "boss_id": result.boss_id,
                "from_explore": True,  # 标记是从探索进入的战斗
                "region_id": state_data.get("region_id", ""),
                "region_name": state_data.get("region_name", "")
            })
            
            # 触发战斗开始
            async for resp in self.battle_handlers.start_battle_from_state(event, user_id):
                yield resp
            return
        
        # 非战斗结果 - 处理奖励
        if result.coins_gained > 0:
            await self.pm.add_currency(user_id, coins=result.coins_gained)
        
        for item in result.items_gained:
            item_id = item.get("item_id", "")
            amount = item.get("amount", 1)
            if item_id == "_diamonds":
                await self.pm.add_currency(user_id, diamonds=amount)
            elif item_id:
                await self.pm.add_item(user_id, item_id, amount)
        
        if result.exp_gained > 0:
            await self.pm.add_exp(user_id, result.exp_gained)
        
        # 处理事件效果
        if result.event_type == EventType.HEAL:
            await self.pm.heal_team(user_id)
        elif result.event_type == EventType.TRAP:
            # 简化处理：队伍受到伤害
            team = await self.pm.get_team(user_id)
            for m_data in team:
                if m_data.get("current_hp", 0) > 0:
                    damage = int(m_data["max_hp"] * 0.15)
                    m_data["current_hp"] = max(1, m_data["current_hp"] - damage)
                    await self.pm.update_monster_from_dict(m_data["instance_id"], m_data)
        
        # 显示更新后的地图（图片）
        exp_map = self.wm.get_active_map(user_id)
        if exp_map:
            region_name = state_data.get("region_name", "")
            yield event.plain_result(result.message)
            async for msg in self._send_map_image(event, exp_map, region_name=region_name):
                yield msg



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

        # 使用图片渲染地图
        async for result in self._send_map_image(event, exp_map):
            yield result


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
            await self.pm.add_currency(user_id, coins=rewards["coins"])
        if rewards.get("exp", 0) > 0:
            await self.pm.add_exp(user_id, rewards["exp"])

        yield event.plain_result(result["message"])


