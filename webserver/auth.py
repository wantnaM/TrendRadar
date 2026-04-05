# coding=utf-8
"""
可选的 Bearer Token 认证
环境变量 ADMIN_TOKEN 设置时启用，未设置时不认证
"""
import os
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


security = HTTPBearer(auto_error=False)


def is_auth_enabled() -> bool:
    """检查是否启用了认证"""
    return bool(os.environ.get("ADMIN_TOKEN", "").strip())


def get_admin_token() -> str:
    """获取配置的 admin token"""
    return os.environ.get("ADMIN_TOKEN", "")


async def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = None) -> bool:
    """验证 token"""
    if not is_auth_enabled():
        return True
    
    if not credentials:
        return False
    
    expected_token = get_admin_token()
    provided_token = credentials.credentials
    
    # 简单的字符串比较（生产环境应使用更安全的比较）
    return provided_token == expected_token


async def require_auth(request: Request) -> None:
    """
    依赖项：要求认证
    在路由中使用: dependencies=[Depends(require_auth)]
    """
    if not is_auth_enabled():
        return
    
    auth_header = request.headers.get("authorization", "")
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = auth_header[7:]  # 去掉 "Bearer "
    expected_token = get_admin_token()
    
    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )
