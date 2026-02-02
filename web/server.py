"""
Web管理后台服务器
"""

import asyncio
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from astrbot.api import logger

from .auth import AuthManager

if TYPE_CHECKING:
    from ..main import MonsterGamePlugin


class WebServer:
    """Web管理后台服务器"""

    def __init__(self, plugin: "MonsterGamePlugin"):
        self.plugin = plugin
        self.config = plugin.game_config
        self.db = plugin.db
        self.pm = plugin.player_manager

        # 从插件配置读取Web设置
        web_config = plugin.astrbot_config.get("web_admin", {})
        self.enabled = web_config.get("enabled", False)
        self.host = web_config.get("host", "127.0.0.1")
        self.port = web_config.get("port", 8765)
        self.password = web_config.get("admin_password", "admin123")

        # 认证管理器
        self.auth = AuthManager(self.password)

        # FastAPI实例
        self.app: Optional[FastAPI] = None
        self.server_thread: Optional[threading.Thread] = None
        self._server: Optional[uvicorn.Server] = None

        # 静态文件目录
        self.static_dir = Path(__file__).parent / "static"

    def create_app(self) -> FastAPI:
        """创建FastAPI应用"""
        app = FastAPI(
            title="精灵对战游戏管理后台",
            description="管理游戏配置、玩家数据等",
            version="1.0.0",
            docs_url="/api/docs",
            redoc_url=None
        )

        # CORS中间件
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 注册路由
        self._register_routes(app)

        # 静态文件
        if self.static_dir.exists():
            app.mount("/static", StaticFiles(directory=str(self.static_dir)), name="static")

        return app

    def _register_routes(self, app: FastAPI):
        """注册所有路由"""

        # ==================== 页面路由 ====================

        @app.get("/", response_class=HTMLResponse)
        async def index():
            """主页"""
            index_file = self.static_dir / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return HTMLResponse("<h1>精灵对战游戏管理后台</h1><p>静态文件未找到</p>")

        # ==================== 认证API ====================

        @app.post("/api/login")
        async def login(request: Request):
            """登录"""
            try:
                data = await request.json()
                password = data.get("password", "")

                if self.auth.verify_password(password):
                    token = self.auth.create_token()
                    return JSONResponse({
                        "success": True,
                        "token": token,
                        "message": "登录成功"
                    })
                else:
                    return JSONResponse({
                        "success": False,
                        "message": "密码错误"
                    }, status_code=401)
            except Exception as e:
                return JSONResponse({
                    "success": False,
                    "message": str(e)
                }, status_code=400)

        @app.post("/api/logout")
        async def logout(request: Request):
            """登出"""
            token = request.headers.get("Authorization", "").replace("Bearer ", "")
            if token:
                self.auth.revoke_token(token)
            return JSONResponse({"success": True, "message": "已登出"})

        @app.get("/api/check-auth")
        async def check_auth(request: Request):
            """检查认证状态"""
            token = request.headers.get("Authorization", "").replace("Bearer ", "")
            if token and self.auth.verify_token(token):
                return JSONResponse({"authenticated": True})
            return JSONResponse({"authenticated": False}, status_code=401)

        # ==================== 仪表盘API ====================

        @app.get("/api/dashboard")
        async def get_dashboard(request: Request):
            """获取仪表盘数据"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            try:
                stats = {
                    "total_players": self.db.get_total_players(),
                    "total_monsters": self.db.get_total_monsters(),
                    "total_battles": self.db.get_total_battles(),
                    "monster_templates": len(self.config.monsters),
                    "skill_count": len(self.config.skills),
                    "region_count": len(self.config.regions),
                    "server_status": "运行中",
                }
                return JSONResponse({"success": True, "data": stats})
            except Exception as e:
                logger.error(f"获取仪表盘数据失败: {e}")
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        # ==================== 精灵模板API ====================

        @app.get("/api/monsters")
        async def get_monsters(request: Request):
            """获取所有精灵模板"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            monsters = self.config.monsters
            return JSONResponse({
                "success": True,
                "data": list(monsters.values()),
                "total": len(monsters)
            })

        @app.get("/api/monsters/detail")
        async def get_monster(request: Request, id: str = None):
            """获取单个精灵模板"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            if not id:
                raise HTTPException(status_code=400, detail="缺少id参数")

            monster = self.config.get_item("monsters", id)
            if not monster:
                raise HTTPException(status_code=404, detail="精灵不存在")
            return JSONResponse({"success": True, "data": monster})

        @app.post("/api/monsters")
        async def create_monster(request: Request):
            """创建精灵模板"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            try:
                data = await request.json()
                monster_id = data.get("id")

                if not monster_id:
                    return JSONResponse({"success": False, "message": "缺少ID"}, status_code=400)

                if monster_id in self.config.monsters:
                    return JSONResponse({"success": False, "message": "ID已存在"}, status_code=400)

                self.config.monsters[monster_id] = data
                self.config.save_config("monsters")

                return JSONResponse({"success": True, "message": "创建成功"})
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.put("/api/monsters/update")
        async def update_monster(request: Request, id: str = None):
            """更新精灵模板"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            try:
                if not id:
                    raise HTTPException(status_code=400, detail="缺少id参数")

                data = await request.json()
                if id not in self.config.monsters:
                    raise HTTPException(status_code=404, detail="精灵不存在")
                self.config.set_item("monsters", id, data)
                return JSONResponse({"success": True, "message": "更新成功"})
            except HTTPException:
                raise
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.delete("/api/monsters/delete")
        async def delete_monster(request: Request, id: str = None):
            """删除精灵模板"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            if not id:
                raise HTTPException(status_code=400, detail="缺少id参数")
            if id not in self.config.monsters:
                raise HTTPException(status_code=404, detail="精灵不存在")
            self.config.delete_item("monsters", id)
            return JSONResponse({"success": True, "message": "删除成功"})

        # ==================== 技能API ====================

        @app.get("/api/skills")
        async def get_skills(request: Request):
            """获取所有技能"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            skills = self.config.skills
            return JSONResponse({
                "success": True,
                "data": list(skills.values()),
                "total": len(skills)
            })

        @app.get("/api/skills/detail")
        async def get_skill(request: Request, id: str = None):
            """获取单个技能"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            if not id:
                raise HTTPException(status_code=400, detail="缺少id参数")
            skill = self.config.get_item("skills", id)
            if not skill:
                raise HTTPException(status_code=404, detail="技能不存在")
            return JSONResponse({"success": True, "data": skill})

        @app.post("/api/skills")
        async def create_skill(request: Request):
            """创建技能"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            try:
                data = await request.json()
                skill_id = data.get("id")

                if not skill_id:
                    return JSONResponse({"success": False, "message": "缺少ID"}, status_code=400)

                if skill_id in self.config.skills:
                    return JSONResponse({"success": False, "message": "ID已存在"}, status_code=400)

                self.config.skills[skill_id] = data
                self.config.save_config("skills")

                return JSONResponse({"success": True, "message": "创建成功"})
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.put("/api/skills/update")
        async def update_skill(request: Request, id: str = None):
            """更新技能"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            try:
                if not id:
                    raise HTTPException(status_code=400, detail="缺少id参数")

                data = await request.json()
                if id not in self.config.skills:
                    raise HTTPException(status_code=404, detail="技能不存在")
                self.config.set_item("skills", id, data)
                return JSONResponse({"success": True, "message": "更新成功"})
            except HTTPException:
                raise
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.delete("/api/skills/delete")
        async def delete_skill(request: Request, id: str = None):
            """删除技能"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            if not id:
                raise HTTPException(status_code=400, detail="缺少id参数")
            if id not in self.config.skills:
                raise HTTPException(status_code=404, detail="技能不存在")
            self.config.delete_item("skills", id)
            return JSONResponse({"success": True, "message": "删除成功"})

        # ==================== 区域API ====================

        @app.get("/api/regions")
        async def get_regions(request: Request):
            """获取所有区域"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            regions = self.config.regions
            return JSONResponse({
                "success": True,
                "data": list(regions.values()),
                "total": len(regions)
            })

        @app.post("/api/regions")
        async def create_region(request: Request):
            """创建区域"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            try:
                data = await request.json()
                region_id = data.get("id")

                if not region_id:
                    return JSONResponse({"success": False, "message": "缺少ID"}, status_code=400)

                self.config.regions[region_id] = data
                self.config.save_config("regions")

                return JSONResponse({"success": True, "message": "创建成功"})
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.put("/api/regions/update")
        async def update_region(request: Request, id: str = None):
            """更新区域"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            try:
                if not id:
                    raise HTTPException(status_code=400, detail="缺少id参数")

                data = await request.json()

                self.config.set_item("regions", id, data)
                return JSONResponse({"success": True, "message": "更新成功"})
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.delete("/api/regions/delete")
        async def delete_region(request: Request, id: str = None):
            """删除区域"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            if not id:
                raise HTTPException(status_code=400, detail="缺少id参数")

            self.config.delete_item("regions", id)
            return JSONResponse({"success": True, "message": "删除成功"})

        # ==================== BOSS API ====================

        @app.get("/api/bosses")
        async def get_bosses(request: Request):
            """获取所有BOSS"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            bosses = self.config.bosses
            regions = self.config.regions
            
            # 构建 Boss ID -> 区域名称 的映射
            boss_region_map = {}
            for region_id, region_data in regions.items():
                if region_data.get("boss"):
                    boss_region_map[region_data["boss"]] = region_data.get("name", region_id)
            
            # 为每个 Boss 附加所在区域信息
            boss_list = []
            for boss in bosses.values():
                boss_copy = dict(boss)
                boss_copy["region"] = boss_region_map.get(boss.get("id"), "")
                boss_list.append(boss_copy)
            
            return JSONResponse({
                "success": True,
                "data": boss_list,
                "total": len(boss_list)
            })


        @app.post("/api/bosses")
        async def create_boss(request: Request):
            """创建BOSS"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            try:
                data = await request.json()
                boss_id = data.get("id")

                if not boss_id:
                    return JSONResponse({"success": False, "message": "缺少ID"}, status_code=400)

                self.config.bosses[boss_id] = data
                self.config.save_config("bosses")

                return JSONResponse({"success": True, "message": "创建成功"})
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.put("/api/bosses/update")
        async def update_boss(request: Request, id: str = None):
            """更新BOSS"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            try:
                if not id:
                    raise HTTPException(status_code=400, detail="缺少id参数")

                data = await request.json()
                self.config.set_item("bosses", id, data)
                return JSONResponse({"success": True, "message": "更新成功"})
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.delete("/api/bosses/delete")
        async def delete_boss(request: Request, id: str = None):
            """删除BOSS"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            if not id:
                raise HTTPException(status_code=400, detail="缺少id参数")
            self.config.delete_item("bosses", id)
            return JSONResponse({"success": True, "message": "删除成功"})

        # ==================== 物品管理API ====================

        @app.get("/api/items")
        async def get_items(request: Request):
            """获取所有物品"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            items = self.config.items
            return JSONResponse({
                "success": True,
                "data": list(items.values()),
                "total": len(items)
            })

        @app.get("/api/items/detail")
        async def get_item(request: Request, id: str = None):
            """获取单个物品详情"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            if not id:
                raise HTTPException(status_code=400, detail="缺少id参数")

            item = self.config.get_item("items", id)
            if not item:
                raise HTTPException(status_code=404, detail="物品不存在")
            return JSONResponse({"success": True, "data": item})

        @app.post("/api/items")
        async def create_item(request: Request):
            """创建物品"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            try:
                data = await request.json()
                item_id = data.get("id")

                if not item_id:
                    return JSONResponse({"success": False, "message": "缺少ID"}, status_code=400)

                if item_id in self.config.items:
                    return JSONResponse({"success": False, "message": "物品ID已存在"}, status_code=400)

                # 确保必要字段
                data.setdefault("name", item_id)
                data.setdefault("type", "tool")
                data.setdefault("rarity", 1)
                data.setdefault("price", 0)
                data.setdefault("currency", "coins")
                data.setdefault("shop_available", False)
                data.setdefault("sellable", False)
                data.setdefault("sell_price", 0)
                data.setdefault("effect", {})

                self.config.items[item_id] = data
                self.config.save_config("items")

                return JSONResponse({"success": True, "message": "物品已创建"})
            except Exception as e:
                logger.error(f"创建物品失败: {e}")
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.put("/api/items/update")
        async def update_item(request: Request):
            """更新物品"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            try:
                data = await request.json()
                item_id = data.get("id")

                if not item_id or item_id not in self.config.items:
                    return JSONResponse({"success": False, "message": "物品不存在"}, status_code=404)

                # 更新物品数据
                self.config.items[item_id].update(data)
                self.config.save_config("items")

                return JSONResponse({"success": True, "message": "物品已更新"})
            except Exception as e:
                logger.error(f"更新物品失败: {e}")
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.delete("/api/items")
        async def delete_item(request: Request, id: str = None):
            """删除物品"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            if not id:
                raise HTTPException(status_code=400, detail="缺少id参数")

            if id not in self.config.items:
                return JSONResponse({"success": False, "message": "物品不存在"}, status_code=404)

            del self.config.items[id]
            self.config.save_config("items")

            return JSONResponse({"success": True, "message": "物品已删除"})

        # ==================== 玩家管理API ====================

        @app.get("/api/players")
        async def get_players(request: Request, page: int = 1, limit: int = 20):
            """获取玩家列表"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            try:
                offset = (page - 1) * limit
                players = self.db.get_players(limit=limit, offset=offset)
                total = self.db.get_total_players()

                return JSONResponse({
                    "success": True,
                    "data": players,
                    "total": total,
                    "page": page,
                    "limit": limit
                })
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.get("/api/players/{user_id}")
        async def get_player(request: Request, user_id: str):
            """获取单个玩家详情"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            player = self.pm.get_player(user_id)
            if not player:
                raise HTTPException(status_code=404, detail="玩家不存在")

            monsters = self.pm.get_monsters(user_id)

            return JSONResponse({
                "success": True,
                "data": {
                    "player": player,
                    "monsters": monsters,
                    "monster_count": len(monsters)
                }
            })

        @app.post("/api/players/{user_id}/give")
        async def give_to_player(request: Request, user_id: str):
            """给玩家发放奖励"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            try:
                data = await request.json()
                coins = data.get("coins", 0)
                diamonds = data.get("diamonds", 0)
                exp = data.get("exp", 0)
                stamina = data.get("stamina", 0)

                if coins > 0 or diamonds > 0:
                    self.pm.add_currency(user_id, coins=coins, diamonds=diamonds)
                if exp > 0:
                    self.pm.add_exp(user_id, exp)
                if stamina > 0:
                    self.pm.restore_stamina(user_id, stamina)

                return JSONResponse({"success": True, "message": "发放成功"})
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.post("/api/players/{user_id}/reset")
        async def reset_player(request: Request, user_id: str):
            """重置玩家数据"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            try:
                # 删除玩家所有精灵
                self.db.delete_player_monsters(user_id)
                # 重置玩家数据
                self.db.delete_player(user_id)

                return JSONResponse({"success": True, "message": "重置成功"})
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        # ==================== 属性/天气/性格 API ====================

        @app.get("/api/types")
        async def get_types(request: Request):
            """获取所有属性"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            return JSONResponse({"success": True, "data": self.config.types})

        @app.get("/api/weathers")
        async def get_weathers(request: Request):
            """获取所有天气"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            return JSONResponse({"success": True, "data": self.config.weathers})

        @app.get("/api/natures")
        async def get_natures(request: Request):
            """获取所有性格"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            return JSONResponse({"success": True, "data": self.config.natures})

        # ==================== 性格API (完整CRUD) ====================

        @app.get("/api/natures/detail")
        async def get_nature_detail(request: Request, id: str = None):
            """获取性格详情"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            if not id:
                raise HTTPException(status_code=400, detail="缺少id参数")
            nature = self.config.get_item("natures", id)
            if not nature:
                raise HTTPException(status_code=404, detail="性格不存在")
            return JSONResponse({"success": True, "data": nature})

        @app.post("/api/natures")
        async def create_nature(request: Request):
            """创建性格"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            try:
                data = await request.json()
                nature_id = data.get("id")
                if not nature_id:
                    return JSONResponse({"success": False, "message": "缺少ID"}, status_code=400)
                if nature_id in self.config.natures:
                    return JSONResponse({"success": False, "message": "性格ID已存在"}, status_code=400)
                # 确保必要字段
                data.setdefault("name", nature_id)
                data.setdefault("buff_stat", None)
                data.setdefault("buff_percent", 0)
                data.setdefault("debuff_stat", None)
                data.setdefault("debuff_percent", 0)
                data.setdefault("weight", 10)
                data.setdefault("description", "")
                self.config.set_item("natures", nature_id, data)
                return JSONResponse({"success": True, "message": "创建成功"})
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.put("/api/natures/update")
        async def update_nature(request: Request, id: str = None):
            """更新性格"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            try:
                if not id:
                    raise HTTPException(status_code=400, detail="缺少id参数")
                data = await request.json()
                if id not in self.config.natures:
                    raise HTTPException(status_code=404, detail="性格不存在")
                self.config.set_item("natures", id, data)
                return JSONResponse({"success": True, "message": "更新成功"})
            except HTTPException:
                raise
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.delete("/api/natures/delete")
        async def delete_nature(request: Request, id: str = None):
            """删除性格"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")
            if not id:
                raise HTTPException(status_code=400, detail="缺少id参数")
            if id not in self.config.natures:
                raise HTTPException(status_code=404, detail="性格不存在")
            # 防止删除最后一个性格
            if len(self.config.natures) <= 1:
                return JSONResponse({"success": False, "message": "至少保留一个性格"}, status_code=400)
            self.config.delete_item("natures", id)
            return JSONResponse({"success": True, "message": "删除成功"})


        # ==================== 配置操作API ====================

        @app.post("/api/config/reload")
        async def reload_config(request: Request):
            """重载所有配置"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            try:
                self.config.reload_all()
                return JSONResponse({"success": True, "message": "配置已重载"})
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        @app.post("/api/config/backup")
        async def backup_config(request: Request):
            """备份配置"""
            if not self._check_auth(request):
                raise HTTPException(status_code=401, detail="未授权")

            try:
                backup_path = self.config.backup_all()
                return JSONResponse({"success": True, "message": f"已备份到: {backup_path}"})
            except Exception as e:
                return JSONResponse({"success": False, "message": str(e)}, status_code=500)

    def _check_auth(self, request: Request) -> bool:
        """检查请求认证"""
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            token = request.cookies.get("auth_token", "")
        return bool(token and self.auth.verify_token(token))

    def start(self):
        """启动Web服务器（非阻塞）"""
        if not self.enabled:
            logger.info("🌐 Web管理后台已禁用")
            return

        self.app = self.create_app()

        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="warning"
        )
        self._server = uvicorn.Server(config)

        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()

        logger.info(f"🌐 Web管理后台已启动: http://{self.host}:{self.port}")

    def _run_server(self):
        """在线程中运行服务器"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._server.serve())

    def stop(self):
        """停止Web服务器"""
        if self._server:
            self._server.should_exit = True
            logger.info("🌐 Web管理后台已停止")
