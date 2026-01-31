"""
数据库管理模块
- 使用SQLite存储玩家数据
- 支持异步操作
- 自动建表和迁移
"""

import sqlite3
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
from threading import Lock
from datetime import datetime


class Database:
    """
    游戏数据库管理器

    存储内容：
    - 玩家基础信息
    - 玩家拥有的精灵
    - 玩家背包道具
    - 战斗记录/统计
    """

    def __init__(self, db_path: Path):
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

        # 初始化数据库结构
        self._init_tables()

    @contextmanager
    def _get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row  # 返回字典形式
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _init_tables(self):
        """初始化数据库表结构"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 玩家表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS players (
                        user_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        coins INTEGER DEFAULT 1000,
                        diamonds INTEGER DEFAULT 0,
                        stamina INTEGER DEFAULT 100,
                        max_stamina INTEGER DEFAULT 100,
                        level INTEGER DEFAULT 1,
                        exp INTEGER DEFAULT 0,
                        wins INTEGER DEFAULT 0,
                        losses INTEGER DEFAULT 0,
                        current_region TEXT DEFAULT 'starter_forest',
                        team_slots TEXT DEFAULT '[]',
                        titles TEXT DEFAULT '[]',
                        achievements TEXT DEFAULT '[]',
                        settings TEXT DEFAULT '{}',
                        last_stamina_update TEXT,
                        last_daily_reward TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    )
                ''')

                # 精灵表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS monsters (
                        instance_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        data TEXT NOT NULL,
                        is_in_team INTEGER DEFAULT 0,
                        team_position INTEGER DEFAULT -1,
                        created_at TEXT,
                        updated_at TEXT,
                        FOREIGN KEY (owner_id) REFERENCES players(user_id)
                    )
                ''')

                # 背包/道具表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS inventory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        owner_id TEXT NOT NULL,
                        item_id TEXT NOT NULL,
                        amount INTEGER DEFAULT 1,
                        FOREIGN KEY (owner_id) REFERENCES players(user_id),
                        UNIQUE(owner_id, item_id)
                    )
                ''')

                # BOSS击杀记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS boss_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        boss_id TEXT NOT NULL,
                        first_clear INTEGER DEFAULT 0,
                        clear_count INTEGER DEFAULT 0,
                        last_clear_time TEXT,
                        best_time_seconds INTEGER,
                        FOREIGN KEY (user_id) REFERENCES players(user_id),
                        UNIQUE(user_id, boss_id)
                    )
                ''')

                # 创建索引
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_monsters_owner ON monsters(owner_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_inventory_owner ON inventory(owner_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_boss_records_user ON boss_records(user_id)')

    # ==================== 玩家操作 ====================

    def player_exists(self, user_id: str) -> bool:
        """检查玩家是否存在"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM players WHERE user_id = ?', (user_id,))
                return cursor.fetchone() is not None

    def create_player(self, user_id: str, name: str) -> Dict:
        """
        创建新玩家

        Args:
            user_id: 用户ID
            name: 用户名

        Returns:
            玩家数据字典
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        player_data = {
            "user_id": user_id,
            "name": name,
            "coins": 1000,
            "diamonds": 0,
            "stamina": 100,
            "max_stamina": 100,
            "level": 1,
            "exp": 0,
            "wins": 0,
            "losses": 0,
            "current_region": "starter_forest",
            "team_slots": [],
            "titles": [],
            "achievements": [],
            "settings": {},
            "last_stamina_update": now,
            "last_daily_reward": None,
            "created_at": now,
            "updated_at": now,
        }

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO players (
                        user_id, name, coins, diamonds, stamina, max_stamina,
                        level, exp, wins, losses, current_region, team_slots,
                        titles, achievements, settings, last_stamina_update,
                        last_daily_reward, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id, name, 1000, 0, 100, 100,
                    1, 0, 0, 0, "starter_forest", "[]",
                    "[]", "[]", "{}", now,
                    None, now, now
                ))

        return player_data

    def get_player(self, user_id: str) -> Optional[Dict]:
        """获取玩家数据"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()

                if row is None:
                    return None

                player = dict(row)
                # 解析JSON字段
                player["team_slots"] = json.loads(player.get("team_slots", "[]"))
                player["titles"] = json.loads(player.get("titles", "[]"))
                player["achievements"] = json.loads(player.get("achievements", "[]"))
                player["settings"] = json.loads(player.get("settings", "{}"))

                return player

    def update_player(self, user_id: str, updates: Dict) -> bool:
        """
        更新玩家数据

        Args:
            user_id: 用户ID
            updates: 要更新的字段字典

        Returns:
            是否成功
        """
        if not updates:
            return True

        # 处理JSON字段
        json_fields = ["team_slots", "titles", "achievements", "settings"]
        processed_updates = {}
        for key, value in updates.items():
            if key in json_fields and not isinstance(value, str):
                processed_updates[key] = json.dumps(value, ensure_ascii=False)
            else:
                processed_updates[key] = value

        processed_updates["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        set_clause = ", ".join([f"{k} = ?" for k in processed_updates.keys()])
        values = list(processed_updates.values()) + [user_id]

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f'UPDATE players SET {set_clause} WHERE user_id = ?',
                    values
                )
                return cursor.rowcount > 0

    def add_player_currency(self, user_id: str, coins: int = 0, diamonds: int = 0) -> bool:
        """增加玩家货币"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE players 
                    SET coins = coins + ?, diamonds = diamonds + ?,
                        updated_at = ?
                    WHERE user_id = ?
                ''', (coins, diamonds, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
                return cursor.rowcount > 0

    def consume_stamina(self, user_id: str, amount: int) -> bool:
        """
        消耗体力

        Returns:
            是否成功（体力不足返回False）
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # 先检查体力是否足够
                cursor.execute('SELECT stamina FROM players WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                if row is None or row["stamina"] < amount:
                    return False

                cursor.execute('''
                    UPDATE players SET stamina = stamina - ?, updated_at = ?
                    WHERE user_id = ?
                ''', (amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
                return True

    def restore_stamina(self, user_id: str, amount: int) -> int:
        """
        恢复体力

        Returns:
            恢复后的体力值
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE players 
                    SET stamina = MIN(stamina + ?, max_stamina), updated_at = ?
                    WHERE user_id = ?
                ''', (amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))

                cursor.execute('SELECT stamina FROM players WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                return row["stamina"] if row else 0

    def add_player_exp(self, user_id: str, exp: int) -> Dict:
        """
        增加玩家经验

        Returns:
            {"leveled_up": bool, "new_level": int}
        """
        result = {"leveled_up": False, "new_level": 0}

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT level, exp FROM players WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()

                if row is None:
                    return result

                current_level = row["level"]
                current_exp = row["exp"] + exp

                # 简单升级公式: level * 1000
                while current_level < 100:
                    exp_needed = current_level * 1000
                    if current_exp >= exp_needed:
                        current_exp -= exp_needed
                        current_level += 1
                        result["leveled_up"] = True
                    else:
                        break

                result["new_level"] = current_level

                cursor.execute('''
                    UPDATE players SET level = ?, exp = ?, updated_at = ?
                    WHERE user_id = ?
                ''', (current_level, current_exp,
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))

        return result

    def record_battle_result(self, user_id: str, is_win: bool):
        """记录战斗结果"""
        field = "wins" if is_win else "losses"
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    UPDATE players SET {field} = {field} + 1, updated_at = ?
                    WHERE user_id = ?
                ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))

    # ==================== 精灵操作 ====================

    def add_monster(self, owner_id: str, monster_data: Dict) -> bool:
        """
        添加精灵到玩家背包

        Args:
            owner_id: 玩家ID
            monster_data: 精灵数据字典（来自MonsterInstance.to_dict()）
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        instance_id = monster_data.get("instance_id")

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO monsters 
                    (instance_id, owner_id, data, is_in_team, team_position, created_at, updated_at)
                    VALUES (?, ?, ?, 0, -1, ?, ?)
                ''', (
                    instance_id,
                    owner_id,
                    json.dumps(monster_data, ensure_ascii=False),
                    now, now
                ))
                return True

    def get_player_monsters(self, owner_id: str) -> List[Dict]:
        """获取玩家所有精灵"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT data, is_in_team, team_position 
                    FROM monsters 
                    WHERE owner_id = ?
                    ORDER BY team_position DESC, created_at ASC
                ''', (owner_id,))

                monsters = []
                for row in cursor.fetchall():
                    monster = json.loads(row["data"])
                    monster["_is_in_team"] = bool(row["is_in_team"])
                    monster["_team_position"] = row["team_position"]
                    monsters.append(monster)

                return monsters

    def get_monster(self, instance_id: str) -> Optional[Dict]:
        """获取单个精灵数据"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT data FROM monsters WHERE instance_id = ?', (instance_id,))
                row = cursor.fetchone()

                if row is None:
                    return None

                return json.loads(row["data"])

    def update_monster(self, instance_id: str, monster_data: Dict) -> bool:
        """更新精灵数据"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE monsters SET data = ?, updated_at = ?
                    WHERE instance_id = ?
                ''', (json.dumps(monster_data, ensure_ascii=False), now, instance_id))
                return cursor.rowcount > 0

    def delete_monster(self, instance_id: str) -> bool:
        """删除精灵（放生）"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM monsters WHERE instance_id = ?', (instance_id,))
                return cursor.rowcount > 0

    def get_player_team(self, owner_id: str) -> List[Dict]:
        """获取玩家队伍精灵"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT data, team_position 
                    FROM monsters 
                    WHERE owner_id = ? AND is_in_team = 1
                    ORDER BY team_position ASC
                ''', (owner_id,))

                team = []
                for row in cursor.fetchall():
                    monster = json.loads(row["data"])
                    monster["_team_position"] = row["team_position"]
                    team.append(monster)

                return team

    def set_team(self, owner_id: str, monster_ids: List[str]) -> bool:
        """
        设置玩家队伍

        Args:
            owner_id: 玩家ID
            monster_ids: 精灵instance_id列表（按队伍顺序）
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 先清空原队伍
                cursor.execute('''
                    UPDATE monsters SET is_in_team = 0, team_position = -1, updated_at = ?
                    WHERE owner_id = ?
                ''', (now, owner_id))

                # 设置新队伍
                for position, instance_id in enumerate(monster_ids[:6]):  # 最多6只
                    cursor.execute('''
                        UPDATE monsters 
                        SET is_in_team = 1, team_position = ?, updated_at = ?
                        WHERE instance_id = ? AND owner_id = ?
                    ''', (position, now, instance_id, owner_id))

                return True

    def get_player_monster_count(self, owner_id: str) -> int:
        """获取玩家精灵数量"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as count FROM monsters WHERE owner_id = ?', (owner_id,))
                row = cursor.fetchone()
                return row["count"] if row else 0

    # ==================== 道具操作 ====================

    def get_inventory(self, owner_id: str) -> Dict[str, int]:
        """获取玩家背包道具"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT item_id, amount FROM inventory WHERE owner_id = ?', (owner_id,))

                inventory = {}
                for row in cursor.fetchall():
                    inventory[row["item_id"]] = row["amount"]

                return inventory

    def add_item(self, owner_id: str, item_id: str, amount: int = 1) -> int:
        """
        添加道具

        Returns:
            添加后的道具数量
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO inventory (owner_id, item_id, amount)
                    VALUES (?, ?, ?)
                    ON CONFLICT(owner_id, item_id) 
                    DO UPDATE SET amount = amount + ?
                ''', (owner_id, item_id, amount, amount))

                cursor.execute(
                    'SELECT amount FROM inventory WHERE owner_id = ? AND item_id = ?',
                    (owner_id, item_id)
                )
                row = cursor.fetchone()
                return row["amount"] if row else 0

    def consume_item(self, owner_id: str, item_id: str, amount: int = 1) -> bool:
        """
        消耗道具

        Returns:
            是否成功（数量不足返回False）
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 检查数量
                cursor.execute(
                    'SELECT amount FROM inventory WHERE owner_id = ? AND item_id = ?',
                    (owner_id, item_id)
                )
                row = cursor.fetchone()
                if row is None or row["amount"] < amount:
                    return False

                new_amount = row["amount"] - amount
                if new_amount <= 0:
                    cursor.execute(
                        'DELETE FROM inventory WHERE owner_id = ? AND item_id = ?',
                        (owner_id, item_id)
                    )
                else:
                    cursor.execute(
                        'UPDATE inventory SET amount = ? WHERE owner_id = ? AND item_id = ?',
                        (new_amount, owner_id, item_id)
                    )

                return True

    def get_item_count(self, owner_id: str, item_id: str) -> int:
        """获取道具数量"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT amount FROM inventory WHERE owner_id = ? AND item_id = ?',
                    (owner_id, item_id)
                )
                row = cursor.fetchone()
                return row["amount"] if row else 0

    # ==================== BOSS记录 ====================

    def get_boss_record(self, user_id: str, boss_id: str) -> Optional[Dict]:
        """获取BOSS击杀记录"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM boss_records 
                    WHERE user_id = ? AND boss_id = ?
                ''', (user_id, boss_id))
                row = cursor.fetchone()
                return dict(row) if row else None

    def record_boss_clear(self, user_id: str, boss_id: str,
                          time_seconds: int = None) -> Dict:
        """
        记录BOSS通关

        Returns:
            {"is_first_clear": bool, "clear_count": int}
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 检查是否首次
                cursor.execute('''
                    SELECT first_clear, clear_count, best_time_seconds 
                    FROM boss_records 
                    WHERE user_id = ? AND boss_id = ?
                ''', (user_id, boss_id))
                row = cursor.fetchone()

                if row is None:
                    # 首次击杀
                    cursor.execute('''
                        INSERT INTO boss_records 
                        (user_id, boss_id, first_clear, clear_count, last_clear_time, best_time_seconds)
                        VALUES (?, ?, 1, 1, ?, ?)
                    ''', (user_id, boss_id, now, time_seconds))
                    return {"is_first_clear": True, "clear_count": 1}
                else:
                    # 更新记录
                    new_count = row["clear_count"] + 1
                    best_time = row["best_time_seconds"]
                    if time_seconds and (best_time is None or time_seconds < best_time):
                        best_time = time_seconds

                    cursor.execute('''
                        UPDATE boss_records 
                        SET clear_count = ?, last_clear_time = ?, best_time_seconds = ?
                        WHERE user_id = ? AND boss_id = ?
                    ''', (new_count, now, best_time, user_id, boss_id))

                    return {"is_first_clear": False, "clear_count": new_count}

    def is_boss_first_cleared(self, user_id: str, boss_id: str) -> bool:
        """检查是否已首次通关BOSS"""
        record = self.get_boss_record(user_id, boss_id)
        return record is not None and record.get("first_clear", 0) == 1

    # ==================== 统计查询 ====================

    def get_leaderboard(self, order_by: str = "wins", limit: int = 10) -> List[Dict]:
        """获取排行榜"""
        valid_fields = ["wins", "level", "coins", "diamonds"]
        if order_by not in valid_fields:
            order_by = "wins"

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    SELECT user_id, name, level, wins, losses, coins 
                    FROM players 
                    ORDER BY {order_by} DESC 
                    LIMIT ?
                ''', (limit,))

                return [dict(row) for row in cursor.fetchall()]

    # ==================== 统计操作 ====================

    def get_total_players(self) -> int:
        """获取总玩家数"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as count FROM players')
                row = cursor.fetchone()
                return row["count"] if row else 0

    def get_total_monsters(self) -> int:
        """获取总精灵数（所有玩家）"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as count FROM monsters')
                row = cursor.fetchone()
                return row["count"] if row else 0

    def get_total_battles(self) -> int:
        """获取总战斗次数（胜场+败场）"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COALESCE(SUM(wins), 0) + COALESCE(SUM(losses), 0) as total FROM players')
                row = cursor.fetchone()
                return row["total"] if row else 0

    def get_players(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """获取玩家列表（分页）"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT p.user_id, p.name, p.level, p.coins, p.diamonds, 
                           p.stamina, p.wins, p.losses, p.created_at,
                           (SELECT COUNT(*) FROM monsters WHERE owner_id = p.user_id) as monster_count
                    FROM players p
                    ORDER BY p.created_at DESC
                    LIMIT ? OFFSET ?
                ''', (limit, offset))

                players = []
                for row in cursor.fetchall():
                    players.append(dict(row))
                return players

    def delete_player(self, user_id: str) -> bool:
        """删除玩家"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM players WHERE user_id = ?', (user_id,))
                return cursor.rowcount > 0

    def delete_player_monsters(self, user_id: str) -> int:
        """删除玩家所有精灵"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM monsters WHERE owner_id = ?', (user_id,))
                return cursor.rowcount

