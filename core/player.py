"""
玩家管理器（异步版本）
- 封装数据库操作
- 提供业务逻辑层
- 管理玩家状态
- 所有涉及IO的方法均为异步，避免阻塞事件循环
"""

from typing import Dict, List, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..database.db import Database
    from .config_manager import ConfigManager
    from .monster import MonsterInstance


class PlayerManager:
    """
    玩家管理器（异步版本）

    负责：
    - 玩家注册/查询
    - 精灵管理（添加/移除/队伍）
    - 货币/道具管理
    - 体力系统
    
    注意：所有涉及数据库IO的方法都是 async def，调用时需要 await
    """

    # 体力恢复配置
    STAMINA_RECOVERY_MINUTES = 5  # 每5分钟恢复1点体力
    MAX_MONSTER_CAPACITY = 100  # 精灵背包上限
    MAX_TEAM_SIZE = 3  # 队伍上限（战斗时可切换的精灵数量）

    def __init__(self, db: "Database", config_manager: "ConfigManager" = None):
        """
        初始化玩家管理器

        Args:
            db: 数据库实例
            config_manager: 配置管理器
        """
        self.db = db
        self.config = config_manager

    # ==================== 玩家基础操作 ====================

    async def player_exists(self, user_id: str) -> bool:
        """检查玩家是否存在"""
        return await self.db.async_player_exists(user_id)

    async def create_player(self, user_id: str, name: str) -> Dict:
        """创建新玩家"""
        return await self.db.async_create_player(user_id, name)

    async def get_player(self, user_id: str, auto_recover_stamina: bool = True) -> Optional[Dict]:
        """
        获取玩家数据

        Args:
            user_id: 用户ID
            auto_recover_stamina: 是否自动恢复体力

        Returns:
            玩家数据字典，不存在返回None
        """
        player = await self.db.async_get_player(user_id)

        if player and auto_recover_stamina:
            recovered = self._calculate_stamina_recovery(player)
            if recovered > 0:
                new_stamina = await self.db.async_restore_stamina(user_id, recovered)
                player["stamina"] = new_stamina
                await self.db.async_update_player(user_id, {
                    "last_stamina_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

        return player

    def _calculate_stamina_recovery(self, player: Dict) -> int:
        """计算应恢复的体力（纯计算，无IO，保持同步）"""
        last_update_str = player.get("last_stamina_update")
        if not last_update_str:
            return 0

        try:
            last_update = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return 0

        now = datetime.now()
        minutes_passed = (now - last_update).total_seconds() / 60
        recovery = int(minutes_passed / self.STAMINA_RECOVERY_MINUTES)

        current = player.get("stamina", 0)
        max_stamina = player.get("max_stamina", 100)
        max_recovery = max_stamina - current

        return min(recovery, max_recovery)

    async def update_player(self, user_id: str, updates: Dict) -> bool:
        """更新玩家数据"""

        return await self.db.async_update_player(user_id, updates)

    async def get_player_info_text(self, user_id: str) -> str:
        """获取玩家信息文本（用于显示）"""
        player = await self.get_player(user_id)
        if not player:
            return "❌ 玩家不存在"

        monster_count = await self.db.async_get_player_monster_count(user_id)
        team = await self.get_team(user_id)

        win_rate = 0
        total_battles = player["wins"] + player["losses"]
        if total_battles > 0:
            win_rate = player["wins"] / total_battles * 100

        return (
            f"👤 {player['name']} (Lv.{player['level']})\n"
            f"{'─' * 20}\n"
            f"💰 金币: {player['coins']}\n"
            f"💎 钻石: {player['diamonds']}\n"
            f"⚡ 体力: {player['stamina']}/{player['max_stamina']}\n"
            f"{'─' * 20}\n"
            f"📦 精灵: {monster_count}/{self.MAX_MONSTER_CAPACITY}\n"
            f"👥 队伍: {len(team)}/{self.MAX_TEAM_SIZE}\n"
            f"🏆 战绩: {player['wins']}胜 {player['losses']}负 ({win_rate:.1f}%)\n"
            f"📍 当前区域: {player['current_region']}\n"
            f"📅 注册: {player['created_at'][:10]}"
        )

    # ==================== 货币操作 ====================

    async def add_currency(self, user_id: str, coins: int = 0, diamonds: int = 0) -> bool:
        """增加货币"""
        return await self.db.async_add_player_currency(user_id, coins, diamonds)

    async def spend_coins(self, user_id: str, amount: int) -> bool:
        """
        消费金币

        Returns:
            是否成功（金币不足返回False）
        """
        player = await self.db.async_get_player(user_id)
        if not player or player["coins"] < amount:
            return False
        return await self.db.async_add_player_currency(user_id, coins=-amount)

    async def spend_diamonds(self, user_id: str, amount: int) -> bool:
        """消费钻石"""
        player = await self.db.async_get_player(user_id)
        if not player or player["diamonds"] < amount:
            return False
        return await self.db.async_add_player_currency(user_id, diamonds=-amount)

    # ==================== 体力操作 ====================

    async def consume_stamina(self, user_id: str, amount: int) -> bool:
        """消耗体力"""
        return await self.db.async_consume_stamina(user_id, amount)

    async def restore_stamina(self, user_id: str, amount: int) -> int:
        """恢复体力，返回恢复后的值"""
        return await self.db.async_restore_stamina(user_id, amount)

    async def get_stamina(self, user_id: str) -> tuple:
        """获取体力 (当前, 最大)"""
        player = await self.get_player(user_id)
        if not player:
            return (0, 0)
        return (player["stamina"], player["max_stamina"])

    # ==================== 经验/等级 ====================

    async def add_exp(self, user_id: str, exp: int) -> Dict:
        """
        增加玩家经验

        Returns:
            {"leveled_up": bool, "new_level": int}
        """
        return await self.db.async_add_player_exp(user_id, exp)

    # ==================== 战斗记录 ====================

    async def record_battle(self, user_id: str, is_win: bool):
        """记录战斗结果"""
        await self.db.async_record_battle_result(user_id, is_win)

    # ==================== 精灵管理 ====================

    async def add_monster(self, user_id: str, monster: "MonsterInstance") -> bool:
        """
        添加精灵到玩家背包

        Args:
            user_id: 玩家ID
            monster: MonsterInstance实例

        Returns:
            是否成功（背包已满返回False）
        """
        current_count = await self.db.async_get_player_monster_count(user_id)
        if current_count >= self.MAX_MONSTER_CAPACITY:
            return False

        monster_data = monster.to_dict()
        return await self.db.async_add_monster(user_id, monster_data)

    async def add_monster_from_dict(self, user_id: str, monster_data: Dict) -> bool:
        """从字典添加精灵"""
        current_count = await self.db.async_get_player_monster_count(user_id)
        if current_count >= self.MAX_MONSTER_CAPACITY:
            return False
        return await self.db.async_add_monster(user_id, monster_data)


    async def get_monsters(self, user_id: str) -> List[Dict]:
        """获取玩家所有精灵"""
        return await self.db.async_get_player_monsters(user_id)

    async def get_monster(self, instance_id: str) -> Optional[Dict]:
        """获取单个精灵"""
        return await self.db.async_get_monster(instance_id)

    async def update_monster(self, monster: "MonsterInstance") -> bool:
        """更新精灵数据"""
        return await self.db.async_update_monster(monster.instance_id, monster.to_dict())

    async def update_monster_from_dict(self, instance_id: str, monster_data: Dict) -> bool:
        """从字典更新精灵"""
        return await self.db.async_update_monster(instance_id, monster_data)

    async def release_monster(self, user_id: str, instance_id: str) -> bool:
        """
        放生精灵

        Returns:
            是否成功
        """
        monster = await self.db.async_get_monster(instance_id)
        if not monster:
            return False

        # 不能放生队伍中的精灵（需要先移出队伍）
        monsters = await self.db.async_get_player_monsters(user_id)
        for m in monsters:
            if m.get("instance_id") == instance_id and m.get("_is_in_team"):
                return False

        return await self.db.async_delete_monster(instance_id)

    async def get_monster_count(self, user_id: str) -> int:
        """获取精灵数量"""
        return await self.db.async_get_player_monster_count(user_id)

    # ==================== 队伍管理 ====================

    async def get_team(self, user_id: str) -> List[Dict]:
        """获取玩家队伍"""
        return await self.db.async_get_player_team(user_id)

    async def set_team(self, user_id: str, monster_ids: List[str]) -> bool:
        """
        设置队伍

        Args:
            user_id: 玩家ID
            monster_ids: 精灵instance_id列表（按顺序）

        Returns:
            是否成功
        """
        if len(monster_ids) > self.MAX_TEAM_SIZE:
            return False

        if len(monster_ids) == 0:
            return False

        # 验证精灵是否属于该玩家
        player_monsters = await self.get_monsters(user_id)
        player_monster_ids = {m["instance_id"] for m in player_monsters}

        for mid in monster_ids:
            if mid not in player_monster_ids:
                return False

        return await self.db.async_set_team(user_id, monster_ids)

    async def add_to_team(self, user_id: str, instance_id: str) -> bool:
        """添加精灵到队伍末尾"""
        team = await self.get_team(user_id)
        if len(team) >= self.MAX_TEAM_SIZE:
            return False

        team_ids = [m["instance_id"] for m in team]
        if instance_id in team_ids:
            return False

        team_ids.append(instance_id)
        return await self.set_team(user_id, team_ids)

    async def remove_from_team(self, user_id: str, instance_id: str) -> bool:
        """从队伍移除精灵"""
        team = await self.get_team(user_id)
        team_ids = [m["instance_id"] for m in team if m["instance_id"] != instance_id]

        if len(team_ids) == 0:
            return False

        return await self.set_team(user_id, team_ids)

    async def swap_team_position(self, user_id: str, pos1: int, pos2: int) -> bool:
        """交换队伍位置"""
        team = await self.get_team(user_id)
        if pos1 < 0 or pos1 >= len(team) or pos2 < 0 or pos2 >= len(team):
            return False

        team_ids = [m["instance_id"] for m in team]
        team_ids[pos1], team_ids[pos2] = team_ids[pos2], team_ids[pos1]
        return await self.set_team(user_id, team_ids)

    async def get_first_available_monster(self, user_id: str) -> Optional[Dict]:
        """获取队伍中第一个未倒下的精灵"""
        team = await self.get_team(user_id)
        for monster in team:
            if monster.get("current_hp", 0) > 0:
                return monster
        return None

    async def has_available_monster(self, user_id: str) -> bool:
        """检查是否有可战斗的精灵"""
        return await self.get_first_available_monster(user_id) is not None

    async def heal_all_monsters(self, user_id: str) -> int:
        """
        治疗所有精灵

        Returns:
            治疗的精灵数量
        """
        monsters = await self.get_monsters(user_id)
        healed_count = 0

        for monster_data in monsters:
            if monster_data["current_hp"] < monster_data["max_hp"] or monster_data.get("status"):
                monster_data["current_hp"] = monster_data["max_hp"]
                monster_data["status"] = None
                monster_data["status_turns"] = 0
                await self.db.async_update_monster(monster_data["instance_id"], monster_data)
                healed_count += 1

        return healed_count

    async def heal_team(self, user_id: str) -> int:
        """治疗队伍精灵"""
        team = await self.get_team(user_id)
        healed_count = 0

        for monster_data in team:
            if monster_data["current_hp"] < monster_data["max_hp"] or monster_data.get("status"):
                monster_data["current_hp"] = monster_data["max_hp"]
                monster_data["status"] = None
                monster_data["status_turns"] = 0
                await self.db.async_update_monster(monster_data["instance_id"], monster_data)
                healed_count += 1

        return healed_count

    # ==================== 道具管理 ====================

    async def get_inventory(self, user_id: str) -> Dict[str, int]:
        """获取背包道具"""
        return await self.db.async_get_inventory(user_id)

    async def add_item(self, user_id: str, item_id: str, amount: int = 1) -> int:
        """添加道具，返回当前数量"""
        return await self.db.async_add_item(user_id, item_id, amount)

    async def use_item(self, user_id: str, item_id: str, amount: int = 1) -> bool:
        """使用道具"""
        return await self.db.async_consume_item(user_id, item_id, amount)

    async def has_item(self, user_id: str, item_id: str, amount: int = 1) -> bool:
        """检查是否拥有足够道具"""
        return await self.db.async_get_item_count(user_id, item_id) >= amount

    # ==================== 区域管理 ====================

    async def get_current_region(self, user_id: str) -> str:
        """获取当前区域"""
        player = await self.db.async_get_player(user_id)
        return player["current_region"] if player else "starter_forest"

    async def set_current_region(self, user_id: str, region_id: str) -> bool:
        """设置当前区域"""
        return await self.db.async_update_player(user_id, {"current_region": region_id})

    async def can_enter_region(self, user_id: str, region_id: str) -> tuple:
        """
        检查是否可以进入区域

        Returns:
            (can_enter: bool, reason: str)
        """
        if not self.config:
            return (True, "")

        region = self.config.get_item("regions", region_id)
        if not region:
            return (False, "区域不存在")

        player = await self.get_player(user_id)
        if not player:
            return (False, "玩家不存在")

        unlock_condition = region.get("unlock_requires")  # 与 default_regions.json 字段名保持一致
        if not unlock_condition:
            return (True, "")

        condition_type = unlock_condition.get("type")

        if condition_type == "level":
            # 等级解锁条件：{"type": "level", "value": 10}
            condition_value = unlock_condition.get("value")
            if player["level"] < condition_value:
                return (False, f"需要等级 {condition_value}")
        elif condition_type == "boss":
            # BOSS解锁条件：{"type": "boss", "id": "森林守护者"}
            boss_id = unlock_condition.get("id")
            if not await self.db.async_is_boss_first_cleared(user_id, boss_id):
                boss_config = self.config.get_item("bosses", boss_id)
                boss_name = boss_config.get("name", boss_id) if boss_config else boss_id
                return (False, f"需要先击败 {boss_name}")

        return (True, "")

    # ==================== BOSS记录 ====================

    async def record_boss_clear(self, user_id: str, boss_id: str, time_seconds: int = None) -> Dict:
        """记录BOSS通关"""
        return await self.db.async_record_boss_clear(user_id, boss_id, time_seconds)

    async def is_boss_first_cleared(self, user_id: str, boss_id: str) -> bool:
        """检查是否已首通BOSS"""
        return await self.db.async_is_boss_first_cleared(user_id, boss_id)

    # ==================== 排行榜 ====================

    async def get_leaderboard(self, order_by: str = "wins", limit: int = 10) -> List[Dict]:
        """获取排行榜"""
        return await self.db.async_get_leaderboard(order_by, limit)


    async def get_leaderboard_text(self, order_by: str = "wins", limit: int = 10) -> str:
        """获取排行榜文本"""
        title_map = {
            "wins": "🏆 胜场排行榜",
            "level": "📊 等级排行榜",
            "coins": "💰 金币排行榜",
        }

        title = title_map.get(order_by, "排行榜")
        players = await self.get_leaderboard(order_by, limit)

        if not players:
            return f"{title}\n暂无数据"

        text = f"{title}\n{'─' * 20}\n"
        medals = ["🥇", "🥈", "🥉"]

        for i, p in enumerate(players):
            rank = medals[i] if i < 3 else f"{i + 1}."
            value = p.get(order_by, 0)
            text += f"{rank} {p['name']} Lv.{p['level']} - {value}\n"

        return text

    # ==================== BUFF 管理 ====================

    async def get_active_buffs(self, user_id: str) -> Dict:
        """
        获取玩家当前激活的 buff 列表
        
        Returns:
            格式: {buff_type: {"value": float, "expires_at": str, "source": str}}
        """
        player = await self.db.async_get_player(user_id)
        if not player:
            return {}
        
        buffs = player.get("active_buffs", {})
        if isinstance(buffs, str):
            import json
            try:
                buffs = json.loads(buffs)
            except:
                buffs = {}
        
        # 清理过期的 buff
        now = datetime.now()
        valid_buffs = {}
        for buff_type, buff_data in buffs.items():
            expires_at_str = buff_data.get("expires_at", "")
            if expires_at_str:
                try:
                    expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
                    if expires_at > now:
                        valid_buffs[buff_type] = buff_data
                except ValueError:
                    pass
        
        # 如果有过期的 buff，更新数据库
        if len(valid_buffs) != len(buffs):
            await self._save_buffs(user_id, valid_buffs)
        
        return valid_buffs

    async def add_buff(self, user_id: str, buff_type: str, buff_value: float, 
                 duration_minutes: int, source: str = "item") -> bool:
        """
        给玩家添加一个 buff
        
        Args:
            user_id: 玩家ID
            buff_type: buff 类型 (catch_rate, exp_rate, coin_rate 等)
            buff_value: buff 数值（倍率，如 1.5 表示 +50%）
            duration_minutes: 持续时间（分钟）
            source: 来源（道具名称等）
        
        Returns:
            是否成功
        """
        buffs = await self.get_active_buffs(user_id)
        
        expires_at = datetime.now()
        from datetime import timedelta
        expires_at += timedelta(minutes=duration_minutes)
        
        buffs[buff_type] = {
            "value": buff_value,
            "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            "source": source
        }
        
        return await self._save_buffs(user_id, buffs)

    async def remove_buff(self, user_id: str, buff_type: str) -> bool:
        """移除指定的 buff"""
        buffs = await self.get_active_buffs(user_id)
        if buff_type in buffs:
            del buffs[buff_type]
            return await self._save_buffs(user_id, buffs)
        return False

    async def get_buff_multiplier(self, user_id: str, buff_type: str) -> float:
        """
        获取指定类型 buff 的倍率
        
        Returns:
            倍率值，无 buff 时返回 1.0
        """
        buffs = await self.get_active_buffs(user_id)
        if buff_type in buffs:
            return buffs[buff_type].get("value", 1.0)
        return 1.0

    async def _save_buffs(self, user_id: str, buffs: Dict) -> bool:
        """保存 buff 数据到数据库"""
        import json
        return await self.db.async_update_player(user_id, {
            "active_buffs": json.dumps(buffs, ensure_ascii=False)
        })

    async def get_buffs_text(self, user_id: str) -> str:
        """获取玩家当前 buff 的文本描述"""
        buffs = await self.get_active_buffs(user_id)
        if not buffs:
            return "当前没有激活的增益效果"
        
        buff_names = {
            "catch_rate": "🎯 捕捉率",
            "exp_rate": "📈 经验",
            "coin_rate": "💰 金币",
            "attack": "⚔️ 攻击",
            "defense": "🛡️ 防御",
            "speed": "💨 速度",
            "critical": "🎯 暴击"
        }
        
        now = datetime.now()
        lines = ["✨ 当前增益效果："]
        
        for buff_type, data in buffs.items():
            name = buff_names.get(buff_type, buff_type)
            value = data.get("value", 1.0)
            expires_at_str = data.get("expires_at", "")
            
            try:
                expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
                remaining = expires_at - now
                remaining_mins = int(remaining.total_seconds() / 60)
                if remaining_mins >= 60:
                    time_str = f"{remaining_mins // 60}小时{remaining_mins % 60}分钟"
                else:
                    time_str = f"{remaining_mins}分钟"
            except:
                time_str = "未知"
            
            percent = int((value - 1) * 100) if value > 1 else int(value * 100)
            lines.append(f"  {name} +{percent}% (剩余 {time_str})")
        
        return "\n".join(lines)


