"""
战斗系统模块

重构后的战斗系统，将原本1500+行的单文件拆分为多个职责清晰的模块：
- constants.py: 战斗常量（消灭魔法数字）
- models.py: 数据类定义
- damage_calculator.py: 伤害计算器
- effect_processor.py: 技能效果处理器
- status_handler.py: 状态效果处理
- weather_system.py: 天气系统
- ai_controller.py: AI逻辑
- battle_renderer.py: UI渲染
- battle_system.py: 主战斗系统（协调者）
"""

# 导出主要接口
from .models import (
    BattleType,
    ActionType,
    BattleAction,
    BattleResult,
    TurnResult,
    BattleState,
)

from .battle_system import BattleSystem

__all__ = [
    # 枚举类型
    "BattleType",
    "ActionType",
    # 数据类
    "BattleAction",
    "BattleResult", 
    "TurnResult",
    "BattleState",
    # 主系统
    "BattleSystem",
]
