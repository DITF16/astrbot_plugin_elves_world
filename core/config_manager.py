"""
配置管理器 - 统一管理所有游戏配置的加载、保存和热更新

支持异步操作，避免阻塞事件循环
增强错误处理：JSON解析失败时保留旧配置，避免数据丢失
"""

import json
import shutil
import asyncio
from pathlib import Path
from typing import Dict, Optional, Callable, List, Set
from threading import Lock
import time
from astrbot.api import logger


class ConfigLoadError(Exception):
    """配置加载错误异常"""
    def __init__(self, config_name: str, filepath: Path, original_error: Exception):
        self.config_name = config_name
        self.filepath = filepath
        self.original_error = original_error
        super().__init__(f"Failed to load config '{config_name}' from {filepath}: {original_error}")


class ConfigManager:
    """
    游戏配置管理器
    - 管理所有JSON配置文件
    - 支持热更新（Web后台修改后自动生效）
    - 线程安全
    - 支持异步操作（避免阻塞事件循环）
    - 增强错误处理：JSON解析失败时保留旧配置，防止数据覆盖
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
        "catch_config": "catch_config.json",
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

        # 记录加载失败的配置（防止被空数据覆盖）
        self._corrupted_configs: Set[str] = set()

        # 更新回调（支持同步和异步回调）
        self._update_callbacks: List[Callable] = []

        # 初始化配置文件（同步，仅在启动时执行一次）
        self._init_config_files()

        # 加载所有配置（同步，仅在启动时执行一次）
        self._reload_all_sync()

    def _init_config_files(self):
        """初始化配置文件，如果不存在则从默认目录复制"""
        for config_name, filename in self.CONFIG_FILES.items():
            target_file = self.data_path / filename
            default_file = self.default_data_path / f"default_{filename}"

            if not target_file.exists() and default_file.exists():
                shutil.copy(default_file, target_file)

    # ==================== 同步方法（内部使用）====================

    def _reload_all_sync(self):
        """同步重新加载所有配置（仅供初始化使用）"""
        with self._lock:
            for config_name in self.CONFIG_FILES:
                try:
                    self._load_config_sync(config_name)
                except ConfigLoadError as e:
                    # 记录错误但不中断其他配置加载
                    logger.error(f"❌ {e}")

    def _load_config_sync(self, config_name: str) -> Dict:
        """
        同步加载单个配置文件
        
        Raises:
            ConfigLoadError: 当配置文件损坏或无法解析时抛出
        """
        filename = self.CONFIG_FILES.get(config_name)
        if not filename:
            return {}

        filepath = self.data_path / filename
        if not filepath.exists():
            logger.warning(f"⚠️ 配置文件不存在: {filepath}")
            # 文件不存在是正常情况（首次运行），设置空缓存
            self._cache[config_name] = {}
            return {}

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 自动为每个项目添加ID（使用键名）
            for key, value in data.items():
                if isinstance(value, dict) and 'id' not in value:
                    value['id'] = key

            # 加载成功，从损坏列表中移除（如果之前在里面）
            self._corrupted_configs.discard(config_name)

            # 存入缓存
            self._cache[config_name] = data
            self._cache_time[config_name] = time.time()

            logger.info(f"✅ 已加载配置 {config_name}: {len(data)} 项")
            return data

        except json.JSONDecodeError as e:
            # JSON格式错误 - 标记为损坏，保留旧缓存
            self._corrupted_configs.add(config_name)
            logger.error(f"❌ 配置文件JSON格式错误 {filepath}: {e}")
            logger.warning(f"⚠️ 配置 '{config_name}' 已标记为损坏，保留旧缓存，禁止保存")
            
            # 不修改缓存！保留之前的有效数据
            if config_name not in self._cache:
                raise ConfigLoadError(config_name, filepath, e)
            
            return self._cache.get(config_name, {})

        except Exception as e:
            # 其他错误 - 同样标记为损坏
            self._corrupted_configs.add(config_name)
            logger.error(f"❌ 加载配置文件失败 {filepath}: {e}")
            
            if config_name not in self._cache:
                raise ConfigLoadError(config_name, filepath, e)
            
            return self._cache.get(config_name, {})

    def _save_config_sync(self, config_name: str, data: Dict) -> bool:
        """
        同步保存配置文件
        
        安全机制：
        1. 如果配置被标记为损坏，拒绝保存以防止数据丢失
        2. 使用临时文件+原子替换，避免写入中断导致文件损坏
        3. 写入后验证JSON有效性
        """
        # 安全检查：拒绝保存损坏的配置
        if config_name in self._corrupted_configs:
            logger.error(f"🛡️ 安全保护：配置 '{config_name}' 之前加载失败，拒绝保存以防止数据丢失")
            logger.error(f"   请先手动修复配置文件，然后调用 reload_all() 重新加载")
            return False
        
        filename = self.CONFIG_FILES.get(config_name)
        if not filename:
            return False

        filepath = self.data_path / filename

        try:
            # 先写入临时文件，成功后再替换（原子写入）
            temp_filepath = filepath.with_suffix('.json.tmp')
            
            with self._lock:
                with open(temp_filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # 验证写入的JSON是否有效
                with open(temp_filepath, 'r', encoding='utf-8') as f:
                    json.load(f)  # 如果解析失败会抛异常
                
                # 替换原文件（原子操作）
                temp_filepath.replace(filepath)
                
                self._cache[config_name] = data
                self._cache_time[config_name] = time.time()
            
            return True
        except Exception as e:
            logger.error(f"❌ 保存配置 {config_name} 失败: {e}")
            # 清理临时文件
            temp_filepath = filepath.with_suffix('.json.tmp')
            if temp_filepath.exists():
                try:
                    temp_filepath.unlink()
                except:
                    pass
            return False

    # ==================== 异步方法（推荐在协程中使用）====================

    async def reload_all(self):
        """
        异步重新加载所有配置
        
        在异步上下文中调用此方法不会阻塞事件循环
        """
        await asyncio.to_thread(self._reload_all_sync)

        # 触发更新回调
        await self._trigger_callbacks()

    async def set_async(self, config_name: str, data: Dict) -> bool:
        """
        异步设置整个配置
        
        Args:
            config_name: 配置名称
            data: 配置数据
            
        Returns:
            是否保存成功
        """
        success = await asyncio.to_thread(self._save_config_sync, config_name, data)
        
        if success:
            await self._trigger_callbacks()
        
        return success

    async def set_item_async(self, config_name: str, item_id: str, item_data: Dict) -> bool:
        """异步设置配置中的单个项目"""
        config = self.get(config_name)
        config[item_id] = item_data
        return await self.set_async(config_name, config)

    async def delete_item_async(self, config_name: str, item_id: str) -> bool:
        """异步删除配置中的单个项目"""
        config = self.get(config_name)
        if item_id in config:
            del config[item_id]
            return await self.set_async(config_name, config)
        return False

    async def _trigger_callbacks(self):
        """触发所有更新回调（支持同步和异步回调）"""
        for callback in self._update_callbacks:
            try:
                result = callback()
                # 如果回调返回协程，则等待它
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"配置更新回调执行失败: {e}")

    # ==================== 同步读取方法（从缓存读取，无IO）====================

    def get(self, config_name: str) -> Dict:
        """
        获取配置（从缓存）
        
        注意：此方法是同步的，因为只读取内存缓存，无磁盘IO
        """
        with self._lock:
            return self._cache.get(config_name, {}).copy()

    def get_item(self, config_name: str, item_id: str) -> Optional[Dict]:
        """获取配置中的单个项目（从缓存）"""
        config = self.get(config_name)
        return config.get(item_id)


    def register_update_callback(self, callback: Callable):
        """
        注册配置更新回调
        
        回调可以是同步函数或异步函数（async def）
        """
        self._update_callbacks.append(callback)

    def is_corrupted(self, config_name: str) -> bool:
        """检查配置是否被标记为损坏"""
        return config_name in self._corrupted_configs

    def get_corrupted_configs(self) -> Set[str]:
        """获取所有损坏的配置名称列表"""
        return self._corrupted_configs.copy()

    def clear_corrupted_flag(self, config_name: str) -> bool:
        """
        手动清除配置的损坏标记（在手动修复文件后调用）
        
        注意：这不会重新加载配置，只是允许后续的保存操作
        建议在调用此方法后立即调用 reload_all() 重新加载配置
        """
        if config_name in self._corrupted_configs:
            self._corrupted_configs.discard(config_name)
            logger.info(f"✅ 已清除配置 '{config_name}' 的损坏标记")
            return True
        return False


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

    @property
    def catch_config(self) -> Dict:
        """获取捕捉系统配置"""
        return self.get("catch_config")

