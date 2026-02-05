"""
精灵实例类
"""

import random
import uuid
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field, asdict

from .formulas import GameFormulas

if TYPE_CHECKING:
    from .config_manager import ConfigManager


@dataclass
class MonsterInstance:
    """
    精灵实例 - 玩家拥有的具体精灵
    """

    # 唯一标识
    instance_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # 模板信息
    template_id: str = ""
    name: str = ""
    nickname: str = ""  # 玩家起的昵称
    types: List[str] = field(default_factory=list)
    rarity: int = 3
    description: str = ""

    # 等级与经验
    level: int = 1
    exp: int = 0

    # 性格 (性格ID，从配置读取)
    nature_id: str = "hardy"

    # 个体值 (IV) - 出生时随机，不可变
    ivs: Dict[str, int] = field(default_factory=dict)

    # 努力值 (EV) - 通过战斗积累
    evs: Dict[str, int] = field(default_factory=lambda: {
        "hp": 0, "attack": 0, "defense": 0,
        "sp_attack": 0, "sp_defense": 0, "speed": 0
    })

    # 基础属性 (来自模板)
    base_stats: Dict[str, int] = field(default_factory=dict)

    # 成长率 (来自模板)
    growth_rates: Dict[str, float] = field(default_factory=dict)

    # 计算后的实际属性
    stats: Dict[str, int] = field(default_factory=dict)

    # HP
    current_hp: int = 0
    max_hp: int = 0

    # 技能 (技能ID列表，最多4个)
    skills: List[str] = field(default_factory=list)

    # 特性
    ability_id: Optional[str] = None

    # 进化信息
    evolves_to: Optional[str] = None
    evolution_level: Optional[int] = None
    evolution_item: Optional[str] = None
    evolves_from: Optional[str] = None

    # 状态
    status: Optional[str] = None  # burn, paralyze, poison, sleep, freeze
    status_turns: int = 0

    # 好感度
    friendship: int = 50

    # 来源信息
    caught_at: str = ""
    caught_time: str = ""
    original_trainer_id: str = ""
    original_trainer_name: str = ""

    # 统计
    battles_won: int = 0
    battles_total: int = 0

    @classmethod
    def from_template(cls,
                      template: Dict,
                      level: int = 5,
                      config_manager: "ConfigManager" = None,
                      nature_id: str = None,
                      ivs: Dict[str, int] = None,
                      caught_region: str = "",
                      trainer_id: str = "",
                      trainer_name: str = "") -> "MonsterInstance":
        """
        从模板创建精灵实例
        """
        # 随机性格（支持权重）
        if nature_id is None:
            if config_manager:
                natures_config = config_manager.natures
                if natures_config:
                    # 构建权重列表，按权重随机选择
                    nature_ids = list(natures_config.keys())
                    weights = [natures_config[n].get("weight", 10) for n in nature_ids]
                    nature_id = random.choices(nature_ids, weights=weights, k=1)[0]
                else:
                    nature_id = "hardy"
            else:
                nature_id = "hardy"

        # 随机个体值 (稀有度越高，保底满个体数越多)
        if ivs is None:
            rarity = template.get("rarity", 3)
            guaranteed_max = max(0, rarity - 2)
            ivs = GameFormulas.generate_ivs(guaranteed_max=guaranteed_max)

        instance = cls(
            template_id=template["id"],
            name=template["name"],
            types=template.get("types", ["normal"]),
            rarity=template.get("rarity", 3),
            description=template.get("description", ""),
            level=level,
            nature_id=nature_id,
            ivs=ivs,
            base_stats=template.get("base_stats", {
                "hp": 50, "attack": 50, "defense": 50,
                "sp_attack": 50, "sp_defense": 50, "speed": 50
            }),
            growth_rates=template.get("growth_rates", {
                "hp": 2.0, "attack": 2.0, "defense": 2.0,
                "sp_attack": 2.0, "sp_defense": 2.0, "speed": 2.0
            }),
            skills=template.get("skills", [])[:4],
            ability_id=template.get("ability"),
            caught_at=caught_region,
            caught_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            original_trainer_id=trainer_id,
            original_trainer_name=trainer_name,
        )

        # 处理进化信息
        evolution = template.get("evolution")
        if evolution:
            instance.evolves_to = evolution.get("evolves_to")
            instance.evolution_level = evolution.get("level_required")
            instance.evolution_item = evolution.get("item_required")

        instance.evolves_from = template.get("evolves_from")

        # 计算属性
        instance.recalculate_stats(config_manager)
        instance.current_hp = instance.max_hp

        return instance

    def recalculate_stats(self, config_manager: "ConfigManager" = None):
        """重新计算属性值"""
        nature_config = None
        if config_manager:
            nature_config = config_manager.get_item("natures", self.nature_id)

        self.stats = GameFormulas.calculate_all_stats(
            base_stats=self.base_stats,
            ivs=self.ivs,
            evs=self.evs,
            level=self.level,
            growth_rates=self.growth_rates,
            nature_config=nature_config
        )

        old_max_hp = self.max_hp
        self.max_hp = self.stats.get("hp", 100)

        # 保持HP比例
        if old_max_hp > 0:
            hp_ratio = self.current_hp / old_max_hp
            self.current_hp = int(self.max_hp * hp_ratio)
        else:
            self.current_hp = self.max_hp

        self.current_hp = max(0, min(self.current_hp, self.max_hp))

    def add_exp(self, amount: int, config_manager: "ConfigManager" = None) -> Dict:
        """
        增加经验值

        Returns:
            {"leveled_up": bool, "levels_gained": int, "old_level": int, "new_level": int, "new_skills": list, "can_evolve": bool}
        """
        old_level = self.level  # 记录升级前的等级
        
        result = {
            "leveled_up": False,
            "levels_gained": 0,
            "old_level": old_level,
            "new_level": old_level,
            "new_skills": [],
            "can_evolve": False
        }

        self.exp += amount

        while self.level < 100:
            exp_needed = GameFormulas.calculate_exp_required(self.level)
            if self.exp >= exp_needed:
                self.exp -= exp_needed
                self.level += 1
                result["leveled_up"] = True
                result["levels_gained"] += 1

                # 检查新技能
                if config_manager:
                    monster_template = config_manager.get_item("monsters", self.template_id)
                    if monster_template:
                        learnable = monster_template.get("learnable_skills", {})
                        level_str = str(self.level)
                        if level_str in learnable:
                            new_skill = learnable[level_str]
                            if new_skill not in self.skills:
                                result["new_skills"].append(new_skill)
                                if len(self.skills) < 4:
                                    self.skills.append(new_skill)
            else:
                break

        # 更新 new_level 为升级后的等级
        result["new_level"] = self.level

        if result["leveled_up"]:
            self.recalculate_stats(config_manager)
            if self.evolves_to and self.evolution_level:
                if self.level >= self.evolution_level:
                    result["can_evolve"] = True

        return result


    def add_evs(self, ev_gains: Dict[str, int], config_manager: "ConfigManager" = None):
        """增加努力值"""
        EV_MAX = 252
        EV_TOTAL_MAX = 510

        total_evs = sum(self.evs.values())

        for stat, gain in ev_gains.items():
            if stat in self.evs:
                can_add = min(
                    gain,
                    EV_MAX - self.evs[stat],
                    EV_TOTAL_MAX - total_evs
                )
                if can_add > 0:
                    self.evs[stat] += can_add
                    total_evs += can_add

        self.recalculate_stats(config_manager)

    def heal(self, amount: int = -1) -> int:
        """
        治疗精灵

        Args:
            amount: 治疗量，-1表示完全恢复

        Returns:
            实际恢复量
        """
        if amount < 0:
            healed = self.max_hp - self.current_hp
            self.current_hp = self.max_hp
        else:
            healed = min(amount, self.max_hp - self.current_hp)
            self.current_hp += healed

        self.status = None
        self.status_turns = 0
        return healed

    def take_damage(self, damage: int) -> bool:
        """
        受到伤害

        Returns:
            是否倒下
        """
        self.current_hp = max(0, self.current_hp - damage)
        return self.current_hp <= 0

    def can_evolve(self) -> bool:
        """检查是否可以进化"""
        if not self.evolves_to:
            return False

        # 等级进化
        if self.evolution_level and self.level >= self.evolution_level:
            return True

        # 道具进化需要额外检查（由外部调用时传入道具）
        return False

    def evolve(self, config_manager: "ConfigManager") -> Optional["MonsterInstance"]:
        """
        执行进化

        Returns:
            进化后的新实例，失败返回None
        """
        if not self.can_evolve() or not config_manager:
            return None

        new_template = config_manager.get_item("monsters", self.evolves_to)
        if not new_template:
            return None

        # 保留原有数据
        old_nickname = self.nickname
        old_ivs = self.ivs.copy()
        old_evs = self.evs.copy()
        old_friendship = self.friendship
        old_caught_at = self.caught_at
        old_caught_time = self.caught_time
        old_trainer_id = self.original_trainer_id
        old_trainer_name = self.original_trainer_name
        old_battles_won = self.battles_won
        old_battles_total = self.battles_total

        # 更新为新模板数据
        self.template_id = new_template["id"]
        self.name = new_template["name"]
        self.types = new_template.get("types", self.types)
        self.rarity = new_template.get("rarity", self.rarity)
        self.description = new_template.get("description", "")
        self.base_stats = new_template.get("base_stats", self.base_stats)
        self.growth_rates = new_template.get("growth_rates", self.growth_rates)
        self.ability_id = new_template.get("ability", self.ability_id)

        # 保留昵称或使用新名字
        if not old_nickname:
            self.nickname = ""

        # 学习进化后的新技能
        new_skills = new_template.get("skills", [])
        for skill in new_skills:
            if skill not in self.skills and len(self.skills) < 4:
                self.skills.append(skill)

        # 更新进化链
        self.evolves_from = self.template_id
        new_evolution = new_template.get("evolution")
        if new_evolution:
            self.evolves_to = new_evolution.get("evolves_to")
            self.evolution_level = new_evolution.get("level_required")
            self.evolution_item = new_evolution.get("item_required")
        else:
            self.evolves_to = None
            self.evolution_level = None
            self.evolution_item = None

        # 重新计算属性
        self.recalculate_stats(config_manager)
        self.current_hp = self.max_hp  # 进化后HP回满

        return self

    def learn_skill(self, skill_id: str, slot: int = None) -> bool:
        """
        学习技能

        Args:
            skill_id: 技能ID
            slot: 替换的技能槽位 (0-3)，None则自动添加

        Returns:
            是否成功
        """
        if skill_id in self.skills:
            return False  # 已学会

        if slot is not None:
            if 0 <= slot < len(self.skills):
                self.skills[slot] = skill_id
                return True
            elif slot == len(self.skills) and len(self.skills) < 4:
                self.skills.append(skill_id)
                return True
        else:
            if len(self.skills) < 4:
                self.skills.append(skill_id)
                return True

        return False

    def forget_skill(self, skill_id: str) -> bool:
        """遗忘技能"""
        if skill_id in self.skills and len(self.skills) > 1:
            self.skills.remove(skill_id)
            return True
        return False

    def set_nickname(self, nickname: str):
        """设置昵称"""
        self.nickname = nickname[:20]  # 限制长度

    def get_display_name(self) -> str:
        """获取显示名称（优先昵称）"""
        return self.nickname if self.nickname else self.name

    def get_hp_bar(self, length: int = 10) -> str:
        """获取HP条显示"""
        if self.max_hp <= 0:
            return "?" * length

        filled = int((self.current_hp / self.max_hp) * length)
        empty = length - filled

        # 根据HP比例选择颜色符号
        hp_ratio = self.current_hp / self.max_hp
        if hp_ratio > 0.5:
            char = "█"
        elif hp_ratio > 0.2:
            char = "▓"
        else:
            char = "░"

        return char * filled + "·" * empty

    def get_status_icon(self) -> str:
        """获取状态图标"""
        status_icons = {
            "burn": "🔥",
            "paralyze": "⚡",
            "poison": "☠️",
            "sleep": "💤",
            "freeze": "❄️",
        }
        return status_icons.get(self.status, "")

    def get_rarity_stars(self) -> str:
        """获取稀有度星星"""
        return "⭐" * self.rarity

    def get_type_icons(self, type_config: Dict = None) -> str:
        """获取属性图标"""
        if type_config:
            icons = []
            for t in self.types:
                type_data = type_config.get(t, {})
                icons.append(type_data.get("icon", t))
            return " ".join(icons)
        return "/".join(self.types)

    def get_iv_total(self) -> int:
        """获取个体值总和"""
        return sum(self.ivs.values())

    def get_ev_total(self) -> int:
        """获取努力值总和"""
        return sum(self.evs.values())

    def is_fainted(self) -> bool:
        """是否已倒下"""
        return self.current_hp <= 0

    def apply_status(self, status: str, turns: int = 0) -> bool:
        """
        施加状态

        Args:
            status: 状态类型
            turns: 持续回合数，0表示永久直到治愈

        Returns:
            是否成功施加
        """
        # 已有状态不能被覆盖
        if self.status is not None:
            return False

        # 某些属性免疫某些状态
        type_immunities = {
            "fire": ["burn", "freeze"],
            "electric": ["paralyze"],
            "ice": ["freeze"],
            "poison": ["poison"],
        }

        for t in self.types:
            if status in type_immunities.get(t, []):
                return False

        self.status = status
        self.status_turns = turns
        return True

    def tick_status(self) -> Dict:
        """
        处理状态回合效果

        Returns:
            {"damage": int, "skip_turn": bool, "cured": bool}
        """
        result = {"damage": 0, "skip_turn": False, "cured": False}

        if not self.status:
            return result

        # 状态效果
        if self.status == "burn":
            result["damage"] = max(1, self.max_hp // 16)
        elif self.status == "poison":
            result["damage"] = max(1, self.max_hp // 8)
        elif self.status == "paralyze":
            result["skip_turn"] = random.random() < 0.25  # 25%无法行动
        elif self.status == "sleep":
            result["skip_turn"] = True
            # 每回合有33%几率醒来
            if random.random() < 0.33:
                result["cured"] = True
        elif self.status == "freeze":
            result["skip_turn"] = True
            # 每回合有20%几率解冻
            if random.random() < 0.20:
                result["cured"] = True

        # 应用伤害
        if result["damage"] > 0:
            self.take_damage(result["damage"])

        # 处理回合数
        if self.status_turns > 0:
            self.status_turns -= 1
            if self.status_turns <= 0:
                result["cured"] = True

        # 治愈状态
        if result["cured"]:
            self.status = None
            self.status_turns = 0

        return result

    def to_dict(self) -> Dict:
        """转换为字典（用于存储）"""
        return {
            "instance_id": self.instance_id,
            "template_id": self.template_id,
            "name": self.name,
            "nickname": self.nickname,
            "types": self.types,
            "rarity": self.rarity,
            "description": self.description,
            "level": self.level,
            "exp": self.exp,
            "nature_id": self.nature_id,
            "ivs": self.ivs,
            "evs": self.evs,
            "base_stats": self.base_stats,
            "growth_rates": self.growth_rates,
            "stats": self.stats,
            "current_hp": self.current_hp,
            "max_hp": self.max_hp,
            "skills": self.skills,
            "ability_id": self.ability_id,
            "evolves_to": self.evolves_to,
            "evolution_level": self.evolution_level,
            "evolution_item": self.evolution_item,
            "evolves_from": self.evolves_from,
            "status": self.status,
            "status_turns": self.status_turns,
            "friendship": self.friendship,
            "caught_at": self.caught_at,
            "caught_time": self.caught_time,
            "original_trainer_id": self.original_trainer_id,
            "original_trainer_name": self.original_trainer_name,
            "battles_won": self.battles_won,
            "battles_total": self.battles_total,
        }

    @classmethod
    def from_dict(cls, data: Dict, config_manager: "ConfigManager" = None) -> "MonsterInstance":
        """从字典恢复"""
        instance = cls()

        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        # 确保属性计算正确
        if config_manager:
            instance.recalculate_stats(config_manager)

        return instance

    def get_summary(self, config_manager: "ConfigManager" = None) -> str:
        """获取精灵摘要信息"""
        type_icons = self.get_type_icons(config_manager.types if config_manager else None)
        nature_name = self.nature_id
        if config_manager:
            nature_data = config_manager.get_item("natures", self.nature_id)
            if nature_data:
                nature_name = nature_data.get("name", self.nature_id)

        status_str = f" {self.get_status_icon()}" if self.status else ""

        return (
            f"{self.get_display_name()} Lv.{self.level} {self.get_rarity_stars()}\n"
            f"属性: {type_icons}{status_str}\n"
            f"HP: {self.get_hp_bar()} {self.current_hp}/{self.max_hp}\n"
            f"性格: {nature_name}"
        )

    def get_detail(self, config_manager: "ConfigManager" = None) -> str:
        """获取精灵详细信息"""
        type_icons = self.get_type_icons(config_manager.types if config_manager else None)

        # 性格
        nature_name = self.nature_id
        nature_desc = ""
        if config_manager:
            nature_data = config_manager.get_item("natures", self.nature_id)
            if nature_data:
                nature_name = nature_data.get("name", self.nature_id)
                nature_desc = nature_data.get("description", "")

        # 技能列表
        skills_str = ""
        for i, skill_id in enumerate(self.skills, 1):
            skill_name = skill_id
            skill_type = ""
            skill_power = ""
            if config_manager:
                skill_data = config_manager.get_item("skills", skill_id)
                if skill_data:
                    skill_name = skill_data.get("name", skill_id)
                    skill_type = skill_data.get("type", "")
                    power = skill_data.get("power", 0)
                    skill_power = f"威力:{power}" if power > 0 else "辅助"
            skills_str += f"  {i}. {skill_name} [{skill_type}] {skill_power}\n"

        # 个体值评价
        iv_total, iv_rating = GameFormulas.get_iv_rating(self.ivs)

        # 经验进度
        exp_needed = GameFormulas.calculate_exp_required(self.level)
        exp_progress = f"{self.exp}/{exp_needed}"

        return (
            f"{'═' * 24}\n"
            f"  {self.get_display_name()} Lv.{self.level} {self.get_rarity_stars()}\n"
            f"{'═' * 24}\n"
            f"属性: {type_icons}\n"
            f"HP: {self.get_hp_bar(15)} {self.current_hp}/{self.max_hp}\n"
            f"{'─' * 24}\n"
            f"攻击: {self.stats.get('attack', 0):>3} | 防御: {self.stats.get('defense', 0):>3}\n"
            f"特攻: {self.stats.get('sp_attack', 0):>3} | 特防: {self.stats.get('sp_defense', 0):>3}\n"
            f"速度: {self.stats.get('speed', 0):>3}\n"
            f"{'─' * 24}\n"
            f"性格: {nature_name} ({nature_desc})\n"
            f"个体值: {iv_total}/186 [{iv_rating}]\n"
            f"经验: {exp_progress}\n"
            f"{'─' * 24}\n"
            f"技能:\n{skills_str}"
            f"{'─' * 24}\n"
            f"{self.description}"
        )
