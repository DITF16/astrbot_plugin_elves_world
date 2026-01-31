"""
简单的认证模块
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict
from functools import wraps

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse


class AuthManager:
    """认证管理器"""

    def __init__(self, password: str, token_expire_hours: int = 24):
        self.password_hash = self._hash_password(password)
        self.token_expire_hours = token_expire_hours
        self.active_tokens: Dict[str, datetime] = {}

    def _hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str) -> bool:
        """验证密码"""
        return self._hash_password(password) == self.password_hash

    def create_token(self) -> str:
        """创建访问令牌"""
        token = secrets.token_urlsafe(32)
        expire_time = datetime.now() + timedelta(hours=self.token_expire_hours)
        self.active_tokens[token] = expire_time
        self._cleanup_expired_tokens()
        return token

    def verify_token(self, token: str) -> bool:
        """验证令牌"""
        if token not in self.active_tokens:
            return False

        expire_time = self.active_tokens[token]
        if datetime.now() > expire_time:
            del self.active_tokens[token]
            return False

        return True

    def revoke_token(self, token: str):
        """撤销令牌"""
        if token in self.active_tokens:
            del self.active_tokens[token]

    def _cleanup_expired_tokens(self):
        """清理过期令牌"""
        now = datetime.now()
        expired = [t for t, exp in self.active_tokens.items() if now > exp]
        for token in expired:
            del self.active_tokens[token]


def require_auth(auth_manager: AuthManager):
    """认证装饰器工厂"""

    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # 从Header或Cookie获取token
            token = request.headers.get("Authorization", "").replace("Bearer ", "")
            if not token:
                token = request.cookies.get("auth_token", "")

            if not token or not auth_manager.verify_token(token):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未授权访问"
                )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator
