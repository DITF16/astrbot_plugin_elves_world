"""
玩家相关指令处理器
- 注册、信息查看、治疗、排行榜等
"""

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger
from astrbot.core.utils.session_waiter import session_waiter, SessionController

from typing import TYPE_CHECKING
import random

if TYPE_CHECKING:
    from ..main import MonsterGamePlugin


class PlayerHandlers:
    """玩家相关指令处理器"""

    def __init__(self, plugin: "MonsterGamePlugin"):
        self.plugin = plugin
        self.config = plugin.game_config  # 游戏配置（精灵/技能等）
        self.pm = plugin.player_manager
        self.db = plugin.db

    def _get_monster_instance_class(self):
        """延迟导入避免循环引用"""
        from ..core import MonsterInstance
        return MonsterInstance

    async def cmd_start(self, event: AstrMessageEvent):
        """
        注册指令
        指令: /精灵 注册
        """
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()

        if await self.pm.player_exists(user_id):
            yield event.plain_result(
                "🎮 你已经是训练师了！\n"
                "发送 /精灵 帮助 查看所有指令"
            )
            return

        # 创建玩家（使用插件配置的最大体力值）
        await self.pm.create_player(user_id, user_name)

        # 更新为配置的最大体力
        await self.pm.update_player(user_id, {"max_stamina": self.plugin.max_stamina})

        yield event.plain_result(
            f"🎉 欢迎来到精灵世界，{user_name}！\n\n"
            "请选择你的初始伙伴：\n"
            "━━━━━━━━━━━━\n"
            "1️⃣ 烈焰龙 🔥 火系 - 攻击型\n"
            "2️⃣ 水灵精 💧 水系 - 平衡型\n"
            "3️⃣ 青叶狐 🌿 草系 - 速度型\n"
            "━━━━━━━━━━━━\n"
            "请回复 1、2 或 3"
        )

        MonsterInstance = self._get_monster_instance_class()

        @session_waiter(timeout=60, record_history_chains=False, session_id=user_id)
        async def choose_starter(controller: SessionController, ev: AstrMessageEvent):
            choice = ev.message_str.strip()

            starter_map = {
                "1": "烈焰龙",
                "2": "水灵精",
                "3": "青叶狐"
            }

            if choice not in starter_map:
                await ev.send(ev.plain_result("请回复 1、2 或 3 选择你的伙伴~"))
                controller.keep(timeout=60, reset_timeout=True)
                return

            template_id = starter_map[choice]
            template = self.config.get_item("monsters", template_id)

            if not template:
                await ev.send(ev.plain_result("❌ 精灵数据异常，请联系管理员"))
                controller.stop()
                return

            # 创建精灵实例
            monster = MonsterInstance.from_template(
                template=template,
                level=5,
                config_manager=self.config,
                trainer_id=user_id,
                trainer_name=user_name,
                caught_region="starter"
            )

            # 添加到背包并设为队伍
            await self.pm.add_monster(user_id, monster)
            await self.pm.set_team(user_id, [monster.instance_id])

            await ev.send(ev.plain_result(
                f"🎊 太棒了！{template['name']} 成为了你的伙伴！\n\n"
                f"{monster.get_summary(self.config)}\n\n"
                "━━━━━━━━━━━━\n"
                "发送 /精灵 背包 查看你的精灵\n"
                "发送 /精灵 探索 开始冒险\n"
                "发送 /精灵 帮助 查看更多"
            ))
            controller.stop()

        try:
            await choose_starter(event)
        except TimeoutError:
            yield event.plain_result("⏰ 选择超时啦，请重新发送 /精灵 注册")
        finally:
            event.stop_event()


    async def cmd_info(self, event: AstrMessageEvent):
        """
        查看个人信息
        指令: /精灵 我
        """
        user_id = event.get_sender_id()

        if not await self.pm.player_exists(user_id):
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册 开始游戏")
            return

        info_text = await self.pm.get_player_info_text(user_id)
        yield event.plain_result(info_text)

    async def cmd_heal(self, event: AstrMessageEvent):
        """
        治疗所有精灵
        指令: /精灵 治疗
        """
        user_id = event.get_sender_id()

        player = await self.pm.get_player(user_id)
        if not player:
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        # 使用插件配置的治疗费用
        heal_cost = self.plugin.heal_cost

        if player["coins"] < heal_cost:
            yield event.plain_result(
                f"❌ 金币不足！\n"
                f"治疗需要 {heal_cost} 金币\n"
                f"当前金币: {player['coins']}"
            )
            return

        healed = await self.pm.heal_all_monsters(user_id)

        if healed == 0:
            yield event.plain_result("💚 你的精灵都很健康，不需要治疗~")
            return

        await self.pm.spend_coins(user_id, heal_cost)
        yield event.plain_result(
            f"💚 治疗完成！\n"
            f"已恢复 {healed} 只精灵的HP和状态\n"
            f"消耗 {heal_cost} 金币"
        )

    async def cmd_rank(self, event: AstrMessageEvent, rank_type: str = "胜场"):
        """
        查看排行榜
        指令: /精灵 排行 [类型]
        类型: 胜场/等级/金币
        """
        type_map = {
            "胜场": "wins",
            "胜利": "wins",
            "等级": "level",
            "金币": "coins",
            "钱": "coins",
        }

        order_by = type_map.get(rank_type, "wins")
        text = await self.pm.get_leaderboard_text(order_by, limit=10)
        yield event.plain_result(text)


    async def cmd_help(self, event: AstrMessageEvent):
        """
        显示帮助
        指令: /精灵 帮助
        """
        help_text = """
🎮 精灵对战游戏
━━━━━━━━━━━━

📌 基础指令
/精灵 注册 - 成为训练师
/精灵 我 - 查看个人信息
/精灵 背包 - 查看精灵列表
/精灵 详情 [序号] - 精灵详细信息
/精灵 队伍 - 管理出战队伍
/精灵 治疗 - 恢复所有精灵

📌 冒险指令
/精灵 探索 - 进入探索地图
/精灵 区域 - 查看可探索区域
/精灵 战斗 - 快速野外战斗

📌 养成指令
/精灵 进化 - 进化精灵
/精灵 改名 [序号] [新名] - 给精灵起昵称

📌 其他
/精灵 签到 - 每日签到
/精灵 排行 - 查看排行榜
/精灵 帮助 - 显示本帮助

━━━━━━━━━━━━
💡 探索时输入坐标(如A1)移动
💡 战斗时输入技能序号攻击
"""
        yield event.plain_result(help_text)

    async def cmd_sign(self, event: AstrMessageEvent):
        """
        每日签到
        指令: /精灵 签到
        """
        user_id = event.get_sender_id()

        # 检查是否启用签到
        if not self.plugin.daily_reward_enabled:
            yield event.plain_result("❌ 签到功能已关闭")
            return

        player = await self.pm.get_player(user_id)
        if not player:
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        last_sign = player.get("last_daily_reward")

        if last_sign == today:
            yield event.plain_result("📅 今天已经签到过啦，明天再来吧~")
            return

        # 使用插件配置的签到奖励
        coins = random.randint(self.plugin.daily_coins_min, self.plugin.daily_coins_max)
        exp = random.randint(self.plugin.daily_exp_min, self.plugin.daily_exp_max)
        stamina = self.plugin.daily_stamina_reward

        await self.pm.add_currency(user_id, coins=coins)
        await self.pm.add_exp(user_id, exp)
        await self.pm.restore_stamina(user_id, stamina)
        await self.pm.update_player(user_id, {"last_daily_reward": today})

        yield event.plain_result(
            f"📅 签到成功！\n"
            f"━━━━━━━━━━━━\n"
            f"💰 金币 +{coins}\n"
            f"✨ 经验 +{exp}\n"
            f"⚡ 体力 +{stamina}\n"
            f"━━━━━━━━━━━━\n"
            f"明天继续签到有惊喜哦~"
        )

    # ==================== 商店系统 ====================

    def _get_currency_icon(self, currency: str) -> str:
        """获取货币图标"""
        return "💎" if currency == "diamonds" else "💰"

    def _get_item_type_name(self, item_type: str) -> str:
        """获取物品类型名称"""
        type_names = {
            "capture": "捕捉", "heal": "治疗", "revive": "复活",
            "evolution": "进化", "stamina": "体力", "exp": "经验",
            "buff": "增益", "tool": "道具", "gift": "礼包", "material": "材料",
            "special": "特殊", "subscription": "订阅",
        }
        return type_names.get(item_type, "其他")

    async def cmd_shop(self, event: AstrMessageEvent, category: str = ""):
        """
        查看商店
        指令: /精灵 商店 [分类]
        """
        user_id = event.get_sender_id()
        player = await self.pm.get_player(user_id)
        if not player:
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        # 获取所有可购买物品
        all_items = self.config.items
        shop_items = {k: v for k, v in all_items.items()
                      if v.get("shop_available", False) and v.get("price", 0) > 0}

        if not shop_items:
            yield event.plain_result("🏪 商店暂时没有商品出售~")
            return

        # 分类筛选
        category_map = {
            "精灵球": "capture", "球": "capture", "药水": "heal", "治疗": "heal",
            "复活": "revive", "进化石": "evolution", "进化": "evolution",
            "体力": "stamina", "经验": "exp", "糖果": "exp",
            "增益": "buff", "护符": "buff", "道具": "tool", "礼包": "gift",
        }
        filter_type = category_map.get(category, "")
        if filter_type:
            shop_items = {k: v for k, v in shop_items.items() if v.get("type") == filter_type}
            if not shop_items:
                yield event.plain_result(f"🏪 没有找到 [{category}] 类型的商品")
                return

        # 按货币类型分组
        coins_items = [v for v in shop_items.values() if v.get("currency", "coins") == "coins"]
        diamonds_items = [v for v in shop_items.values() if v.get("currency") == "diamonds"]

        text = "🏪 精灵商店\n━━━━━━━━━━━━\n"
        text += f"💰 金币: {player['coins']}  💎 钻石: {player['diamonds']}\n"
        text += "━━━━━━━━━━━━\n"

        if coins_items:
            text += "\n💰 【金币商品】\n"
            for item in sorted(coins_items, key=lambda x: x.get("price", 0)):
                stars = "★" * item.get("rarity", 1)
                text += f"  {stars} {item['name']} - 💰{item['price']}\n"

        if diamonds_items:
            text += "\n💎 【钻石商品】\n"
            for item in sorted(diamonds_items, key=lambda x: x.get("price", 0)):
                stars = "★" * item.get("rarity", 1)
                text += f"  {stars} {item['name']} - 💎{item['price']}\n"

        text += "\n━━━━━━━━━━━━\n"
        text += "💡 购买: /精灵 购买 物品名 [数量]\n"
        text += "💡 分类: 精灵球/药水/进化石/体力/经验/增益/道具/礼包"
        yield event.plain_result(text)

    async def cmd_buy(self, event: AstrMessageEvent, item_name: str = "", amount: int = 1):
        """
        购买物品
        指令: /精灵 购买 物品名 [数量]
        """
        user_id = event.get_sender_id()
        player = await self.pm.get_player(user_id)
        if not player:
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        if not item_name:
            yield event.plain_result("❌ 请指定要购买的物品\n用法: /精灵 购买 物品名 [数量]")
            return

        if amount < 1 or amount > 99:
            yield event.plain_result("❌ 购买数量必须在1-99之间")
            return

        # 查找物品（支持模糊匹配）
        item = self.config.get_item("items", item_name)
        if not item:
            for k, v in self.config.items.items():
                if item_name in k or item_name in v.get("name", ""):
                    item = v
                    break

        if not item:
            yield event.plain_result(f"❌ 找不到物品: {item_name}")
            return

        if not item.get("shop_available", False) or item.get("price", 0) <= 0:
            yield event.plain_result(f"❌ {item['name']} 不在商店出售")
            return

        currency = item.get("currency", "coins")
        total_cost = item["price"] * amount

        # 检查并扣除货币
        if currency == "diamonds":
            if player["diamonds"] < total_cost:
                yield event.plain_result(f"❌ 钻石不足！需要💎{total_cost}，拥有💎{player['diamonds']}")
                return
            await self.pm.spend_diamonds(user_id, total_cost)
        else:
            if player["coins"] < total_cost:
                yield event.plain_result(f"❌ 金币不足！需要💰{total_cost}，拥有💰{player['coins']}")
                return
            await self.pm.spend_coins(user_id, total_cost)

        # 添加物品
        new_count = await self.pm.add_item(user_id, item["id"], amount)
        icon = self._get_currency_icon(currency)
        yield event.plain_result(
            f"🛒 购买成功！\n━━━━━━━━━━━━\n"
            f"物品: {item['name']} x{amount}\n"
            f"花费: {icon}{total_cost}\n"
            f"当前持有: {new_count}个"
        )

    async def cmd_sell(self, event: AstrMessageEvent, item_name: str = "", amount: int = 1):
        """
        出售物品
        指令: /精灵 出售 物品名 [数量]
        """
        user_id = event.get_sender_id()
        player = await self.pm.get_player(user_id)
        if not player:
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        if not item_name:
            yield event.plain_result("❌ 请指定要出售的物品\n用法: /精灵 出售 物品名 [数量]")
            return

        if amount < 1:
            yield event.plain_result("❌ 出售数量必须大于0")
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

        if not item.get("sellable", False) or item.get("sell_price", 0) <= 0:
            yield event.plain_result(f"❌ {item['name']} 无法出售")
            return

        # 检查背包
        inventory = await self.pm.get_inventory(user_id)
        owned = inventory.get(item["id"], 0)
        if owned < amount:
            yield event.plain_result(f"❌ 物品不足！需要{amount}个，拥有{owned}个")
            return

        # 扣除物品，获得金币
        await self.pm.use_item(user_id, item["id"], amount)
        total_earn = item["sell_price"] * amount
        await self.pm.add_currency(user_id, coins=total_earn)

        yield event.plain_result(
            f"💸 出售成功！\n━━━━━━━━━━━━\n"
            f"物品: {item['name']} x{amount}\n"
            f"获得: 💰{total_earn}\n"
            f"剩余: {owned - amount}个"
        )

    async def cmd_items(self, event: AstrMessageEvent):
        """
        查看背包物品
        指令: /精灵 物品
        """
        user_id = event.get_sender_id()
        player = await self.pm.get_player(user_id)
        if not player:
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        inventory = await self.pm.get_inventory(user_id)
        if not inventory:
            yield event.plain_result("🎒 背包空空如也~\n去商店看看吧: /精灵 商店")
            return

        # 按类型分组
        items_by_type = {}
        for item_id, count in inventory.items():
            if count <= 0:
                continue
            item = self.config.get_item("items", item_id)
            if not item:
                continue
            item_type = item.get("type", "other")
            if item_type not in items_by_type:
                items_by_type[item_type] = []
            items_by_type[item_type].append((item, count))

        type_order = ["capture", "heal", "revive", "stamina", "exp", "evolution", "buff", "tool", "gift", "material", "special", "subscription"]
        type_icons = {"capture": "🔮", "heal": "💊", "revive": "💖", "stamina": "⚡",
                      "exp": "🍬", "evolution": "💎", "buff": "✨", "tool": "🔧", "gift": "🎁", "material": "🧩",
                      "special": "⚗️", "subscription": "🎫"}

        text = "🎒 我的背包\n━━━━━━━━━━━━\n"
        text += f"💰 金币: {player['coins']}  💎 钻石: {player['diamonds']}\n"
        text += "━━━━━━━━━━━━"

        for item_type in type_order:
            if item_type not in items_by_type:
                continue
            items = items_by_type[item_type]
            icon = type_icons.get(item_type, "📦")
            type_name = self._get_item_type_name(item_type)
            text += f"\n\n{icon} 【{type_name}】\n"
            for item, count in sorted(items, key=lambda x: x[0].get("rarity", 1), reverse=True):
                text += f"  {item['name']} x{count}\n"

        text += "\n━━━━━━━━━━━━\n"
        text += "💡 使用: /精灵 使用 物品名 [精灵序号]\n"
        text += "💡 出售: /精灵 出售 物品名 [数量]"
        yield event.plain_result(text)

    async def cmd_use_item(self, event: AstrMessageEvent, item_name: str = "", target: int = 1):
        """
        使用物品
        指令: /精灵 使用 物品名 [目标精灵序号]
        """
        user_id = event.get_sender_id()
        player = await self.pm.get_player(user_id)
        if not player:
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        if not item_name:
            yield event.plain_result("❌ 请指定要使用的物品\n用法: /精灵 使用 物品名 [精灵序号]")
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

        if not await self.pm.has_item(user_id, item["id"]):
            yield event.plain_result(f"❌ 你没有 {item['name']}")
            return

        item_type = item.get("type", "")
        effect = item.get("effect", {})

        # 治疗药水
        if item_type == "heal":
            monsters = await self.pm.get_monsters(user_id)
            if not monsters:
                yield event.plain_result("❌ 你还没有精灵")
                return
            if target < 1 or target > len(monsters):
                yield event.plain_result(f"❌ 请指定正确的精灵序号 (1-{len(monsters)})")
                return

            monster = monsters[target - 1]
            max_hp = monster["stats"]["hp"]
            if monster["current_hp"] >= max_hp:
                yield event.plain_result(f"❌ {monster.get('nickname') or monster['name']} HP已满")
                return

            await self.pm.use_item(user_id, item["id"])
            heal_amount = effect.get("heal_hp", 30)
            old_hp = monster["current_hp"]
            new_hp = min(old_hp + heal_amount, max_hp)
            monster["current_hp"] = new_hp
            await self.pm.update_monster_from_dict(monster["instance_id"], monster)

            yield event.plain_result(
                f"💊 使用了 {item['name']}！\n"
                f"{monster.get('nickname') or monster['name']} HP: {old_hp} → {new_hp}"
            )

        # 体力药水
        elif item_type == "stamina":
            await self.pm.use_item(user_id, item["id"])
            restore = effect.get("restore_stamina", 30)
            new_stamina = await self.pm.restore_stamina(user_id, restore)
            yield event.plain_result(
                f"⚡ 使用了 {item['name']}！\n"
                f"体力恢复了 {restore} 点，当前: {new_stamina}/{player.get('max_stamina', 100)}"
            )

        # 经验糖果
        elif item_type == "exp":
            monsters = await self.pm.get_monsters(user_id)
            if not monsters:
                yield event.plain_result("❌ 你还没有精灵")
                return
            if target < 1 or target > len(monsters):
                yield event.plain_result(f"❌ 请指定正确的精灵序号 (1-{len(monsters)})")
                return

            monster = monsters[target - 1]
            await self.pm.use_item(user_id, item["id"])
            exp_amount = effect.get("give_exp", 100)

            from ..core import MonsterInstance
            monster_inst = MonsterInstance.from_dict(monster, self.config)
            result = monster_inst.add_exp(exp_amount, self.config)
            await self.pm.update_monster(monster_inst)

            text = f"🍬 使用了 {item['name']}！\n"
            text += f"{monster_inst.get_display_name()} 获得了 {exp_amount} 经验"
            if result.get("leveled_up"):
                text += f"\n🎉 升级了！Lv.{result['old_level']} → Lv.{result['new_level']}"
            yield event.plain_result(text)

        # 礼包
        elif item_type == "gift":
            await self.pm.use_item(user_id, item["id"])
            min_d = effect.get("diamonds_min", 10)
            max_d = effect.get("diamonds_max", 30)
            diamonds = random.randint(min_d, max_d)
            await self.pm.add_currency(user_id, diamonds=diamonds)
            yield event.plain_result(f"🎁 打开了 {item['name']}！\n获得了 💎{diamonds} 钻石！")

        # 复活药
        elif item_type == "revive":
            monsters = await self.pm.get_monsters(user_id)
            if not monsters:
                yield event.plain_result("❌ 你还没有精灵")
                return
            if target < 1 or target > len(monsters):
                yield event.plain_result(f"❌ 请指定正确的精灵序号 (1-{len(monsters)})")
                return

            monster = monsters[target - 1]
            if monster["current_hp"] > 0:
                yield event.plain_result(f"❌ {monster.get('nickname') or monster['name']} 还活着，不需要复活")
                return

            await self.pm.use_item(user_id, item["id"])
            heal_percent = effect.get("heal_percent", 50)
            max_hp = monster["stats"]["hp"]
            new_hp = max(1, int(max_hp * heal_percent / 100))
            monster["current_hp"] = new_hp
            monster["status"] = "normal"
            await self.pm.update_monster_from_dict(monster["instance_id"], monster)

            yield event.plain_result(
                f"💖 使用了 {item['name']}！\n"
                f"{monster.get('nickname') or monster['name']} 复活了！HP: {new_hp}/{max_hp}"
            )

        # ==================== 增益道具 (buff) ====================
        elif item_type == "buff":
            buff_type = effect.get("buff_type", "")
            buff_value = effect.get("buff_value", 1.5)
            duration = effect.get("duration_minutes", 30)

            # 持续性增益道具 - 可在背包中使用
            if buff_type in ["catch_rate", "exp_rate", "coin_rate"]:
                # 使用 PlayerManager 的 add_buff 方法
                success = await self.pm.add_buff(
                    user_id=user_id,
                    buff_type=buff_type,
                    buff_value=buff_value,
                    duration_minutes=duration,
                    source=item["name"]
                )

                if success:
                    # 扣除道具
                    await self.pm.use_item(user_id, item["id"], 1)

                    buff_names = {
                        "catch_rate": "🎯 捕捉率",
                        "exp_rate": "📈 经验获取",
                        "coin_rate": "💰 金币获取"
                    }
                    percent = int((buff_value - 1) * 100)

                    # 管理员日志
                    print(
                        f"[道具使用] 玩家 {user_id} 使用 {item['name']} - {buff_names.get(buff_type, buff_type)} +{percent}%，持续 {duration} 分钟")

                    yield event.plain_result(
                        f"✨ 使用成功！\n"
                        f"━━━━━━━━━━━━\n"
                        f"📦 道具: {item['name']}\n"
                        f"🎯 效果: {buff_names.get(buff_type, buff_type)} +{percent}%\n"
                        f"⏱️ 持续: {duration} 分钟\n"
                        f"━━━━━━━━━━━━\n"
                        f"💡 在探索和战斗中将自动生效！"
                    )
                else:
                    yield event.plain_result("❌ 使用失败，请稍后再试")
                return

            # 战斗增益道具 - 只能在战斗中使用
            else:
                yield event.plain_result(
                    f"⚔️ {item['name']} 是战斗增益道具\n"
                    f"━━━━━━━━━━━━\n"
                    f"📋 效果: {item.get('description', '提升战斗属性')}\n"
                    f"━━━━━━━━━━━━\n"
                    f"⚠️ 此道具只能在战斗中使用！\n"
                    f"进入战斗后，选择「道具」选项即可使用"
                )
                return

        # ==================== 特殊道具 (special) ====================
        elif item_type == "special":
            item_id = item["id"]
            monsters = await self.pm.get_monsters(user_id)
            if not monsters:
                yield event.plain_result("❌ 你还没有精灵")
                return
            if target < 1 or target > len(monsters):
                yield event.plain_result(f"❌ 请指定正确的精灵序号 (1-{len(monsters)})")
                return

            monster = monsters[target - 1]
            from ..core import MonsterInstance
            monster_inst = MonsterInstance.from_dict(monster, self.config)

            # 属性重置药剂 - 重置个体值
            if "属性重置" in item["name"] or effect.get("reset_ivs"):
                from ..core.formulas import GameFormulas
                old_ivs = monster_inst.ivs.copy()
                old_total = sum(old_ivs.values())

                # 30%概率获得更好的IV
                bonus_chance = effect.get("bonus_chance", 0.3)
                if random.random() < bonus_chance:
                    new_ivs = GameFormulas.generate_ivs(min_iv=10, max_iv=31, guaranteed_max=2)
                else:
                    new_ivs = GameFormulas.generate_ivs()

                monster_inst.ivs = new_ivs
                monster_inst.recalculate_stats(self.config)
                await self.pm.use_item(user_id, item["id"])
                await self.pm.update_monster(monster_inst)

                new_total = sum(new_ivs.values())
                improvement = new_total - old_total

                text = f"⚗️ 使用了 {item['name']}！\n"
                text += f"{monster_inst.get_display_name()} 的个体值已重置！\n"
                text += f"━━━━━━━━━━━━\n"
                text += f"IV总和: {old_total} → {new_total}"
                if improvement > 0:
                    text += f" (↑+{improvement} 🎉)"
                elif improvement < 0:
                    text += f" (↓{improvement})"
                else:
                    text += " (→持平)"
                yield event.plain_result(text)

            # 技能遗忘药 - 遗忘一个技能
            elif "技能遗忘" in item["name"] or effect.get("forget_skill"):
                if not monster_inst.skills:
                    yield event.plain_result(f"❌ {monster_inst.get_display_name()} 还没有学会任何技能")
                    return

                # 遗忘最后一个技能
                forgotten_skill_id = monster_inst.skills[-1]
                skill_info = self.config.get_item("skills", forgotten_skill_id)
                skill_name = skill_info.get("name", forgotten_skill_id) if skill_info else forgotten_skill_id

                monster_inst.forget_skill(forgotten_skill_id)
                await self.pm.use_item(user_id, item["id"])
                await self.pm.update_monster(monster_inst)

                yield event.plain_result(
                    f"💫 使用了 {item['name']}！\n"
                    f"{monster_inst.get_display_name()} 遗忘了技能 [{skill_name}]！\n"
                    f"当前技能槽位: {len(monster_inst.skills)}/4"
                )

            # 技能学习器 - 学习随机新技能
            elif "技能学习" in item["name"] or effect.get("learn_skill"):
                if len(monster_inst.skills) >= 4:
                    yield event.plain_result(f"❌ {monster_inst.get_display_name()} 技能槽已满，请先使用技能遗忘药")
                    return

                # 获取精灵可学习的技能（根据属性）
                all_skills = self.config.skills
                monster_types = monster_inst.types if isinstance(monster_inst.types, list) else [monster_inst.types]

                # 筛选适合该精灵的技能
                available_skills = []
                for skill_id, skill_data in all_skills.items():
                    if skill_id in monster_inst.skills:
                        continue  # 跳过已学会的
                    skill_type = skill_data.get("type", "")
                    # 可学习同属性技能或普通属性技能
                    if skill_type in monster_types or skill_type == "normal":
                        available_skills.append((skill_id, skill_data))

                if not available_skills:
                    yield event.plain_result(f"❌ 没有找到 {monster_inst.get_display_name()} 可以学习的新技能")
                    return

                # 随机选择一个技能
                new_skill_id, new_skill_data = random.choice(available_skills)
                monster_inst.learn_skill(new_skill_id)
                await self.pm.use_item(user_id, item["id"])
                await self.pm.update_monster(monster_inst)

                yield event.plain_result(
                    f"📚 使用了 {item['name']}！\n"
                    f"{monster_inst.get_display_name()} 学会了新技能 [{new_skill_data.get('name', new_skill_id)}]！\n"
                    f"威力: {new_skill_data.get('power', 0)} | 类型: {new_skill_data.get('type', '普通')}"
                )

            else:
                yield event.plain_result(
                    f"❌ {item['name']} 的特殊效果尚未实现\n"
                    f"请联系管理员配置此道具的效果"
                )

        # ==================== 订阅类道具 (subscription) ====================
        elif item_type == "subscription":
            # 目前简化处理：直接发放奖励
            daily_reward = effect.get("daily_diamonds", 30)
            duration_days = effect.get("duration_days", 30)

            # 立即发放首次奖励 + 总价值提示
            await self.pm.use_item(user_id, item["id"])
            await self.pm.add_currency(user_id, diamonds=daily_reward)

            total_value = daily_reward * duration_days
            yield event.plain_result(
                f"🎫 激活了 {item['name']}！\n"
                f"━━━━━━━━━━━━\n"
                f"📅 有效期: {duration_days}天\n"
                f"💎 每日奖励: {daily_reward}钻石\n"
                f"💰 总价值: {total_value}钻石\n"
                f"━━━━━━━━━━━━\n"
                f"✅ 已发放今日奖励 💎{daily_reward}\n"
                f"⚠️ 请每天签到领取剩余奖励！"
            )

        else:
            yield event.plain_result(
                f"❌ {item['name']} 暂时无法在背包中直接使用\n"
                f"(部分物品需要在特定场景使用，如战斗中)"
            )
