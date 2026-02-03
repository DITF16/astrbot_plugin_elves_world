from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger, AstrBotConfig
from astrbot.core.star.filter.event_message_type import EventMessageType
from astrbot.core.star import StarTools

from pathlib import Path


# 导入核心模块
from .core import (
    ConfigManager,
    PlayerManager,
    BattleSystem,
    WorldManager,
)
from .database import Database
from .web import WebServer

# 导入指令处理器
from .handlers import (
    PlayerHandlers,
    MonsterHandlers,
    BattleHandlers,
    ExploreHandlers,
)

class MonsterGamePlugin(Star):
    """精灵对战游戏主插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)

        # 保存AstrBot配置
        self.astrbot_config = config

        # ==================== 路径配置 ====================
        # 插件目录（存放默认数据）
        self.plugin_dir = Path(__file__).parent
        self.default_data_path = self.plugin_dir / "data"

        # 运行时数据目录（使用AstrBot规范路径）
        self.plugin_data_path = StarTools.get_data_dir()
        self.plugin_data_path.mkdir(parents=True, exist_ok=True)

        # ==================== 读取配置 ====================
        self._load_settings()

        # ==================== 初始化核心系统 ====================
        self.game_config = ConfigManager(
            data_path=self.plugin_data_path,  # 运行时数据目录（可读写）
            default_data_path=self.default_data_path  # 插件自带的默认数据目录（只读）
        )

        self.db = Database(self.plugin_data_path / "game.db")
        self.player_manager = PlayerManager(self.db, self.game_config)
        self.battle_system = BattleSystem(self.game_config, self.player_manager)
        self.world_manager = WorldManager(self.game_config)

        # ==================== 初始化指令处理器 ====================
        self.player_handlers = PlayerHandlers(self)
        self.monster_handlers = MonsterHandlers(self)
        self.battle_handlers = BattleHandlers(self)
        self.explore_handlers = ExploreHandlers(self)

        # 注入依赖（避免循环引用）
        self.explore_handlers.set_battle_handlers(self.battle_handlers)
        self.battle_handlers.set_explore_handlers(self.explore_handlers)

        # 初始化Web管理后台
        self.web_server = WebServer(self)
        self.web_server.start()

        logger.info("🎮 精灵对战游戏插件加载成功！")

    # ==================== 前缀消息处理器 ====================
    
    @filter.event_message_type(EventMessageType.ALL, priority=1)
    async def handle_game_action(self, event: AstrMessageEvent):
        """
        处理带前缀的游戏操作消息
        
        当玩家在探索或战斗中时，只有带前缀的消息才会被处理为游戏操作
        不带前缀的消息会被忽略，玩家可以正常聊天
        """
        prefix = self.game_action_prefix
        if not prefix:
            return  # 没有配置前缀，不处理
        
        msg = event.message_str.strip()
        
        # 检查消息是否以前缀开头
        if not msg.startswith(prefix):
            return  # 不是游戏操作消息，忽略
        
        # 去掉前缀，获取实际操作内容
        action = msg[len(prefix):].strip()
        if not action:
            return  # 前缀后没有内容，忽略
        
        user_id = event.get_sender_id()
        
        # 检查玩家是否存在
        if not self.db.player_exists(user_id):
            return  # 玩家不存在，忽略
        
        # 获取玩家游戏状态
        state, state_data = self.db.get_game_state(user_id)
        
        if not state:
            return  # 玩家不在游戏状态中，忽略
        
        # 根据状态分发处理
        if state == "exploring":
            async for result in self.explore_handlers.handle_explore_action(event, user_id, action, state_data):
                yield result
            event.stop_event()
            
        elif state == "battling":
            async for result in self.battle_handlers.handle_battle_action(event, user_id, action, state_data):
                yield result
            event.stop_event()


    def _load_settings(self):
        """从AstrBot配置加载游戏设置"""
        # 游戏基础设置
        game_settings = self.astrbot_config.get("game_settings", {})
        self.stamina_recovery_minutes = game_settings.get("stamina_recovery_minutes", 5)
        self.max_stamina = game_settings.get("max_stamina", 100)
        self.max_team_size = game_settings.get("max_team_size", 6)
        self.max_monster_capacity = game_settings.get("max_monster_capacity", 100)
        self.heal_cost = game_settings.get("heal_cost", 100)
        self.battle_stamina_cost = game_settings.get("battle_stamina_cost", 5)

        # 签到奖励设置
        daily_reward = self.astrbot_config.get("daily_reward", {})
        self.daily_reward_enabled = daily_reward.get("enabled", True)
        self.daily_coins_min = daily_reward.get("coins_min", 100)
        self.daily_coins_max = daily_reward.get("coins_max", 300)
        self.daily_exp_min = daily_reward.get("exp_min", 20)
        self.daily_exp_max = daily_reward.get("exp_max", 50)
        self.daily_stamina_reward = daily_reward.get("stamina_reward", 30)

        # 战斗设置
        battle_settings = self.astrbot_config.get("battle_settings", {})
        self.battle_timeout = battle_settings.get("battle_timeout", 180)
        self.explore_timeout = battle_settings.get("explore_timeout", 300)
        self.exp_multiplier = battle_settings.get("exp_multiplier", 1.0)
        self.coin_multiplier = battle_settings.get("coin_multiplier", 1.0)
        self.catch_rate_multiplier = battle_settings.get("catch_rate_multiplier", 1.0)

        # 地图设置
        map_settings = self.astrbot_config.get("map_settings", {})
        self.default_map_size = map_settings.get("default_map_size", "medium")
        self.fog_of_war = map_settings.get("fog_of_war", True)
        self.monster_encounter_rate = map_settings.get("monster_encounter_rate", 30)
        self.treasure_rate = map_settings.get("treasure_rate", 15)
        self.rare_encounter_rate = map_settings.get("rare_encounter_rate", 5)

        # 调试设置
        debug = self.astrbot_config.get("debug", {})
        self.debug_mode = debug.get("enabled", False)
        self.show_damage_details = debug.get("show_damage_details", False)
        self.auto_win = debug.get("auto_win", False)



        # 游戏操作前缀（探索/战斗时使用）
        self.game_action_prefix = self.astrbot_config.get("game_action_prefix", ">")



        if self.debug_mode:
            logger.info("🔧 精灵游戏调试模式已启用")

    # ==================== 主指令组 ====================

    @filter.command_group("精灵")
    def pm_group(self):
        """精灵游戏主指令组"""
        pass

    # ==================== 玩家指令 ====================

    @pm_group.command("注册")
    async def cmd_start(self, event: AstrMessageEvent):
        """注册成为训练师"""
        async for result in self.player_handlers.cmd_start(event):
            yield result

    @pm_group.command("我")
    async def cmd_info(self, event: AstrMessageEvent):
        """查看个人信息"""
        async for result in self.player_handlers.cmd_info(event):
            yield result

    @pm_group.command("签到")
    async def cmd_sign(self, event: AstrMessageEvent):
        """每日签到"""
        async for result in self.player_handlers.cmd_sign(event):
            yield result

    @pm_group.command("治疗")
    async def cmd_heal(self, event: AstrMessageEvent):
        """治疗所有精灵"""
        async for result in self.player_handlers.cmd_heal(event):
            yield result

    @pm_group.command("排行")
    async def cmd_rank(self, event: AstrMessageEvent, rank_type: str = "胜场"):
        """查看排行榜"""
        async for result in self.player_handlers.cmd_rank(event, rank_type):
            yield result

    @pm_group.command("帮助")
    async def cmd_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        async for result in self.player_handlers.cmd_help(event):
            yield result

    # ==================== 精灵管理指令 ====================

    @pm_group.command("背包")
    async def cmd_bag(self, event: AstrMessageEvent):
        """查看精灵背包"""
        async for result in self.monster_handlers.cmd_bag(event):
            yield result

    @pm_group.command("详情")
    async def cmd_detail(self, event: AstrMessageEvent, index: int = 1):
        """查看精灵详情"""
        async for result in self.monster_handlers.cmd_detail(event, index):
            yield result

    @pm_group.command("队伍")
    async def cmd_team(self, event: AstrMessageEvent, *args):
        """队伍管理"""
        async for result in self.monster_handlers.cmd_team(event, *args):
            yield result

    @pm_group.command("进化")
    async def cmd_evolve(self, event: AstrMessageEvent, index: int = 0):
        """进化精灵"""
        async for result in self.monster_handlers.cmd_evolve(event, index):
            yield result

    @pm_group.command("改名")
    async def cmd_rename(self, event: AstrMessageEvent, index: int = 0, *name_parts):
        """给精灵起昵称"""
        async for result in self.monster_handlers.cmd_rename(event, index, *name_parts):
            yield result

    @pm_group.command("放生")
    async def cmd_release(self, event: AstrMessageEvent, index: int = 0):
        """放生精灵"""
        async for result in self.monster_handlers.cmd_release(event, index):
            yield result

    # ==================== 战斗指令 ====================

    @pm_group.command("战斗")
    async def cmd_battle(self, event: AstrMessageEvent):
        """快速野外战斗"""
        async for result in self.battle_handlers.cmd_battle(event):
            yield result

    # ==================== 探索指令 ====================

    @pm_group.command("区域")
    async def cmd_regions(self, event: AstrMessageEvent):
        """查看可探索区域"""
        async for result in self.explore_handlers.cmd_regions(event):
            yield result

    @pm_group.command("探索")
    async def cmd_explore(self, event: AstrMessageEvent, region_name: str = ""):
        """探索区域"""
        async for result in self.explore_handlers.cmd_explore(event, region_name):
            yield result

    @pm_group.command("地图")
    async def cmd_map(self, event: AstrMessageEvent):
        """查看当前地图"""
        async for result in self.explore_handlers.cmd_map(event):
            yield result

    @pm_group.command("离开")
    async def cmd_leave(self, event: AstrMessageEvent):
        """离开当前探索"""
        async for result in self.explore_handlers.cmd_leave(event):
            yield result

    # ==================== 商店指令 ====================

    @pm_group.command("商店")
    async def cmd_shop(self, event: AstrMessageEvent, category: str = ""):
        """查看商店"""
        async for result in self.player_handlers.cmd_shop(event, category):
            yield result

    @pm_group.command("购买")
    async def cmd_buy(self, event: AstrMessageEvent, item_name: str = "", amount: int = 1):
        """购买物品"""
        async for result in self.player_handlers.cmd_buy(event, item_name, amount):
            yield result

    @pm_group.command("出售")
    async def cmd_sell(self, event: AstrMessageEvent, item_name: str = "", amount: int = 1):
        """出售物品"""
        async for result in self.player_handlers.cmd_sell(event, item_name, amount):
            yield result

    @pm_group.command("物品")
    async def cmd_items(self, event: AstrMessageEvent):
        """查看背包物品"""
        async for result in self.player_handlers.cmd_items(event):
            yield result

    @pm_group.command("使用")
    async def cmd_use_item(self, event: AstrMessageEvent, item_name: str = "", target: int = 1):
        """使用物品"""
        async for result in self.player_handlers.cmd_use_item(event, item_name, target):
            yield result

    # ==================== 管理员指令 ====================

    @pm_group.command("重载配置")
    async def cmd_reload(self, event: AstrMessageEvent):
        """重新加载游戏配置（管理员）"""
        # TODO: 添加权限检查
        try:
            await self.game_config.reload_all()  # 异步重载，不阻塞事件循环
            self._load_settings()
            yield event.plain_result("✅ 游戏配置已重新加载")
        except Exception as e:
            logger.error(f"重载配置失败: {e}")
            yield event.plain_result(f"❌ 重载失败: {e}")

    @pm_group.command("统计")
    async def cmd_stats(self, event: AstrMessageEvent):
        """查看游戏统计（管理员）"""
        total_players = self.db.get_total_players()

        yield event.plain_result(
            f"📊 游戏统计\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"注册玩家: {total_players}\n"
            f"调试模式: {'开启' if self.debug_mode else '关闭'}"
        )

    # ==================== 生命周期 ====================

    async def terminate(self):
        """插件卸载时清理"""
        # 清理活跃战斗
        if hasattr(self, 'battle_handlers'):
            self.battle_handlers._active_battles.clear()

        # 清理活跃探索地图
        if hasattr(self, 'world_manager'):
            self.world_manager._active_maps.clear()

        # 停止Web服务器
        if hasattr(self, 'web_server'):
            self.web_server.stop()

        logger.info("🎮 精灵对战游戏插件已卸载")
