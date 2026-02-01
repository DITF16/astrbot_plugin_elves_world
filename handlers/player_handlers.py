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

        if self.pm.player_exists(user_id):
            yield event.plain_result(
                "🎮 你已经是训练师了！\n"
                "发送 /精灵 帮助 查看所有指令"
            )
            return

        # 创建玩家（使用插件配置的最大体力值）
        self.pm.create_player(user_id, user_name)

        # 更新为配置的最大体力
        self.pm.update_player(user_id, {"max_stamina": self.plugin.max_stamina})

        yield event.plain_result(
            f"🎉 欢迎来到精灵世界，{user_name}！\n\n"
            "请选择你的初始伙伴：\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ 烈焰龙 🔥 火系 - 攻击型\n"
            "2️⃣ 水灵精 💧 水系 - 平衡型\n"
            "3️⃣ 青叶狐 🌿 草系 - 速度型\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "请回复 1、2 或 3"
        )

        MonsterInstance = self._get_monster_instance_class()

        @session_waiter(timeout=60, record_history_chains=False)
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
            self.pm.add_monster(user_id, monster)
            self.pm.set_team(user_id, [monster.instance_id])

            await ev.send(ev.plain_result(
                f"🎊 太棒了！{template['name']} 成为了你的伙伴！\n\n"
                f"{monster.get_summary(self.config)}\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
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

        if not self.pm.player_exists(user_id):
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册 开始游戏")
            return

        info_text = self.pm.get_player_info_text(user_id)
        yield event.plain_result(info_text)

    async def cmd_heal(self, event: AstrMessageEvent):
        """
        治疗所有精灵
        指令: /精灵 治疗
        """
        user_id = event.get_sender_id()

        player = self.pm.get_player(user_id)
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

        healed = self.pm.heal_all_monsters(user_id)

        if healed == 0:
            yield event.plain_result("💚 你的精灵都很健康，不需要治疗~")
            return

        self.pm.spend_coins(user_id, heal_cost)
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
        text = self.pm.get_leaderboard_text(order_by, limit=10)
        yield event.plain_result(text)

    async def cmd_help(self, event: AstrMessageEvent):
        """
        显示帮助
        指令: /精灵 帮助
        """
        help_text = """
🎮 精灵对战游戏
━━━━━━━━━━━━━━━━━━━━

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

━━━━━━━━━━━━━━━━━━━━
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

        player = self.pm.get_player(user_id)
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

        self.pm.add_currency(user_id, coins=coins)
        self.pm.add_exp(user_id, exp)
        self.pm.restore_stamina(user_id, stamina)
        self.pm.update_player(user_id, {"last_daily_reward": today})

        yield event.plain_result(
            f"📅 签到成功！\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 金币 +{coins}\n"
            f"✨ 经验 +{exp}\n"
            f"⚡ 体力 +{stamina}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"明天继续签到有惊喜哦~"
        )
