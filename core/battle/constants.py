"""
战斗系统常量定义

消灭所有魔法数字！所有数值在这里集中管理，方便后续调整平衡性。
"""

from typing import Dict


# ==================== 能力等级修正 ====================

# 能力等级修正表 (-6 ~ +6)
# 用于攻击、防御、特攻、特防、速度
STAT_STAGE_MULTIPLIERS: Dict[int, float] = {
    -6: 2/8,   # 0.25
    -5: 2/7,   # 0.286
    -4: 2/6,   # 0.333
    -3: 2/5,   # 0.4
    -2: 2/4,   # 0.5
    -1: 2/3,   # 0.667
    0: 1.0,    # 基础值
    1: 3/2,    # 1.5
    2: 4/2,    # 2.0
    3: 5/2,    # 2.5
    4: 6/2,    # 3.0
    5: 7/2,    # 3.5
    6: 8/2,    # 4.0
}

# 命中/闪避等级修正表 (-6 ~ +6)
ACCURACY_STAGE_MULTIPLIERS: Dict[int, float] = {
    -6: 3/9,   # 0.333
    -5: 3/8,   # 0.375
    -4: 3/7,   # 0.429
    -3: 3/6,   # 0.5
    -2: 3/5,   # 0.6
    -1: 3/4,   # 0.75
    0: 1.0,    # 基础值
    1: 4/3,    # 1.333
    2: 5/3,    # 1.667
    3: 6/3,    # 2.0
    4: 7/3,    # 2.333
    5: 8/3,    # 2.667
    6: 9/3,    # 3.0
}

# 能力等级范围
STAT_STAGE_MIN = -6
STAT_STAGE_MAX = 6


# ==================== 暴击相关 ====================

# 基础暴击率 (6.25%)
BASE_CRITICAL_RATE = 0.0625

# 高暴击技能的暴击率
HIGH_CRITICAL_RATE = 0.25

# 暴击率上限
MAX_CRITICAL_RATE = 1.0


# ==================== 状态效果 ====================

# 灼伤降低物理攻击的比例
BURN_ATTACK_REDUCTION = 0.5

# 麻痹降低速度的比例
PARALYZE_SPEED_REDUCTION = 0.5

# 麻痹导致无法行动的概率
PARALYZE_SKIP_CHANCE = 0.25

# 睡眠苏醒概率
SLEEP_WAKE_CHANCE = 0.33

# 冰冻解除概率
FREEZE_THAW_CHANCE = 0.20

# 烧伤每回合伤害 (最大HP的1/16)
BURN_DAMAGE_FRACTION = 16

# 中毒每回合伤害 (最大HP的1/8)
POISON_DAMAGE_FRACTION = 8


# ==================== 逃跑相关 ====================

# 逃跑基础概率常数
FLEE_BASE_CONSTANT = 30

# 逃跑速度系数
FLEE_SPEED_MULTIPLIER = 32

# 逃跑最小概率
FLEE_MIN_CHANCE = 0.10

# 逃跑最大概率
FLEE_MAX_CHANCE = 0.95


# ==================== 战斗奖励 ====================

# 基础金币奖励
BASE_COIN_REWARD = 50

# 每级敌人额外金币
COIN_PER_LEVEL = 10

# BOSS金币倍率
BOSS_COIN_MULTIPLIER = 5

# 默认基础经验
DEFAULT_BASE_EXP = 100


# ==================== 默认属性值 ====================

# 默认速度值
DEFAULT_SPEED = 50

# 默认HP
DEFAULT_HP = 100

# 默认等级
DEFAULT_LEVEL = 1

# 最小属性值（确保不为0）
MIN_STAT_VALUE = 1


# ==================== 属性名称映射 ====================

# 属性中文名
STAT_NAMES_CN: Dict[str, str] = {
    "attack": "攻击",
    "defense": "防御",
    "sp_attack": "特攻",
    "sp_defense": "特防",
    "speed": "速度",
    "accuracy": "命中",
    "evasion": "闪避",
    "critical": "暴击",
}

# 所有可修改的属性类型
MODIFIABLE_STATS = [
    "attack", "defense", "sp_attack", "sp_defense",
    "speed", "accuracy", "evasion", "critical"
]


# ==================== 状态效果映射 ====================

# 状态中文名
STATUS_NAMES_CN: Dict[str, str] = {
    "burn": "烧伤",
    "paralyze": "麻痹",
    "poison": "中毒",
    "sleep": "睡眠",
    "freeze": "冰冻",
}

# 状态图标
STATUS_ICONS: Dict[str, str] = {
    "burn": "🔥",
    "paralyze": "⚡",
    "poison": "☠️",
    "sleep": "💤",
    "freeze": "❄️",
}

# 属性免疫状态的映射 (某属性免疫某状态)
STATUS_IMMUNITY: Dict[str, str] = {
    "burn": "fire",       # 火属性免疫烧伤
    "freeze": "ice",      # 冰属性免疫冰冻
    "paralyze": "electric",  # 电属性免疫麻痹
    "poison": "poison",   # 毒属性免疫中毒
}


# ==================== UI渲染相关 ====================

# HP条长度
HP_BAR_LENGTH = 10

# HP条字符
HP_BAR_FULL = "█"
HP_BAR_MEDIUM = "▓"
HP_BAR_LOW = "░"
HP_BAR_EMPTY = "·"

# HP阈值
HP_THRESHOLD_HIGH = 0.5
HP_THRESHOLD_LOW = 0.2

# 分隔线字符
SEPARATOR_DOUBLE = "═"
SEPARATOR_SINGLE = "─"
SEPARATOR_LENGTH = 24


# ==================== 默认效果持续时间 ====================

# 回复效果默认持续回合
DEFAULT_REGEN_DURATION = 3

# 护盾默认持续回合
DEFAULT_SHIELD_DURATION = 3

# 混乱默认持续回合
DEFAULT_CONFUSE_DURATION = 3

# Buff/Debuff默认持续回合
DEFAULT_BUFF_DURATION = 3
