"""
精灵管理指令处理器
- 背包、详情、队伍、进化、改名等
"""

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..main import MonsterGamePlugin


class MonsterHandlers:
    """精灵管理指令处理器"""

    def __init__(self, plugin: "MonsterGamePlugin"):
        self.plugin = plugin
        self.config = plugin.game_config
        self.pm = plugin.player_manager

    def _get_monster_instance_class(self):
        from ..core import MonsterInstance
        return MonsterInstance

    def _make_hp_bar(self, current: int, maximum: int, length: int = 10) -> str:
        """生成HP条"""
        if maximum <= 0:
            return "?" * length

        ratio = current / maximum
        filled = int(ratio * length)
        empty = length - filled

        if ratio > 0.5:
            char = "█"
        elif ratio > 0.2:
            char = "▓"
        else:
            char = "░"

        return char * filled + "·" * empty

    def _get_status_icon(self, status: str) -> str:
        """获取状态图标"""
        icons = {
            "burn": "🔥",
            "paralyze": "⚡",
            "poison": "☠️",
            "sleep": "💤",
            "freeze": "❄️",
        }
        return icons.get(status, "")

    async def cmd_bag(self, event: AstrMessageEvent):
        """
        查看精灵背包
        指令: /精灵 背包
        """
        user_id = event.get_sender_id()

        if not self.pm.player_exists(user_id):
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        monsters = self.pm.get_monsters(user_id)

        if not monsters:
            yield event.plain_result(
                "📦 你的背包空空如也~\n"
                "发送 /精灵 探索 去捕捉精灵吧！"
            )
            return

        lines = ["📦 精灵背包", "━━━━━━━━━━━━━━━━━━━━"]

        for i, m in enumerate(monsters, 1):
            name = m.get("nickname") or m.get("name", "???")
            level = m.get("level", 1)
            types = m.get("types", [])
            rarity = m.get("rarity", 3)
            current_hp = m.get("current_hp", 0)
            max_hp = m.get("max_hp", 1)
            is_team = m.get("_is_in_team", False)
            status = m.get("status", "")

            # 属性图标
            type_icons = ""
            for t in types:
                type_config = self.config.get_item("types", t)
                if type_config:
                    type_icons += type_config.get("icon", "")

            team_mark = "⚔️" if is_team else "　"
            stars = "⭐" * min(rarity, 5)
            hp_percent = int(current_hp / max_hp * 100) if max_hp > 0 else 0
            status_icon = self._get_status_icon(status)

            lines.append(f"{team_mark}{i}. {name} Lv.{level} {type_icons} {status_icon}")
            lines.append(f"　　HP:{hp_percent}% {stars}")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚔️=队伍中")
        lines.append("发送 /精灵 详情 [序号] 查看详情")

        yield event.plain_result("\n".join(lines))

    async def cmd_detail(self, event: AstrMessageEvent, index: int = 1):
        """
        查看精灵详情
        指令: /精灵 详情 [序号]
        """
        user_id = event.get_sender_id()
        MonsterInstance = self._get_monster_instance_class()

        monsters = self.pm.get_monsters(user_id)
        if not monsters:
            yield event.plain_result("📦 你还没有精灵")
            return

        if index < 1 or index > len(monsters):
            yield event.plain_result(f"❌ 请输入 1 到 {len(monsters)} 之间的序号")
            return

        monster_data = monsters[index - 1]
        monster = MonsterInstance.from_dict(monster_data, self.config)
        detail_text = monster.get_detail(self.config)

        yield event.plain_result(detail_text)

    async def cmd_team(self, event: AstrMessageEvent, *args):
        """
        队伍管理
        指令:
        /精灵 队伍 - 查看队伍
        /精灵 队伍 设置 1 3 5 - 设置队伍
        /精灵 队伍 加入 2 - 添加到队伍
        /精灵 队伍 移除 1 - 从队伍移除
        """
        user_id = event.get_sender_id()

        if not self.pm.player_exists(user_id):
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        # 无参数：查看队伍
        if not args:
            team = self.pm.get_team(user_id)
            if not team:
                yield event.plain_result(
                    "👥 队伍为空！\n"
                    "发送 /精灵 队伍 设置 1 2 3 来设置队伍"
                )
                return

            lines = ["👥 当前队伍", "━━━━━━━━━━━━━━━━━━━━"]
            for i, m in enumerate(team, 1):
                name = m.get("nickname") or m.get("name", "???")
                level = m.get("level", 1)
                current_hp = m.get("current_hp", 0)
                max_hp = m.get("max_hp", 1)
                status = m.get("status", "")

                hp_bar = self._make_hp_bar(current_hp, max_hp, 8)
                status_icon = self._get_status_icon(status)

                lines.append(f"{i}. {name} Lv.{level} {status_icon}")
                lines.append(f"　 HP: {hp_bar} {current_hp}/{max_hp}")

            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("发送 /精灵 队伍 设置 1 2 3 调整队伍")
            yield event.plain_result("\n".join(lines))
            return

        action = args[0]

        # 设置队伍
        if action in ["设置", "set"] and len(args) > 1:
            monsters = self.pm.get_monsters(user_id)
            if not monsters:
                yield event.plain_result("❌ 你没有精灵")
                return

            try:
                indices = [int(x) for x in args[1:]]
            except ValueError:
                yield event.plain_result("❌ 请输入正确的序号，如: /精灵 队伍 设置 1 2 3")
                return

            monster_ids = []
            for idx in indices:
                if 1 <= idx <= len(monsters):
                    mid = monsters[idx - 1].get("instance_id")
                    if mid and mid not in monster_ids:
                        monster_ids.append(mid)

            if not monster_ids:
                yield event.plain_result("❌ 没有有效的精灵序号")
                return

            if len(monster_ids) > 6:
                yield event.plain_result("❌ 队伍最多6只精灵")
                return

            if self.pm.set_team(user_id, monster_ids):
                yield event.plain_result(f"✅ 队伍设置成功！共 {len(monster_ids)} 只精灵")
            else:
                yield event.plain_result("❌ 设置失败")

        # 加入队伍
        elif action in ["加入", "添加", "add"] and len(args) > 1:
            try:
                idx = int(args[1])
            except ValueError:
                yield event.plain_result("❌ 请输入正确的序号")
                return

            monsters = self.pm.get_monsters(user_id)
            if idx < 1 or idx > len(monsters):
                yield event.plain_result(f"❌ 请输入 1 到 {len(monsters)} 之间的序号")
                return

            monster_id = monsters[idx - 1].get("instance_id")
            monster_name = monsters[idx - 1].get("nickname") or monsters[idx - 1].get("name", "???")

            if self.pm.add_to_team(user_id, monster_id):
                yield event.plain_result(f"✅ {monster_name} 已加入队伍！")
            else:
                yield event.plain_result("❌ 添加失败（队伍已满或已在队伍中）")

        # 移除队伍
        elif action in ["移除", "移出", "remove"] and len(args) > 1:
            try:
                pos = int(args[1])
            except ValueError:
                yield event.plain_result("❌ 请输入正确的位置")
                return

            team = self.pm.get_team(user_id)
            if pos < 1 or pos > len(team):
                yield event.plain_result(f"❌ 请输入 1 到 {len(team)} 之间的位置")
                return

            monster_id = team[pos - 1].get("instance_id")
            monster_name = team[pos - 1].get("nickname") or team[pos - 1].get("name", "???")

            if self.pm.remove_from_team(user_id, monster_id):
                yield event.plain_result(f"✅ {monster_name} 已从队伍移除")
            else:
                yield event.plain_result("❌ 移除失败（队伍至少需要1只精灵）")

        else:
            yield event.plain_result(
                "👥 队伍管理指令：\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "/精灵 队伍 - 查看当前队伍\n"
                "/精灵 队伍 设置 1 3 5 - 设置队伍\n"
                "/精灵 队伍 加入 2 - 添加精灵\n"
                "/精灵 队伍 移除 1 - 移除精灵"
            )

    async def cmd_evolve(self, event: AstrMessageEvent, index: int = 0):
        """
        进化精灵
        指令: /精灵 进化 [序号]
        """
        user_id = event.get_sender_id()
        MonsterInstance = self._get_monster_instance_class()

        monsters = self.pm.get_monsters(user_id)
        if not monsters:
            yield event.plain_result("❌ 你还没有精灵")
            return

        # 无参数：显示可进化列表
        if index == 0:
            evolvable = []
            for i, m_data in enumerate(monsters, 1):
                monster = MonsterInstance.from_dict(m_data, self.config)
                if monster.can_evolve():
                    evolvable.append((i, monster))

            if not evolvable:
                yield event.plain_result("❌ 目前没有可进化的精灵")
                return

            lines = ["✨ 可进化的精灵", "━━━━━━━━━━━━━━━━━━━━"]
            for idx, monster in evolvable:
                evo_target = self.config.get_item("monsters", monster.evolves_to)
                target_name = evo_target.get("name", "???") if evo_target else "???"
                lines.append(f"{idx}. {monster.get_display_name()} → {target_name}")

            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("发送 /精灵 进化 [序号] 进行进化")
            yield event.plain_result("\n".join(lines))
            return

        # 执行进化
        if index < 1 or index > len(monsters):
            yield event.plain_result(f"❌ 请输入 1 到 {len(monsters)} 之间的序号")
            return

        monster_data = monsters[index - 1]
        monster = MonsterInstance.from_dict(monster_data, self.config)

        if not monster.can_evolve():
            yield event.plain_result(
                f"❌ {monster.get_display_name()} 还不能进化\n"
                f"需要达到 Lv.{monster.evolution_level or '?'}"
            )
            return

        old_name = monster.get_display_name()
        evo_target = self.config.get_item("monsters", monster.evolves_to)
        new_name = evo_target.get("name", "???") if evo_target else "???"

        # 执行进化
        evolved = monster.evolve(self.config)
        if not evolved:
            yield event.plain_result("❌ 进化失败，目标精灵数据不存在")
            return

        # 保存
        self.pm.update_monster(monster)

        yield event.plain_result(
            f"🎊 恭喜！\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{old_name} 进化成了 {monster.get_display_name()}！\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{monster.get_summary(self.config)}"
        )

    async def cmd_rename(self, event: AstrMessageEvent, index: int = 0, *name_parts):
        """
        给精灵起昵称
        指令: /精灵 改名 [序号] [新名字]
        """
        user_id = event.get_sender_id()
        MonsterInstance = self._get_monster_instance_class()

        monsters = self.pm.get_monsters(user_id)
        if not monsters:
            yield event.plain_result("❌ 你还没有精灵")
            return

        if index < 1 or index > len(monsters):
            yield event.plain_result(
                f"❌ 请输入正确的指令格式：\n"
                f"/精灵 改名 [序号] [新名字]\n"
                f"例如: /精灵 改名 1 小火龙"
            )
            return

        new_name = " ".join(name_parts).strip()
        if not new_name:
            yield event.plain_result("❌ 请输入新的昵称")
            return

        if len(new_name) > 12:
            yield event.plain_result("❌ 昵称最长12个字符")
            return

        monster_data = monsters[index - 1]
        monster = MonsterInstance.from_dict(monster_data, self.config)
        old_display = monster.get_display_name()

        monster.set_nickname(new_name)
        self.pm.update_monster(monster)

        yield event.plain_result(f"✅ 已将 {old_display} 改名为 {new_name}")

    async def cmd_release(self, event: AstrMessageEvent, index: int = 0):
        """
        放生精灵
        指令: /精灵 放生 [序号]
        """
        user_id = event.get_sender_id()

        monsters = self.pm.get_monsters(user_id)
        if not monsters:
            yield event.plain_result("❌ 你还没有精灵")
            return

        if index < 1 or index > len(monsters):
            yield event.plain_result(f"❌ 请输入 1 到 {len(monsters)} 之间的序号")
            return

        monster = monsters[index - 1]
        monster_name = monster.get("nickname") or monster.get("name", "???")
        instance_id = monster.get("instance_id")

        # 检查是否在队伍中
        if monster.get("_is_in_team"):
            yield event.plain_result(
                f"❌ {monster_name} 正在队伍中\n"
                f"请先将它从队伍移除：/精灵 队伍 移除"
            )
            return

        # 确认放生
        if self.pm.release_monster(user_id, instance_id):
            yield event.plain_result(
                f"👋 {monster_name} 被放归自然了...\n"
                f"希望它能在野外快乐生活"
            )
        else:
            yield event.plain_result("❌ 放生失败")

