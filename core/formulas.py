"""
游戏核心计算公式
- 属性值计算
- 伤害计算
- 经验计算
- 捕捉概率计算
"""

import random
from typing import Dict, Tuple, Optional


class GameFormulas:
    """游戏计算公式集合"""

    # ==================== 属性值计算 ====================

    @staticmethod
    def calculate_stat(base: int, iv: int, ev: int, level: int,
                       growth_rate: float, nature_mod: float = 1.0,
                       is_hp: bool = False) -> int:
        """
        计算单项属性值

        公式:
        HP = ((基础值×2 + 个体值 + 努力值/4) × 等级/100 + 等级 + 10) × 成长率修正
        其他 = (((基础值×2 + 个体值 + 努力值/4) × 等级/100 + 5) × 性格修正) × 成长率修正

        Args:
            base: 基础属性值
            iv: 个体值 (0-31)
            ev: 努力值 (0-252)
            level: 等级 (1-100)
            growth_rate: 每级成长率
            nature_mod: 性格修正 (0.9 / 1.0 / 1.1)
            is_hp: 是否为HP属性

        Returns:
            计算后的属性值
        """
        # 基础计算
        base_calc = (base * 2 + iv + ev // 4) * level / 100

        if is_hp:
            # HP公式
            result = base_calc + level + 10
        else:
            # 其他属性公式
            result = (base_calc + 5) * nature_mod

        # 应用成长率修正 (成长率影响最终值的加成)
        # 成长率2.0表示每10级额外+10%
        growth_bonus = 1 + (growth_rate - 2.0) * (level / 100) * 0.5
        result = result * max(0.5, growth_bonus)

        return max(1, int(result))

    @staticmethod
    def calculate_all_stats(base_stats: Dict[str, int],
                            ivs: Dict[str, int],
                            evs: Dict[str, int],
                            level: int,
                            growth_rates: Dict[str, float],
                            nature_config: Optional[Dict] = None) -> Dict[str, int]:
        """
        计算所有属性值

        Args:
            base_stats: 基础属性
            ivs: 个体值
            evs: 努力值
            level: 等级
            growth_rates: 成长率
            nature_config: 性格配置 {"buff_stat": "attack", "buff_percent": 10, ...}

        Returns:
            计算后的所有属性值
        """
        result = {}

        for stat_name, base_value in base_stats.items():
            # 计算性格修正
            nature_mod = 1.0
            if nature_config:
                if nature_config.get("buff_stat") == stat_name:
                    nature_mod = 1 + nature_config.get("buff_percent", 10) / 100
                elif nature_config.get("debuff_stat") == stat_name:
                    nature_mod = 1 - nature_config.get("debuff_percent", 10) / 100

            result[stat_name] = GameFormulas.calculate_stat(
                base=base_value,
                iv=ivs.get(stat_name, 0),
                ev=evs.get(stat_name, 0),
                level=level,
                growth_rate=growth_rates.get(stat_name, 2.0),
                nature_mod=nature_mod,
                is_hp=(stat_name == "hp")
            )

        return result

    # ==================== 伤害计算 ====================

    @staticmethod
    def calculate_damage(attacker_level: int,
                         attack_stat: int,
                         defense_stat: int,
                         skill_power: int,
                         type_effectiveness: float = 1.0,
                         weather_mod: float = 1.0,
                         is_critical: bool = False,
                         is_stab: bool = False,
                         random_factor: bool = True) -> Tuple[int, bool]:
        """
        计算技能伤害

        公式: ((2×等级/5+2) × 威力 × 攻击/防御 / 50 + 2) × 修正系数

        Args:
            attacker_level: 攻击方等级
            attack_stat: 攻击方攻击/特攻
            defense_stat: 防御方防御/特防
            skill_power: 技能威力
            type_effectiveness: 属性克制倍率 (0.5 / 1.0 / 2.0)
            weather_mod: 天气修正
            is_critical: 是否暴击
            is_stab: 是否属性一致加成 (Same Type Attack Bonus)
            random_factor: 是否应用随机因子

        Returns:
            (伤害值, 是否暴击)
        """
        if skill_power <= 0:
            return (0, False)

        # 基础伤害
        base_damage = ((2 * attacker_level / 5 + 2) * skill_power * attack_stat / defense_stat) / 50 + 2

        # 暴击判定 (如果没有预先判定)
        critical_hit = is_critical
        critical_mod = 1.5 if critical_hit else 1.0

        # 属性一致加成 (STAB)
        stab_mod = 1.5 if is_stab else 1.0

        # 随机因子 (85%-100%)
        random_mod = random.uniform(0.85, 1.0) if random_factor else 1.0

        # 最终伤害
        final_damage = base_damage * type_effectiveness * weather_mod * critical_mod * stab_mod * random_mod

        return (max(1, int(final_damage)), critical_hit)

    @staticmethod
    def get_type_effectiveness(attack_type: str,
                               defender_types: list,
                               type_chart: Dict) -> float:
        """
        计算属性克制倍率

        Args:
            attack_type: 攻击属性
            defender_types: 防御方属性列表
            type_chart: 属性克制表

        Returns:
            克制倍率 (0.25, 0.5, 1.0, 2.0, 4.0)
        """
        multiplier = 1.0

        attack_config = type_chart.get(attack_type, {})
        strong_against = attack_config.get("strong_against", [])
        weak_against = attack_config.get("weak_against", [])

        for def_type in defender_types:
            if def_type in strong_against:
                multiplier *= 2.0
            elif def_type in weak_against:
                multiplier *= 0.5

        return multiplier

    # ==================== 经验计算 ====================

    @staticmethod
    def calculate_exp_gain(base_exp: int,
                           enemy_level: int,
                           player_level: int,
                           is_wild: bool = True,
                           is_boss: bool = False) -> int:
        """
        计算战斗获得的经验值

        Args:
            base_exp: 精灵基础经验值
            enemy_level: 敌方等级
            player_level: 己方等级
            is_wild: 是否野生
            is_boss: 是否BOSS

        Returns:
            获得的经验值
        """
        # 基础公式
        exp = (base_exp * enemy_level) / 7

        # 等级差修正 (打高级怪经验更多)
        level_diff = enemy_level - player_level
        if level_diff > 0:
            exp *= (1 + level_diff * 0.05)  # 每高1级+5%
        elif level_diff < -10:
            exp *= max(0.1, 1 + level_diff * 0.1)  # 低10级以上大幅减少

        # 野生/训练师修正
        if not is_wild:
            exp *= 1.5

        # BOSS修正
        if is_boss:
            exp *= 3.0

        return max(1, int(exp))

    @staticmethod
    def calculate_exp_required(level: int) -> int:
        """
        计算升级所需经验

        Args:
            level: 当前等级

        Returns:
            升到下一级所需经验
        """
        # 简单公式: level^2 * 10
        return level * level * 10

    # ==================== 捕捉计算 ====================

    @staticmethod
    def calculate_catch_rate(base_catch_rate: int,
                             current_hp: int,
                             max_hp: int,
                             status: Optional[str] = None,
                             ball_bonus: float = 1.0) -> float:
        """
        计算捕捉成功率

        Args:
            base_catch_rate: 基础捕捉率 (0-255)
            current_hp: 当前HP
            max_hp: 最大HP
            status: 异常状态 (sleep, freeze, paralyze, burn, poison)
            ball_bonus: 精灵球加成

        Returns:
            捕捉成功概率 (0.0-1.0)
        """
        # HP修正 (HP越低越容易捕捉)
        hp_ratio = current_hp / max_hp
        hp_modifier = (1 - hp_ratio) * 2 + 1  # 1x ~ 3x

        # 状态修正
        status_modifier = 1.0
        if status in ["sleep", "freeze"]:
            status_modifier = 2.5
        elif status in ["paralyze", "burn", "poison"]:
            status_modifier = 1.5

        # 计算捕捉率
        catch_value = base_catch_rate * hp_modifier * status_modifier * ball_bonus / 255

        return min(1.0, max(0.01, catch_value))  # 最低1%，最高100%

    # ==================== 个体值生成 ====================

    @staticmethod
    def generate_ivs(min_iv: int = 0,
                     max_iv: int = 31,
                     guaranteed_max: int = 0) -> Dict[str, int]:
        """
        生成随机个体值

        Args:
            min_iv: 最小个体值
            max_iv: 最大个体值
            guaranteed_max: 保证满个体的属性数量

        Returns:
            个体值字典
        """
        stats = ["hp", "attack", "defense", "sp_attack", "sp_defense", "speed"]
        ivs = {stat: random.randint(min_iv, max_iv) for stat in stats}

        # 保证一定数量的满个体
        if guaranteed_max > 0:
            max_stats = random.sample(stats, min(guaranteed_max, len(stats)))
            for stat in max_stats:
                ivs[stat] = max_iv

        return ivs

    @staticmethod
    def get_iv_rating(ivs: Dict[str, int]) -> Tuple[int, str]:
        """
        评价个体值

        Returns:
            (总和, 评价文字)
        """
        total = sum(ivs.values())
        max_total = 31 * 6  # 186

        if total >= 180:
            return (total, "完美")
        elif total >= 150:
            return (total, "优秀")
        elif total >= 120:
            return (total, "良好")
        elif total >= 90:
            return (total, "普通")
        else:
            return (total, "较差")
