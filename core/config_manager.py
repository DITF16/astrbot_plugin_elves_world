"""
配置管理器 - 统一管理所有游戏配置的加载、保存和热更新
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Optional, Callable, List
from threading import Lock
import time
from astrbot.api import logger


class ConfigManager:
    """
    游戏配置管理器
    - 管理所有JSON配置文件
    - 支持热更新（Web后台修改后自动生效）
    - 线程安全
    """

    CONFIG_FILES = {
        "types": "types.json",
        "natures": "natures.json",
        "weathers": "weathers.json",
        "monsters": "monsters.json",
        "skills": "skills.json",
        "regions": "regions.json",
        "bosses": "bosses.json",
        "items": "items.json",
    }

    def __init__(self, data_path: Path, default_data_path: Path):
        """
        初始化配置管理器

        Args:
            data_path: 运行时数据目录 (可读写)
            default_data_path: 默认数据目录 (只读，插件自带)
        """
        self.data_path = Path(data_path)
        self.default_data_path = Path(default_data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)

        # 配置缓存
        self._cache: Dict[str, Dict] = {}
        self._cache_time: Dict[str, float] = {}
        self._lock = Lock()

        # 更新回调
        self._update_callbacks: List[Callable] = []

        # 初始化配置文件
        self._init_config_files()

        # 加载所有配置
        self.reload_all()

    def _init_config_files(self):
        """初始化配置文件，如果不存在则从默认目录复制"""
        for config_name, filename in self.CONFIG_FILES.items():
            target_file = self.data_path / filename
            default_file = self.default_data_path / f"default_{filename}"

            if not target_file.exists() and default_file.exists():
                shutil.copy(default_file, target_file)

    def reload_all(self):
        """重新加载所有配置"""
        with self._lock:
            for config_name in self.CONFIG_FILES:
                self._load_config(config_name)

        # 触发更新回调
        for callback in self._update_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"配置更新回调执行失败: {e}")

    def _load_config(self, config_name: str) -> Dict:
        """加载配置文件"""
        filename = self.CONFIG_FILES.get(config_name)
        if not filename:
            return {}

        filepath = self.data_path / filename
        if not filepath.exists():
            logger.warning(f"⚠️ 配置文件不存在: {filepath}")
            self._cache[config_name] = {}
            return {}

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 自动为每个项目添加ID（使用键名）
            for key, value in data.items():
                if isinstance(value, dict) and 'id' not in value:
                    value['id'] = key

            # 存入缓存
            self._cache[config_name] = data
            self._cache_time[config_name] = time.time()

            logger.info(f"✅ 已加载配置 {config_name}: {len(data)} 项")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"❌ 配置文件JSON格式错误 {filepath}: {e}")
            self._cache[config_name] = {}
            return {}
        except Exception as e:
            logger.error(f"❌ 加载配置文件失败 {filepath}: {e}")
            self._cache[config_name] = {}
            return {}

    def get(self, config_name: str) -> Dict:
        """获取配置（从缓存）"""
        with self._lock:
            return self._cache.get(config_name, {}).copy()

    def get_item(self, config_name: str, item_id: str) -> Optional[Dict]:
        """获取配置中的单个项目"""
        config = self.get(config_name)
        return config.get(item_id)

    def set(self, config_name: str, data: Dict) -> bool:
        """设置整个配置"""
        filename = self.CONFIG_FILES.get(config_name)
        if not filename:
            return False

        filepath = self.data_path / filename

        try:
            with self._lock:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self._cache[config_name] = data
                self._cache_time[config_name] = time.time()

            # 触发更新回调
            for callback in self._update_callbacks:
                try:
                    callback()
                except Exception as e:
                    print(f"配置更新回调执行失败: {e}")

            return True
        except Exception as e:
            print(f"保存配置 {config_name} 失败: {e}")
            return False

    def set_item(self, config_name: str, item_id: str, item_data: Dict) -> bool:
        """设置配置中的单个项目"""
        config = self.get(config_name)
        config[item_id] = item_data
        return self.set(config_name, config)

    def delete_item(self, config_name: str, item_id: str) -> bool:
        """删除配置中的单个项目"""
        config = self.get(config_name)
        if item_id in config:
            del config[item_id]
            return self.set(config_name, config)
        return False

    def register_update_callback(self, callback: Callable):
        """注册配置更新回调"""
        self._update_callbacks.append(callback)

    # ==================== 便捷属性 ====================

    @property
    def types(self) -> Dict:
        """获取属性配置"""
        return self.get("types")

    @property
    def natures(self) -> Dict:
        """获取性格配置"""
        return self.get("natures")

    @property
    def weathers(self) -> Dict:
        """获取天气配置"""
        return self.get("weathers")

    @property
    def monsters(self) -> Dict:
        """获取精灵配置"""
        return self.get("monsters")

    @property
    def skills(self) -> Dict:
        """获取技能配置"""
        return self.get("skills")

    @property
    def regions(self) -> Dict:
        """获取区域配置"""
        return self.get("regions")

    @property
    def bosses(self) -> Dict:
        """获取BOSS配置"""
        return self.get("bosses")

    @property
    def items(self) -> Dict:
        """获取道具配置"""
        return self.get("items")
