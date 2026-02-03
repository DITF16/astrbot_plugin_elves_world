"""
世界/区域系统
- 地图生成与探索
- 天气系统
- 野外遭遇生成
- 事件触发
"""

import random
import uuid
from enum import Enum
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime

if TYPE_CHECKING:
    from .config_manager import ConfigManager
    from .monster import MonsterInstance


class CellType(Enum):
    """地图格子类型"""
    UNKNOWN = "unknown"  # 未探索（迷雾）
    EMPTY = "empty"  # 空地
    MONSTER = "monster"  # 野生精灵
    RARE_MONSTER = "rare"  # 稀有精灵
    TREASURE = "treasure"  # 宝箱
    RARE_TREASURE = "rare_treasure"  # 稀有宝箱
    EVENT = "event"  # 事件点
    BOSS = "boss"  # BOSS
    EXIT = "exit"  # 出口/传送点
    PLAYER = "player"  # 玩家当前位置


class EventType(Enum):
    """事件类型"""
    HEAL = "heal"  # 恢复HP
    BUFF = "buff"  # 临时增益
    TRAP = "trap"  # 陷阱（扣HP/体力）
    NPC = "npc"  # NPC对话
    PUZZLE = "puzzle"  # 谜题
    STORY = "story"  # 剧情


@dataclass
class MapCell:
    """地图格子"""
    x: int
    y: int
    cell_type: CellType = CellType.UNKNOWN
    is_explored: bool = False
    is_visible: bool = False  # 是否可见（迷雾战争）

    # 格子内容（根据类型不同而不同）
    monster_id: str = ""  # 精灵模板ID
    monster_level: int = 0  # 精灵等级
    treasure_items: List[Dict] = field(default_factory=list)  # 宝箱内容
    event_type: EventType = None  # 事件类型
    event_data: Dict = field(default_factory=dict)  # 事件数据
    boss_id: str = ""  # BOSS ID
    exit_to: str = ""  # 传送目标区域

    # 显示
    custom_icon: str = ""  # 自定义图标

    def get_icon(self, is_player_here: bool = False) -> str:
        """获取格子显示图标"""
        if is_player_here:
            return "👣"

        if self.custom_icon:
            return self.custom_icon

        if not self.is_explored and not self.is_visible:
            return "？"

        icons = {
            CellType.UNKNOWN: "？",
            CellType.EMPTY: "·",
            CellType.MONSTER: "🐾",
            CellType.RARE_MONSTER: "⭐",
            CellType.TREASURE: "🎁",
            CellType.RARE_TREASURE: "💎",
            CellType.EVENT: "🏚️",
            CellType.BOSS: "👹",
            CellType.EXIT: "🚪",
        }
        return icons.get(self.cell_type, "·")

    def to_dict(self) -> Dict:
        """转为字典"""
        return {
            "x": self.x,
            "y": self.y,
            "cell_type": self.cell_type.value,
            "is_explored": self.is_explored,
            "is_visible": self.is_visible,
            "monster_id": self.monster_id,
            "monster_level": self.monster_level,
            "treasure_items": self.treasure_items,
            "event_type": self.event_type.value if self.event_type else None,
            "event_data": self.event_data,
            "boss_id": self.boss_id,
            "exit_to": self.exit_to,
            "custom_icon": self.custom_icon,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "MapCell":
        """从字典恢复"""
        cell = cls(x=data["x"], y=data["y"])
        cell.cell_type = CellType(data.get("cell_type", "unknown"))
        cell.is_explored = data.get("is_explored", False)
        cell.is_visible = data.get("is_visible", False)
        cell.monster_id = data.get("monster_id", "")
        cell.monster_level = data.get("monster_level", 0)
        cell.treasure_items = data.get("treasure_items", [])
        event_type_str = data.get("event_type")
        cell.event_type = EventType(event_type_str) if event_type_str else None
        cell.event_data = data.get("event_data", {})
        cell.boss_id = data.get("boss_id", "")
        cell.exit_to = data.get("exit_to", "")
        cell.custom_icon = data.get("custom_icon", "")
        return cell


@dataclass
class ExplorationMap:
    """
    探索地图
    保存玩家在某个区域的探索状态
    """
    map_id: str = ""
    region_id: str = ""
    player_id: str = ""

    # 地图尺寸
    width: int = 5
    height: int = 5

    # 玩家位置
    player_x: int = 0
    player_y: int = 0

    # 地图格子 (使用字典存储，key为"x,y")
    cells: Dict[str, MapCell] = field(default_factory=dict)

    # 天气
    weather: str = "clear"
    weather_turns: int = 0  # 剩余回合，0=永久

    # 探索统计
    explored_count: int = 0
    monsters_defeated: int = 0
    treasures_found: int = 0

    # 状态
    is_completed: bool = False  # 是否完成（找到出口/击败BOSS）
    created_at: str = ""

    def get_cell(self, x: int, y: int) -> Optional[MapCell]:
        """获取指定坐标的格子"""
        key = f"{x},{y}"
        return self.cells.get(key)

    def set_cell(self, x: int, y: int, cell: MapCell):
        """设置格子"""
        key = f"{x},{y}"
        self.cells[key] = cell

    def is_valid_position(self, x: int, y: int) -> bool:
        """检查坐标是否有效"""
        return 0 <= x < self.width and 0 <= y < self.height

    def get_adjacent_positions(self, x: int, y: int) -> List[Tuple[int, int]]:
        """获取相邻格子坐标（上下左右）"""
        directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        adjacent = []
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if self.is_valid_position(nx, ny):
                adjacent.append((nx, ny))
        return adjacent

    def reveal_adjacent(self, x: int, y: int):
        """揭示相邻格子（可见但未探索）"""
        for nx, ny in self.get_adjacent_positions(x, y):
            cell = self.get_cell(nx, ny)
            if cell and not cell.is_explored:
                cell.is_visible = True

    def get_total_cells(self) -> int:
        """获取总格子数"""
        return self.width * self.height

    def to_dict(self) -> Dict:
        """转为字典（用于存储）"""
        return {
            "map_id": self.map_id,
            "region_id": self.region_id,
            "player_id": self.player_id,
            "width": self.width,
            "height": self.height,
            "player_x": self.player_x,
            "player_y": self.player_y,
            "cells": {k: v.to_dict() for k, v in self.cells.items()},
            "weather": self.weather,
            "weather_turns": self.weather_turns,
            "explored_count": self.explored_count,
            "monsters_defeated": self.monsters_defeated,
            "treasures_found": self.treasures_found,
            "is_completed": self.is_completed,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ExplorationMap":
        """从字典恢复"""
        exp_map = cls()
        exp_map.map_id = data.get("map_id", "")
        exp_map.region_id = data.get("region_id", "")
        exp_map.player_id = data.get("player_id", "")
        exp_map.width = data.get("width", 5)
        exp_map.height = data.get("height", 5)
        exp_map.player_x = data.get("player_x", 0)
        exp_map.player_y = data.get("player_y", 0)
        exp_map.cells = {
            k: MapCell.from_dict(v) for k, v in data.get("cells", {}).items()
        }
        exp_map.weather = data.get("weather", "clear")
        exp_map.weather_turns = data.get("weather_turns", 0)
        exp_map.explored_count = data.get("explored_count", 0)
        exp_map.monsters_defeated = data.get("monsters_defeated", 0)
        exp_map.treasures_found = data.get("treasures_found", 0)
        exp_map.is_completed = data.get("is_completed", False)
        exp_map.created_at = data.get("created_at", "")
        return exp_map


@dataclass
class ExploreResult:
    """探索结果"""
    success: bool = True
    cell_type: CellType = CellType.EMPTY
    message: str = ""

    # 遭遇战斗
    encounter_battle: bool = False
    monster_data: Dict = field(default_factory=dict)
    is_boss: bool = False
    boss_id: str = ""

    # 获得奖励
    items_gained: List[Dict] = field(default_factory=list)
    coins_gained: int = 0
    exp_gained: int = 0

    # 事件
    event_type: EventType = None
    event_message: str = ""

    # 地图状态
    map_completed: bool = False
    can_exit: bool = False
    exit_to_region: str = ""


class WorldManager:
    """
    世界/区域管理器

    负责：
    - 地图生成
    - 探索处理
    - 天气管理
    - 野外遭遇
    """

    # 默认地图尺寸配置
    DEFAULT_MAP_SIZES = {
        "small": (4, 4),
        "medium": (5, 5),
        "large": (6, 6),
        "huge": (8, 8),
    }

    # 格子类型生成权重（百分比）
    DEFAULT_CELL_WEIGHTS = {
        CellType.EMPTY: 40,
        CellType.MONSTER: 30,
        CellType.TREASURE: 15,
        CellType.EVENT: 10,
        CellType.RARE_MONSTER: 4,
        CellType.RARE_TREASURE: 1,
    }

    def __init__(self, config_manager: "ConfigManager"):
        """初始化世界管理器"""
        self.config = config_manager

        # 活跃的探索地图缓存 {player_id: ExplorationMap}
        self._active_maps: Dict[str, ExplorationMap] = {}

    # ==================== 区域信息 ====================

    def get_region(self, region_id: str) -> Optional[Dict]:
        """获取区域配置"""
        return self.config.get_item("regions", region_id)

    def get_all_regions(self) -> Dict[str, Dict]:
        """获取所有区域"""
        return self.config.regions

    def get_available_regions(self, player: Dict) -> List[Dict]:
        """
        获取玩家可进入的区域列表

        Args:
            player: 玩家数据

        Returns:
            可进入的区域列表
        """
        available = []
        player_level = player.get("level", 1)

        for region_id, region in self.config.regions.items():
            unlock = region.get("unlock_condition")

            # 无条件解锁
            if not unlock:
                available.append({"id": region_id, **region})
                continue

            # 等级条件
            if unlock.get("type") == "level":
                if player_level >= unlock.get("value", 1):
                    available.append({"id": region_id, **region})
                continue

            # BOSS通关条件（需要外部检查）
            # 这里简化处理，实际应该查询数据库
            if unlock.get("type") == "boss_clear":
                # 暂时跳过，由调用方检查
                pass

        return available

    def get_region_info_text(self, region_id: str) -> str:
        """获取区域信息文本"""
        region = self.get_region(region_id)
        if not region:
            return "未知区域"

        level_range = region.get("level_range", [1, 10])
        stamina_cost = region.get("stamina_cost", 10)

        # 野生精灵列表
        wild_monsters = region.get("wild_monsters", [])
        monster_names = []
        for wm in wild_monsters[:5]:  # 最多显示5个
            template = self.config.get_item("monsters", wm.get("monster_id", ""))
            if template:
                monster_names.append(template.get("name", "???"))

        monsters_text = "、".join(monster_names) if monster_names else "无"

        # BOSS
        boss_ids = region.get("boss_ids", [])
        boss_names = []
        for bid in boss_ids:
            boss = self.config.get_item("bosses", bid)
            if boss:
                boss_names.append(boss.get("name", "???"))
        boss_text = "、".join(boss_names) if boss_names else "无"

        return (
            f"📍 {region.get('name', region_id)}\n"
            f"{'─' * 24}\n"
            f"{region.get('description', '')}\n"
            f"{'─' * 24}\n"
            f"等级范围: Lv.{level_range[0]} ~ Lv.{level_range[1]}\n"
            f"消耗体力: {stamina_cost}\n"
            f"野生精灵: {monsters_text}\n"
            f"BOSS: {boss_text}"
        )

    # ==================== 天气系统 ====================

    def roll_weather(self, region_id: str) -> str:
        """
        根据区域配置随机天气

        Returns:
            天气ID
        """
        region = self.get_region(region_id)
        if not region:
            return "clear"

        weather_pool = region.get("weather_pool", [])
        if not weather_pool:
            return "clear"

        # 按权重随机
        total_weight = sum(w.get("weight", 1) for w in weather_pool)
        roll = random.randint(1, total_weight)

        current = 0
        for w in weather_pool:
            current += w.get("weight", 1)
            if roll <= current:
                return w.get("weather_id", "clear")

        return "clear"

    def get_weather_info(self, weather_id: str) -> Dict:
        """获取天气信息"""
        return self.config.get_item("weathers", weather_id) or {
            "id": "clear", "name": "晴朗", "icon": "☀️"
        }

    # ==================== 地图生成 ====================

    def generate_map(self,
                     region_id: str,
                     player_id: str,
                     player_level: int = 1) -> ExplorationMap:
        """
        生成探索地图

        Args:
            region_id: 区域ID
            player_id: 玩家ID
            player_level: 玩家等级

        Returns:
            生成的探索地图
        """
        region = self.get_region(region_id)
        if not region:
            # 默认区域配置
            region = {
                "name": "未知区域",
                "level_range": [1, 10],
                "wild_monsters": [],
                "weather_pool": [{"weather_id": "clear", "weight": 100}],
            }

        # 确定地图尺寸
        map_size = region.get("map_size", "medium")
        if isinstance(map_size, str):
            width, height = self.DEFAULT_MAP_SIZES.get(map_size, (5, 5))
        elif isinstance(map_size, list) and len(map_size) == 2:
            width, height = map_size
        else:
            width, height = 5, 5

        # 创建地图
        exp_map = ExplorationMap(
            map_id=str(uuid.uuid4())[:8],
            region_id=region_id,
            player_id=player_id,
            width=width,
            height=height,
            weather=self.roll_weather(region_id),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        # 获取区域等级范围
        level_range = region.get("level_range", [1, 10])
        min_level, max_level = level_range[0], level_range[1]

        # 获取区域野生精灵配置
        wild_monsters = region.get("wild_monsters", [])

        # 生成所有格子
        for y in range(height):
            for x in range(width):
                cell = self._generate_cell(
                    x, y, width, height,
                    region, wild_monsters,
                    min_level, max_level, player_level
                )
                exp_map.set_cell(x, y, cell)

        # 确保有出口
        self._ensure_exit(exp_map, region)

        # 确保有BOSS（如果区域配置了BOSS）
        # 支持两种格式：boss_ids (数组) 或 boss (单个字符串)
        boss_ids = region.get("boss_ids", [])
        if not boss_ids:
            # 兼容旧格式：单个boss字段
            single_boss = region.get("boss", "")
            if single_boss:
                boss_ids = [single_boss]
        if boss_ids:
            self._place_boss(exp_map, boss_ids[0])

        # 设置玩家初始位置（左上角或随机安全位置）
        start_x, start_y = self._find_start_position(exp_map)
        exp_map.player_x = start_x
        exp_map.player_y = start_y

        # 标记起始位置为已探索，并揭示周围
        start_cell = exp_map.get_cell(start_x, start_y)
        if start_cell:
            start_cell.is_explored = True
            start_cell.cell_type = CellType.EMPTY  # 起点一定是安全的
            exp_map.explored_count = 1
        exp_map.reveal_adjacent(start_x, start_y)

        # 缓存地图
        self._active_maps[player_id] = exp_map

        return exp_map

    def _generate_cell(self,
                       x: int, y: int,
                       width: int, height: int,
                       region: Dict,
                       wild_monsters: List[Dict],
                       min_level: int, max_level: int,
                       player_level: int) -> MapCell:
        """生成单个格子"""
        cell = MapCell(x=x, y=y)

        # 按权重随机类型
        cell_weights = region.get("cell_weights", self.DEFAULT_CELL_WEIGHTS)
        if isinstance(cell_weights, dict):
            # 转换字符串key为CellType
            weights = {}
            for k, v in cell_weights.items():
                if isinstance(k, str):
                    try:
                        weights[CellType(k)] = v
                    except ValueError:
                        pass
                else:
                    weights[k] = v
        else:
            weights = self.DEFAULT_CELL_WEIGHTS

        total = sum(weights.values())
        roll = random.randint(1, total)

        current = 0
        cell_type = CellType.EMPTY
        for ct, weight in weights.items():
            current += weight
            if roll <= current:
                cell_type = ct
                break

        cell.cell_type = cell_type

        # 根据类型填充内容
        if cell_type in [CellType.MONSTER, CellType.RARE_MONSTER]:
            self._fill_monster_cell(cell, wild_monsters, min_level, max_level,
                                    player_level, is_rare=(cell_type == CellType.RARE_MONSTER))

        elif cell_type in [CellType.TREASURE, CellType.RARE_TREASURE]:
            self._fill_treasure_cell(cell, region, is_rare=(cell_type == CellType.RARE_TREASURE))

        elif cell_type == CellType.EVENT:
            self._fill_event_cell(cell)

        return cell

    def _fill_monster_cell(self,
                           cell: MapCell,
                           wild_monsters: List[Dict],
                           min_level: int, max_level: int,
                           player_level: int,
                           is_rare: bool = False):
        """填充精灵格子"""
        if not wild_monsters:
            cell.cell_type = CellType.EMPTY
            return

        # 稀有精灵选择权重低的
        if is_rare:
            # 按权重排序，选择权重最低的（最稀有）
            sorted_monsters = sorted(wild_monsters, key=lambda m: m.get("weight", 50))
            candidates = sorted_monsters[:max(1, len(sorted_monsters) // 3)]
        else:
            candidates = wild_monsters

        # 按权重随机
        total_weight = sum(m.get("weight", 50) for m in candidates)
        roll = random.randint(1, max(1, total_weight))

        current = 0
        selected = candidates[0] if candidates else None
        for m in candidates:
            current += m.get("weight", 50)
            if roll <= current:
                selected = m
                break

        if selected:
            cell.monster_id = selected.get("monster_id", "")
            level_offset = selected.get("level_offset", 0)

            # 基于玩家等级和区域等级范围计算精灵等级
            base_level = max(min_level, min(player_level + level_offset, max_level))
            cell.monster_level = base_level + random.randint(-2, 2)
            cell.monster_level = max(min_level, min(cell.monster_level, max_level))

    def _fill_treasure_cell(self, cell: MapCell, region: Dict, is_rare: bool = False):
        """填充宝箱格子"""
        items = []

        if is_rare:
            # 稀有宝箱：钻石 + 稀有道具
            items.append({"item_id": "_diamonds", "amount": random.randint(10, 30)})
            items.append({"item_id": "_coins", "amount": random.randint(500, 1000)})
        else:
            # 普通宝箱：金币 + 普通道具
            items.append({"item_id": "_coins", "amount": random.randint(100, 300)})

            # 随机道具
            if random.random() < 0.5:
                common_items = ["potion", "pokeball", "antidote"]
                items.append({
                    "item_id": random.choice(common_items),
                    "amount": random.randint(1, 3)
                })

        cell.treasure_items = items

    def _fill_event_cell(self, cell: MapCell):
        """填充事件格子"""
        events = [
            (EventType.HEAL, 40, {"heal_percent": 30, "message": "发现了神秘的治愈泉水！"}),
            (EventType.BUFF, 20, {"buff_type": "attack", "turns": 5, "message": "获得了力量祝福！"}),
            (EventType.TRAP, 25, {"damage_percent": 15, "message": "触发了陷阱！"}),
            (EventType.STORY, 15, {"message": "发现了一块古老的石碑..."}),
        ]

        total = sum(e[1] for e in events)
        roll = random.randint(1, total)

        current = 0
        for event_type, weight, data in events:
            current += weight
            if roll <= current:
                cell.event_type = event_type
                cell.event_data = data
                break

    def _ensure_exit(self, exp_map: ExplorationMap, region: Dict):
        """确保地图有出口"""
        # 在右下角区域放置出口
        exit_x = exp_map.width - 1
        exit_y = exp_map.height - 1

        # 尝试找一个合适的出口位置
        for dx, dy in [(0, 0), (-1, 0), (0, -1), (-1, -1)]:
            x, y = exit_x + dx, exit_y + dy
            if exp_map.is_valid_position(x, y):
                cell = exp_map.get_cell(x, y)
                if cell and cell.cell_type not in [CellType.BOSS]:
                    cell.cell_type = CellType.EXIT
                    cell.exit_to = region.get("exit_to", "")
                    return

    def _place_boss(self, exp_map: ExplorationMap, boss_id: str):
        """在地图上放置BOSS"""
        # 在远离起点的位置放置BOSS
        best_x, best_y = exp_map.width // 2, exp_map.height // 2
        max_distance = 0

        for y in range(exp_map.height):
            for x in range(exp_map.width):
                distance = abs(x) + abs(y)  # 曼哈顿距离（从左上角起点）
                cell = exp_map.get_cell(x, y)
                if cell and cell.cell_type not in [CellType.EXIT] and distance > max_distance:
                    max_distance = distance
                    best_x, best_y = x, y

        boss_cell = exp_map.get_cell(best_x, best_y)
        if boss_cell:
            boss_cell.cell_type = CellType.BOSS
            boss_cell.boss_id = boss_id
            boss_cell.custom_icon = "👹"

    def _find_start_position(self, exp_map: ExplorationMap) -> Tuple[int, int]:
        """找到安全的起始位置"""
        # 优先左上角
        for y in range(min(2, exp_map.height)):
            for x in range(min(2, exp_map.width)):
                cell = exp_map.get_cell(x, y)
                if cell and cell.cell_type in [CellType.EMPTY, CellType.UNKNOWN]:
                    return (x, y)

        # 找任意空地
        for y in range(exp_map.height):
            for x in range(exp_map.width):
                cell = exp_map.get_cell(x, y)
                if cell and cell.cell_type == CellType.EMPTY:
                    return (x, y)

        return (0, 0)

    # ==================== 地图探索 ====================

    def get_active_map(self, player_id: str) -> Optional[ExplorationMap]:
        """获取玩家当前活跃的探索地图"""
        return self._active_maps.get(player_id)

    def set_active_map(self, player_id: str, exp_map: ExplorationMap):
        """设置玩家活跃地图"""
        self._active_maps[player_id] = exp_map

    def clear_active_map(self, player_id: str):
        """清除玩家活跃地图"""
        if player_id in self._active_maps:
            del self._active_maps[player_id]

    def parse_coordinate(self, coord_str: str, exp_map: ExplorationMap) -> Optional[Tuple[int, int]]:
        """
        解析坐标字符串

        支持格式:
        - "A1", "B2", "C3" (字母+数字)
        - "1,2", "1 2" (x,y数字)
        - "12" (两位数字，第一位x第二位y)

        Returns:
            (x, y) 或 None
        """
        coord_str = coord_str.strip().upper()

        if not coord_str:
            return None

        # 格式1: 字母+数字 (A1, B2, ...)
        if len(coord_str) >= 2 and coord_str[0].isalpha():
            col = ord(coord_str[0]) - ord('A')
            try:
                row = int(coord_str[1:]) - 1
                if exp_map.is_valid_position(col, row):
                    return (col, row)
            except ValueError:
                pass

        # 格式2: 数字,数字 或 数字 数字
        if ',' in coord_str or ' ' in coord_str:
            parts = coord_str.replace(',', ' ').split()
            if len(parts) == 2:
                try:
                    x, y = int(parts[0]), int(parts[1])
                    if exp_map.is_valid_position(x, y):
                        return (x, y)
                except ValueError:
                    pass

        # 格式3: 两位数字 (如 "12" 表示 x=1, y=2)
        if len(coord_str) == 2 and coord_str.isdigit():
            x, y = int(coord_str[0]), int(coord_str[1])
            if exp_map.is_valid_position(x, y):
                return (x, y)

        return None

    def explore_cell(self,
                     player_id: str,
                     target_x: int,
                     target_y: int,
                     player_level: int = 1) -> ExploreResult:
        """
        探索指定格子

        Args:
            player_id: 玩家ID
            target_x: 目标X坐标
            target_y: 目标Y坐标
            player_level: 玩家等级

        Returns:
            探索结果
        """
        result = ExploreResult()

        exp_map = self.get_active_map(player_id)
        if not exp_map:
            result.success = False
            result.message = "你没有正在探索的地图！请先进入一个区域。"
            return result

        # 检查坐标有效性
        if not exp_map.is_valid_position(target_x, target_y):
            result.success = False
            result.message = "无效的坐标！"
            return result

        # 检查是否可达（必须与当前位置相邻或是当前位置）
        current_x, current_y = exp_map.player_x, exp_map.player_y
        distance = abs(target_x - current_x) + abs(target_y - current_y)

        if distance > 1:
            result.success = False
            result.message = "只能探索相邻的格子！"
            return result

        if distance == 0:
            result.success = False
            result.message = "你已经在这个位置了！"
            return result

        # 获取目标格子
        cell = exp_map.get_cell(target_x, target_y)
        if not cell:
            result.success = False
            result.message = "格子数据异常！"
            return result

        # 移动玩家
        exp_map.player_x = target_x
        exp_map.player_y = target_y

        # 标记为已探索
        if not cell.is_explored:
            cell.is_explored = True
            exp_map.explored_count += 1

        # 揭示周围格子
        exp_map.reveal_adjacent(target_x, target_y)

        # 处理格子内容
        result.cell_type = cell.cell_type

        if cell.cell_type == CellType.EMPTY:
            result.message = "这里是一片空地。"

        elif cell.cell_type in [CellType.MONSTER, CellType.RARE_MONSTER]:
            result = self._handle_monster_cell(cell, exp_map, player_level)

        elif cell.cell_type in [CellType.TREASURE, CellType.RARE_TREASURE]:
            result = self._handle_treasure_cell(cell, exp_map)

        elif cell.cell_type == CellType.EVENT:
            result = self._handle_event_cell(cell, exp_map)

        elif cell.cell_type == CellType.BOSS:
            result = self._handle_boss_cell(cell, exp_map, player_level)

        elif cell.cell_type == CellType.EXIT:
            result = self._handle_exit_cell(cell, exp_map)

        return result

    def _handle_monster_cell(self,
                             cell: MapCell,
                             exp_map: ExplorationMap,
                             player_level: int) -> ExploreResult:
        """处理精灵格子"""
        result = ExploreResult(success=True, cell_type=cell.cell_type)

        monster_template = self.config.get_item("monsters", cell.monster_id)
        if not monster_template:
            result.message = "遇到了一只神秘的精灵...但它消失了。"
            cell.cell_type = CellType.EMPTY
            return result

        monster_name = monster_template.get("name", "???")
        is_rare = cell.cell_type == CellType.RARE_MONSTER

        # 生成精灵实例数据
        from .monster import MonsterInstance

        monster_instance = MonsterInstance.from_template(
            template=monster_template,
            level=cell.monster_level,
            config_manager=self.config,
            caught_region=exp_map.region_id,
        )

        result.encounter_battle = True
        result.monster_data = monster_instance.to_dict()

        if is_rare:
            result.message = f"⭐ 发现了稀有精灵 {monster_name} Lv.{cell.monster_level}！"
        else:
            result.message = f"🐾 野生的 {monster_name} Lv.{cell.monster_level} 出现了！"

        return result

    def _handle_treasure_cell(self,
                              cell: MapCell,
                              exp_map: ExplorationMap) -> ExploreResult:
        """处理宝箱格子"""
        result = ExploreResult(success=True, cell_type=cell.cell_type)

        is_rare = cell.cell_type == CellType.RARE_TREASURE
        items = cell.treasure_items

        if not items:
            result.message = "宝箱是空的..."
            cell.cell_type = CellType.EMPTY
            return result

        # 处理奖励
        reward_messages = []
        for item in items:
            item_id = item.get("item_id", "")
            amount = item.get("amount", 1)

            if item_id == "_coins":
                result.coins_gained += amount
                reward_messages.append(f"💰 {amount} 金币")
            elif item_id == "_diamonds":
                result.items_gained.append({"item_id": "_diamonds", "amount": amount})
                reward_messages.append(f"💎 {amount} 钻石")
            elif item_id == "_exp":
                result.exp_gained += amount
                reward_messages.append(f"✨ {amount} 经验")
            else:
                result.items_gained.append(item)
                item_config = self.config.get_item("items", item_id)
                item_name = item_config.get("name", item_id) if item_config else item_id
                reward_messages.append(f"📦 {item_name} x{amount}")

        exp_map.treasures_found += 1

        if is_rare:
            result.message = f"💎 发现了稀有宝箱！\n获得: " + "、".join(reward_messages)
        else:
            result.message = f"🎁 发现了宝箱！\n获得: " + "、".join(reward_messages)

        # 标记为已清空
        cell.cell_type = CellType.EMPTY
        cell.treasure_items = []

        return result

    def _handle_event_cell(self,
                           cell: MapCell,
                           exp_map: ExplorationMap) -> ExploreResult:
        """处理事件格子"""
        result = ExploreResult(success=True, cell_type=cell.cell_type)
        result.event_type = cell.event_type

        event_message = cell.event_data.get("message", "发生了一些事情...")

        if cell.event_type == EventType.HEAL:
            heal_percent = cell.event_data.get("heal_percent", 30)
            result.event_message = f"💚 {event_message}\n队伍精灵恢复了 {heal_percent}% HP！"
            result.message = result.event_message

        elif cell.event_type == EventType.BUFF:
            buff_type = cell.event_data.get("buff_type", "attack")
            turns = cell.event_data.get("turns", 5)
            result.event_message = f"⬆️ {event_message}\n获得 {turns} 回合的增益效果！"
            result.message = result.event_message

        elif cell.event_type == EventType.TRAP:
            damage_percent = cell.event_data.get("damage_percent", 15)
            result.event_message = f"💥 {event_message}\n队伍精灵受到了 {damage_percent}% 伤害！"
            result.message = result.event_message

        elif cell.event_type == EventType.STORY:
            result.event_message = f"📜 {event_message}"
            result.message = result.event_message

        else:
            result.message = f"🏚️ {event_message}"

        # 标记为已触发
        cell.cell_type = CellType.EMPTY

        return result

    def _handle_boss_cell(self,
                          cell: MapCell,
                          exp_map: ExplorationMap,
                          player_level: int) -> ExploreResult:
        """处理BOSS格子"""
        result = ExploreResult(success=True, cell_type=cell.cell_type)

        boss_config = self.config.get_item("bosses", cell.boss_id)
        if not boss_config:
            result.message = "BOSS已经离开了..."
            cell.cell_type = CellType.EMPTY
            return result

        boss_name = boss_config.get("name", "???")
        boss_level = boss_config.get("level", 30)

        result.encounter_battle = True
        result.is_boss = True
        result.boss_id = cell.boss_id
        result.message = f"👹 BOSS {boss_name} Lv.{boss_level} 挡住了去路！\n准备战斗！"

        return result

    def _handle_exit_cell(self,
                          cell: MapCell,
                          exp_map: ExplorationMap) -> ExploreResult:
        """处理出口格子"""
        result = ExploreResult(success=True, cell_type=cell.cell_type)

        result.can_exit = True
        result.exit_to_region = cell.exit_to

        # 检查是否完成探索（可选条件）
        explore_percent = exp_map.explored_count / exp_map.get_total_cells() * 100

        result.message = (
            f"🚪 找到了出口！\n"
            f"探索进度: {exp_map.explored_count}/{exp_map.get_total_cells()} ({explore_percent:.0f}%)\n"
            f"击败精灵: {exp_map.monsters_defeated}\n"
            f"发现宝箱: {exp_map.treasures_found}\n\n"
            f"输入 '离开' 结束探索，或继续探索其他区域。"
        )

        return result

    def complete_exploration(self, player_id: str) -> Dict:
        """
        完成探索，结算奖励

        Returns:
            {"success": bool, "message": str, "rewards": dict}
        """
        exp_map = self.get_active_map(player_id)
        if not exp_map:
            return {"success": False, "message": "没有正在进行的探索。", "rewards": {}}

        # 计算探索奖励
        explore_percent = exp_map.explored_count / exp_map.get_total_cells()

        base_coins = 100
        bonus_coins = int(base_coins * explore_percent * 2)
        total_coins = base_coins + bonus_coins

        base_exp = 50
        bonus_exp = int(base_exp * explore_percent * 2)
        total_exp = base_exp + bonus_exp

        rewards = {
            "coins": total_coins,
            "exp": total_exp,
            "explored": exp_map.explored_count,
            "total_cells": exp_map.get_total_cells(),
            "monsters_defeated": exp_map.monsters_defeated,
            "treasures_found": exp_map.treasures_found,
        }

        # 清除地图
        exp_map.is_completed = True
        self.clear_active_map(player_id)

        message = (
            f"🏁 探索完成！\n"
            f"{'─' * 20}\n"
            f"探索进度: {exp_map.explored_count}/{exp_map.get_total_cells()}\n"
            f"击败精灵: {exp_map.monsters_defeated}\n"
            f"发现宝箱: {exp_map.treasures_found}\n"
            f"{'─' * 20}\n"
            f"获得奖励:\n"
            f"  💰 {total_coins} 金币\n"
            f"  ✨ {total_exp} 经验"
        )

        return {"success": True, "message": message, "rewards": rewards}

    def mark_monster_defeated(self, player_id: str):
        """标记击败了一只精灵"""
        exp_map = self.get_active_map(player_id)
        if exp_map:
            exp_map.monsters_defeated += 1
            # 将当前格子标记为空地
            cell = exp_map.get_cell(exp_map.player_x, exp_map.player_y)
            if cell and cell.cell_type in [CellType.MONSTER, CellType.RARE_MONSTER]:
                cell.cell_type = CellType.EMPTY

    def mark_boss_defeated(self, player_id: str):
        """标记击败了BOSS"""
        exp_map = self.get_active_map(player_id)
        if exp_map:
            cell = exp_map.get_cell(exp_map.player_x, exp_map.player_y)
            if cell and cell.cell_type == CellType.BOSS:
                cell.cell_type = CellType.EMPTY
                cell.boss_id = ""

    # ==================== 地图渲染 ====================

    def render_map(self, exp_map: ExplorationMap, show_hidden: bool = False) -> str:
        """
        渲染地图为文本

        Args:
            exp_map: 探索地图
            show_hidden: 是否显示隐藏格子（调试用）

        Returns:
            地图文本
        """
        # 获取区域和天气信息
        region = self.get_region(exp_map.region_id)
        region_name = region.get("name", exp_map.region_id) if region else exp_map.region_id

        weather_info = self.get_weather_info(exp_map.weather)
        weather_icon = weather_info.get("icon", "")
        weather_name = weather_info.get("name", "")

        lines = []

        # 标题
        lines.append(f"📍 {region_name}")
        if exp_map.weather != "clear":
            lines.append(f"天气: {weather_icon} {weather_name}")
        lines.append("─" * (exp_map.width * 3 + 4))

        # 列标题 (A, B, C, ...)
        col_header = "    "
        for x in range(exp_map.width):
            col_header += f" {chr(ord('A') + x)} "
        lines.append(col_header)

        # 地图主体
        for y in range(exp_map.height):
            row_str = f" {y + 1}  "
            for x in range(exp_map.width):
                cell = exp_map.get_cell(x, y)
                is_player = (x == exp_map.player_x and y == exp_map.player_y)

                if cell:
                    if is_player:
                        icon = "👣"
                    elif show_hidden or cell.is_explored or cell.is_visible:
                        icon = cell.get_icon()
                    else:
                        icon = "？"
                else:
                    icon = "·"

                row_str += f"{icon} "

            lines.append(row_str)

        lines.append("─" * (exp_map.width * 3 + 4))

        # 图例
        lines.append("👣你 🐾精灵 ⭐稀有 🎁宝箱 👹BOSS")
        lines.append("🚪出口 🏚️事件 ？未知 ·空地")

        lines.append("─" * (exp_map.width * 3 + 4))

        # 状态信息
        total_cells = exp_map.get_total_cells()
        explored_percent = exp_map.explored_count / total_cells * 100
        lines.append(f"探索: {exp_map.explored_count}/{total_cells} ({explored_percent:.0f}%)")
        lines.append(f"位置: {chr(ord('A') + exp_map.player_x)}{exp_map.player_y + 1}")

        # 操作提示
        lines.append("─" * (exp_map.width * 3 + 4))

        return "\n".join(lines)




# ==================== 地图图片渲染器 ====================

class MapImageRenderer:
    """
    地图图片渲染器
    
    将探索地图渲染为图片，解决文字地图在不同客户端排版错乱的问题。
    使用 Pillow 进行图片渲染，支持异步并发。
    
    特性：
    - 异步渲染：使用 asyncio.to_thread() 避免阻塞事件循环
    - 图片缓存：基于地图状态哈希的缓存机制
    - 美观设计：使用配色方案和图标
    """
    
    # 配色方案
    COLORS = {
        'background': (45, 45, 55),        # 深灰背景
        'grid_line': (70, 70, 80),         # 网格线
        'text': (220, 220, 220),           # 普通文字
        'text_dim': (140, 140, 150),       # 暗淡文字
        'header_bg': (35, 35, 45),         # 标题背景
        'cell_empty': (60, 60, 70),        # 空地
        'cell_unknown': (50, 50, 60),      # 未知
        'cell_player': (100, 200, 100),    # 玩家位置
        'cell_monster': (200, 150, 100),   # 精灵
        'cell_rare': (255, 215, 0),        # 稀有精灵
        'cell_treasure': (100, 180, 255),  # 宝箱
        'cell_boss': (220, 80, 80),        # Boss
        'cell_exit': (150, 220, 150),      # 出口
        'cell_event': (180, 130, 200),     # 事件
    }
    
    # 图标映射（使用 Emoji 符号，需要 NotoColorEmoji 字体支持）
    ICONS = {
        'player': '👣',      # 玩家位置
        'monster': '🐾',     # 普通精灵
        'rare': '⭐',        # 稀有精灵
        'treasure': '🎁',    # 宝箱
        'boss': '👹',        # Boss
        'exit': '🚪',        # 出口
        'event': '🏚️',       # 事件
        'unknown': '❓',     # 未知
        'empty': '·',        # 空地（保持ASCII，因为是小点）
    }

    
    def __init__(self, 
                 cell_size: int = 48,
                 padding: int = 20,
                 font_size: int = 16,
                 cache_enabled: bool = True):
        """
        初始化渲染器
        
        Args:
            cell_size: 每个格子的像素大小
            padding: 图片边距
            font_size: 普通文字字体大小
            cache_enabled: 是否启用缓存
        """
        self.cell_size = cell_size
        self.padding = padding
        self.font_size = font_size
        self.cache_enabled = cache_enabled
        
        # 内存缓存
        self._cache: Dict[str, bytes] = {}
        self._cache_max_size = 50
        
        # 字体（延迟加载）
        self._font = None
        self._emoji_font = None  # Emoji 专用字体
    
    def _get_font(self):
        """获取普通字体，延迟加载"""
        if self._font is None:
            self._font = self._load_font(self.font_size)
        return self._font
    
    def _get_emoji_font(self):
        """获取 Emoji 字体，延迟加载"""
        if self._emoji_font is None:
            self._emoji_font = self._load_emoji_font(int(self.cell_size * 0.6))
        return self._emoji_font
    
    def _load_font(self, size: int):
        """加载字体，优先使用系统中支持中文的字体"""
        from PIL import ImageFont
        import os
        
        # 尝试加载的字体列表（按优先级）
        font_candidates = [
            # Windows
            "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",    # 黑体
            "C:/Windows/Fonts/simsun.ttc",    # 宋体
            # Linux
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            # macOS
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
        ]
        
        for font_path in font_candidates:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception:
                    continue
        
        # 回退到默认字体
        try:
            return ImageFont.load_default()
        except Exception:
            return None
    
    def _load_emoji_font(self, size: int):
        """加载 Emoji 字体（NotoColorEmoji）"""
        from PIL import ImageFont
        import os
        
        # 获取插件目录
        plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Emoji 字体候选列表
        emoji_font_candidates = [
            # 插件自带字体（推荐）
            os.path.join(plugin_dir, "assets", "fonts", "NotoColorEmoji.ttf"),
            # Windows
            "C:/Windows/Fonts/seguiemj.ttf",      # Segoe UI Emoji
            # Linux
            "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
            "/usr/share/fonts/noto-emoji/NotoColorEmoji.ttf",
            # macOS (Apple Color Emoji 不支持 PIL，跳过)
        ]
        
        for font_path in emoji_font_candidates:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception:
                    continue
        
        # 回退到普通字体（Emoji 可能显示为方块）
        return self._get_font()
    
    def _get_map_hash(self, exp_map: 'ExplorationMap') -> str:
        """计算地图状态的哈希值，用于缓存"""
        import hashlib
        
        state_str = f"{exp_map.region_id}:{exp_map.width}:{exp_map.height}:"
        state_str += f"{exp_map.player_x}:{exp_map.player_y}:{exp_map.weather}:"
        state_str += f"{exp_map.explored_count}:"
        
        for y in range(exp_map.height):
            for x in range(exp_map.width):
                cell = exp_map.get_cell(x, y)
                if cell:
                    state_str += f"{cell.cell_type.value}{int(cell.is_explored)}{int(cell.is_visible)}"
                else:
                    state_str += "X"
        
        return hashlib.md5(state_str.encode()).hexdigest()[:16]
    
    async def render_map_async(self, 
                                exp_map: 'ExplorationMap',
                                region_name: str = "",
                                weather_info: Optional[Dict] = None,
                                show_hidden: bool = False,
                                action_prefix: str = ">") -> bytes:
        """
        异步渲染地图为图片
        
        Args:
            exp_map: 探索地图对象
            region_name: 区域名称
            weather_info: 天气信息 {"icon": "☀️", "name": "晴天"}
            show_hidden: 是否显示隐藏格子（调试用）
            
        Returns:
            PNG 图片的字节数据
        """
        import asyncio
        
        # 检查缓存
        cache_key = None
        if self.cache_enabled:
            cache_key = self._get_map_hash(exp_map)
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        # 在线程池中执行渲染（避免阻塞事件循环）
        image_bytes = await asyncio.to_thread(
            self._render_map_sync,
            exp_map,
            region_name,
            weather_info,
            show_hidden,
            action_prefix
        )
        
        # 存入缓存
        if self.cache_enabled and cache_key:
            self._add_to_cache(cache_key, image_bytes)
        
        return image_bytes
    
    def _add_to_cache(self, key: str, data: bytes):
        """添加到缓存，自动清理旧缓存"""
        if len(self._cache) >= self._cache_max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = data
    
    def _render_map_sync(self,
                          exp_map: 'ExplorationMap',
                          region_name: str,
                          weather_info: Optional[Dict],
                          show_hidden: bool,
                          action_prefix: str = ">") -> bytes:
        from PIL import Image, ImageDraw
        import io
        
        # 计算图片尺寸
        header_height = 60
        legend_height = 80
        status_height = 55
        col_header_height = 25
        row_label_width = 40
        
        map_width = exp_map.width * self.cell_size
        map_height = exp_map.height * self.cell_size
        
        total_width = row_label_width + map_width + self.padding * 2
        total_height = header_height + col_header_height + map_height + legend_height + status_height + self.padding * 2
        
        # 创建图片
        img = Image.new('RGB', (total_width, total_height), self.COLORS['background'])
        draw = ImageDraw.Draw(img)
        font = self._get_font()
        emoji_font = self._load_emoji_font(self.font_size)  # 加载 Emoji 字体

        
        y_offset = self.padding
        
        # 1. 绘制标题区域
        y_offset = self._draw_header(draw, font, emoji_font, total_width, y_offset, 
                                      region_name, weather_info, header_height)

        
        # 2. 绘制列标题 (A, B, C, ...)
        y_offset = self._draw_column_headers(draw, font, exp_map, y_offset, row_label_width)
        
        # 3. 绘制地图主体
        y_offset = self._draw_map_grid(draw, font, emoji_font, exp_map, y_offset, 
                                        row_label_width, show_hidden)
        
        # 4. 绘制图例
        y_offset = self._draw_legend(draw, font, emoji_font, total_width, y_offset)
        
        # 5. 绘制状态信息
        self._draw_status(draw, font, exp_map, total_width, y_offset, action_prefix)

        
        # 转换为字节
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        return buffer.getvalue()
    
    def _draw_header(self, draw, font, emoji_font, width: int, y: int, region_name: str,
                      weather_info: Optional[Dict], height: int) -> int:
        """绘制标题区域"""
        # 背景
        draw.rectangle(
            [(self.padding, y), (width - self.padding, y + height)],
            fill=self.COLORS['header_bg']
        )
        
        # 区域名称
        title = f"[{region_name}]" if region_name else "[探索中]"
        if font:
            draw.text((self.padding + 15, y + 12), title,
                      fill=self.COLORS['text'], font=font)
        
        # 天气信息（天气图标使用 emoji_font）
        if weather_info:
            weather_icon = weather_info.get('icon', '')
            weather_name = weather_info.get('name', '')
            
            # 先绘制天气图标（使用 emoji_font）
            icon_x = self.padding + 15
            if weather_icon and emoji_font:
                draw.text((icon_x, y + 35), weather_icon,
                          fill=self.COLORS['text_dim'], font=emoji_font)
                icon_x += 25  # 图标后留出空间
            
            # 再绘制天气名称（使用普通字体）
            if weather_name and font:
                draw.text((icon_x, y + 35), weather_name,
                          fill=self.COLORS['text_dim'], font=font)
        
        return y + height + 5

    
    def _draw_column_headers(self, draw, font, exp_map: 'ExplorationMap', 
                              y: int, row_label_width: int) -> int:
        """绘制列标题"""
        x_start = self.padding + row_label_width
        
        for x in range(exp_map.width):
            col_label = chr(ord('A') + x)
            text_x = x_start + x * self.cell_size + self.cell_size // 2 - 5
            if font:
                draw.text((text_x, y), col_label, fill=self.COLORS['text_dim'], font=font)
        
        return y + 25
    
    def _draw_map_grid(self, draw, font, emoji_font, exp_map: 'ExplorationMap',
                        y_start: int, row_label_width: int, show_hidden: bool) -> int:
        """绘制地图网格"""
        x_start = self.padding + row_label_width
        
        for y in range(exp_map.height):
            # 绘制行号
            row_label = str(y + 1)
            if font:
                draw.text((self.padding + 12, y_start + y * self.cell_size + self.cell_size // 2 - 8),
                          row_label, fill=self.COLORS['text_dim'], font=font)
            
            for x in range(exp_map.width):
                cell_x = x_start + x * self.cell_size
                cell_y = y_start + y * self.cell_size
                
                cell = exp_map.get_cell(x, y)
                is_player = (x == exp_map.player_x and y == exp_map.player_y)
                
                # 绘制格子（传入 emoji_font）
                self._draw_cell(draw, font, emoji_font, cell_x, cell_y, cell, is_player, show_hidden)

        
        # 绘制网格线
        for i in range(exp_map.width + 1):
            line_x = x_start + i * self.cell_size
            draw.line([(line_x, y_start), (line_x, y_start + exp_map.height * self.cell_size)],
                      fill=self.COLORS['grid_line'], width=1)
        
        for i in range(exp_map.height + 1):
            line_y = y_start + i * self.cell_size
            draw.line([(x_start, line_y), (x_start + exp_map.width * self.cell_size, line_y)],
                      fill=self.COLORS['grid_line'], width=1)
        
        return y_start + exp_map.height * self.cell_size + 10
    
    def _draw_cell(self, draw, font, emoji_font, x: int, y: int, cell: Optional['MapCell'],
                    is_player: bool, show_hidden: bool):
        """绘制单个格子"""
        # 确定格子颜色和图标
        if is_player:
            bg_color = self.COLORS['cell_player']
            icon = self.ICONS['player']
        elif cell is None:
            bg_color = self.COLORS['cell_empty']
            icon = self.ICONS['empty']
        elif not (show_hidden or cell.is_explored or cell.is_visible):
            bg_color = self.COLORS['cell_unknown']
            icon = self.ICONS['unknown']
        else:
            # 根据格子类型确定颜色和图标
            type_mapping = {
                CellType.EMPTY: ('cell_empty', 'empty'),
                CellType.MONSTER: ('cell_monster', 'monster'),
                CellType.RARE_MONSTER: ('cell_rare', 'rare'),
                CellType.TREASURE: ('cell_treasure', 'treasure'),
                CellType.BOSS: ('cell_boss', 'boss'),
                CellType.EXIT: ('cell_exit', 'exit'),
                CellType.EVENT: ('cell_event', 'event'),
            }
            color_key, icon_key = type_mapping.get(cell.cell_type, ('cell_empty', 'empty'))
            bg_color = self.COLORS[color_key]
            icon = self.ICONS[icon_key]
        
        # 绘制背景
        margin = 2
        draw.rectangle(
            [(x + margin, y + margin), (x + self.cell_size - margin, y + self.cell_size - margin)],
            fill=bg_color
        )
        
        # 选择字体：Emoji 图标用 emoji_font，普通字符用 font
        is_emoji = icon not in ('·', '.', ' ')  # 空地用普通字符
        use_font = emoji_font if (is_emoji and emoji_font) else font
        
        # 绘制图标（居中）
        if use_font:
            try:
                bbox = draw.textbbox((0, 0), icon, font=use_font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            except Exception:
                text_width = self.cell_size // 2
                text_height = self.cell_size // 2
            
            text_x = x + (self.cell_size - text_width) // 2
            text_y = y + (self.cell_size - text_height) // 2 - 2
            
            # Emoji 不需要设置颜色（彩色 Emoji 自带颜色）
            if is_emoji and emoji_font:
                draw.text((text_x, text_y), icon, font=use_font, embedded_color=True)
            else:
                icon_color = (30, 30, 30) if is_player else self.COLORS['text']
                draw.text((text_x, text_y), icon, fill=icon_color, font=use_font)
    
    def _draw_legend(self, draw, font, emoji_font, width: int, y: int) -> int:
        """绘制图例"""
        # 使用 Emoji 符号和对应的颜色
        legend_items = [
            (self.ICONS['player'], '你', self.COLORS['cell_player']),
            (self.ICONS['monster'], '精灵', self.COLORS['cell_monster']),
            (self.ICONS['rare'], '稀有', self.COLORS['cell_rare']),
            (self.ICONS['treasure'], '宝箱', self.COLORS['cell_treasure']),
            (self.ICONS['boss'], 'BOSS', self.COLORS['cell_boss']),
            (self.ICONS['exit'], '出口', self.COLORS['cell_exit']),
            (self.ICONS['event'], '事件', self.COLORS['cell_event']),
            (self.ICONS['unknown'], '未知', self.COLORS['cell_unknown']),
        ]
        
        items_per_row = 4
        item_width = (width - self.padding * 2) // items_per_row
        
        for i, (icon, label, color) in enumerate(legend_items):
            row = i // items_per_row
            col = i % items_per_row
            
            item_x = self.padding + col * item_width + 10
            item_y = y + row * 30
            
            # 使用 emoji_font 绘制图标
            use_font = emoji_font if emoji_font else font
            if use_font:
                # 绘制 Emoji 图标（彩色）
                if emoji_font:
                    draw.text((item_x, item_y), icon, font=emoji_font, embedded_color=True)
                else:
                    draw.text((item_x, item_y), icon, fill=color, font=font)
            # 绘制标签（使用普通字体）
            if font:
                draw.text((item_x + 25, item_y), label, fill=self.COLORS['text_dim'], font=font)
        return y + 70

    
    def _draw_status(self, draw, font, exp_map: 'ExplorationMap', width: int, y: int, action_prefix: str = ">"):
        """绘制状态信息"""
        total_cells = exp_map.get_total_cells()
        explored_percent = exp_map.explored_count / total_cells * 100 if total_cells > 0 else 0
        
        if font:
            # 探索进度
            progress_text = f"探索: {exp_map.explored_count}/{total_cells} ({explored_percent:.0f}%)"
            draw.text((self.padding + 10, y), progress_text, 
                      fill=self.COLORS['text'], font=font)
            
            # 当前位置
            pos_text = f"位置: {chr(ord('A') + exp_map.player_x)}{exp_map.player_y + 1}"
            draw.text((width // 2, y), pos_text,
                      fill=self.COLORS['text'], font=font)
            
            # 操作提示 - 使用动态前缀并用双引号包裹
            hint_text = f"发送 \"{action_prefix}坐标\" 移动，\"{action_prefix}离开\" 退出"
            draw.text((self.padding + 10, y + 28), hint_text,
                      fill=self.COLORS['text_dim'], font=font)
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()


# 全局渲染器实例（单例）
_map_renderer_instance: Optional['MapImageRenderer'] = None


def get_map_renderer() -> 'MapImageRenderer':
    """获取全局地图渲染器实例"""
    global _map_renderer_instance
    if _map_renderer_instance is None:
        _map_renderer_instance = MapImageRenderer()
    return _map_renderer_instance


