"""
精灵管理指令处理器（异步版本）
- 背包、详情、队伍、进化、改名等
- 所有 PlayerManager 调用均使用 await
"""

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..main import MonsterGamePlugin


class MonsterHandlers:
    """精灵管理指令处理器（异步版本）"""

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

        if not await self.pm.player_exists(user_id):
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        monsters = await self.pm.get_monsters(user_id)

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

        monsters = await self.pm.get_monsters(user_id)
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

    async def cmd_team(self, event: AstrMessageEvent):
        """
        查看当前队伍（最多3只，用于战斗）
        指令: /精灵 队伍
        """
        user_id = event.get_sender_id()

        if not await self.pm.player_exists(user_id):
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        team = await self.pm.get_team(user_id)
        monsters = await self.pm.get_monsters(user_id)
        
        # 获取不在队伍中的精灵（背包中待命的）
        team_ids = {m.get("instance_id") for m in team}
        bench_monsters = [m for m in monsters if m.get("instance_id") not in team_ids]

        lines = ["⚔️ 战斗队伍 (最多3只)", "━━━━━━━━━━━━━━━━━━━━"]
        
        if team:
            for i, m in enumerate(team, 1):
                name = m.get("nickname") or m.get("name", "???")
                level = m.get("level", 1)
                current_hp = m.get("current_hp", 0)
                max_hp = m.get("max_hp", 1)
                status = m.get("status", "")

                hp_bar = self._make_hp_bar(current_hp, max_hp, 8)
                status_icon = self._get_status_icon(status)

                lines.append(f"{i}. {name} Lv.{level} {status_icon}")
                lines.append(f"   HP: {hp_bar} {current_hp}/{max_hp}")
        else:
            lines.append("（空）")
        
        lines.append("")
        lines.append(f"📦 背包待命: {len(bench_monsters)} 只")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 /精灵 上阵 <背包序号> - 从背包上阵")
        lines.append("💡 /精灵 下阵 <队伍位置> - 移回背包")
        
        yield event.plain_result("\n".join(lines))

    async def cmd_deploy(self, event: AstrMessageEvent, index: int = 0):
        """
        上阵：从背包选择精灵加入战斗队伍
        指令: /精灵 上阵 <背包序号>
        """
        user_id = event.get_sender_id()

        if not await self.pm.player_exists(user_id):
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        if index <= 0:
            yield event.plain_result(
                "⚔️ 上阵精灵\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "用法: /精灵 上阵 <背包序号>\n"
                "示例: /精灵 上阵 1\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "💡 先用 /精灵 背包 查看序号"
            )
            return

        monsters = await self.pm.get_monsters(user_id)
        if not monsters:
            yield event.plain_result("❌ 你没有精灵")
            return

        if index < 1 or index > len(monsters):
            yield event.plain_result(f"❌ 请输入 1 到 {len(monsters)} 之间的序号")
            return

        monster = monsters[index - 1]
        monster_id = monster.get("instance_id")
        monster_name = monster.get("nickname") or monster.get("name", "???")

        # 检查是否已在队伍中
        team = await self.pm.get_team(user_id)
        team_ids = [m.get("instance_id") for m in team]
        
        if monster_id in team_ids:
            yield event.plain_result(f"❌ {monster_name} 已经在队伍中了")
            return

        # 检查队伍是否已满（最多3只）
        if len(team) >= 3:
            yield event.plain_result(
                f"❌ 队伍已满（3/3）\n"
                f"请先用 /精灵 下阵 <位置> 移除一只精灵"
            )
            return

        if await self.pm.add_to_team(user_id, monster_id):
            new_pos = len(team) + 1
            yield event.plain_result(
                f"✅ {monster_name} 已上阵！\n"
                f"当前队伍位置: {new_pos}/3"
            )
        else:
            yield event.plain_result("❌ 上阵失败")

    async def cmd_withdraw(self, event: AstrMessageEvent, position: int = 0):
        """
        下阵：将精灵从战斗队伍移回背包
        指令: /精灵 下阵 <队伍位置>
        """
        user_id = event.get_sender_id()

        if not await self.pm.player_exists(user_id):
            yield event.plain_result("❌ 你还不是训练师哦，发送 /精灵 注册")
            return

        team = await self.pm.get_team(user_id)
        
        if not team:
            yield event.plain_result("❌ 队伍是空的，没有可下阵的精灵")
            return

        if position <= 0:
            lines = ["⚔️ 下阵精灵", "━━━━━━━━━━━━━━━━━━━━"]
            for i, m in enumerate(team, 1):
                name = m.get("nickname") or m.get("name", "???")
                level = m.get("level", 1)
                lines.append(f"{i}. {name} Lv.{level}")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("用法: /精灵 下阵 <队伍位置>")
            lines.append("示例: /精灵 下阵 1")
            yield event.plain_result("\n".join(lines))
            return

        if position < 1 or position > len(team):
            yield event.plain_result(f"❌ 请输入 1 到 {len(team)} 之间的位置")
            return

        # 队伍至少保留1只精灵
        if len(team) <= 1:
            yield event.plain_result("❌ 队伍至少需要保留1只精灵")
            return

        monster = team[position - 1]
        monster_id = monster.get("instance_id")
        monster_name = monster.get("nickname") or monster.get("name", "???")

        if await self.pm.remove_from_team(user_id, monster_id):
            yield event.plain_result(
                f"✅ {monster_name} 已下阵，移回背包\n"
                f"当前队伍: {len(team) - 1}/3"
            )
        else:
            yield event.plain_result("❌ 下阵失败")



    async def cmd_evolve(self, event: AstrMessageEvent, index: int = 0):
        """
        进化精灵
        指令: /精灵 进化 [序号]
        """
        user_id = event.get_sender_id()
        MonsterInstance = self._get_monster_instance_class()

        monsters = await self.pm.get_monsters(user_id)
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
        await self.pm.update_monster(monster)

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

        monsters = await self.pm.get_monsters(user_id)
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
        await self.pm.update_monster(monster)

        yield event.plain_result(f"✅ 已将 {old_display} 改名为 {new_name}")

    async def cmd_release(self, event: AstrMessageEvent, index: int = 0):
        """
        放生精灵
        指令: /精灵 放生 [序号]
        """
        user_id = event.get_sender_id()

        monsters = await self.pm.get_monsters(user_id)
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
        if await self.pm.release_monster(user_id, instance_id):
            yield event.plain_result(
                f"👋 {monster_name} 被放归自然了...\n"
                f"希望它能在野外快乐生活"
            )
        else:
            yield event.plain_result("❌ 放生失败")

