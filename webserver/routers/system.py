# coding=utf-8
"""
系统信息 API
"""
import os
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends

from webserver.auth import require_auth

router = APIRouter(prefix="/api/system", dependencies=[Depends(require_auth)])


@router.get("/info")
async def get_system_info():
    """获取系统信息"""
    # 版本信息
    version_file = Path("version")
    version = version_file.read_text().strip() if version_file.exists() else "unknown"
    
    version_mcp_file = Path("version_mcp")
    version_mcp = version_mcp_file.read_text().strip() if version_mcp_file.exists() else "unknown"
    
    # 磁盘占用
    data_dir = "output"
    disk_usage = 0
    db_files = []
    
    if os.path.exists(data_dir):
        for root, dirs, files in os.walk(data_dir):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    size = os.path.getsize(fp)
                    disk_usage += size
                    if f.endswith(".db"):
                        db_files.append({
                            "path": fp,
                            "size": size
                        })
                except OSError:
                    pass
    
    # 配置文件修改时间
    config_files = {}
    config_dir = Path(os.environ.get("CONFIG_PATH", "config/config.yaml")).parent
    if config_dir.exists():
        for f in ["config.yaml", "timeline.yaml", "frequency_words.txt", "ai_interests.txt"]:
            fp = config_dir / f
            if fp.exists():
                config_files[f] = datetime.fromtimestamp(
                    fp.stat().st_mtime
                ).isoformat()
    
    # 运行环境检测
    environment = "local"
    if os.environ.get("GITHUB_ACTIONS") == "true":
        environment = "github_actions"
    elif os.path.exists("/.dockerenv"):
        environment = "docker"
    
    return {
        "success": True,
        "data": {
            "version": version,
            "version_mcp": version_mcp,
            "python_version": sys.version,
            "environment": environment,
            "disk_usage": disk_usage,
            "db_files": db_files,
            "config_files": config_files,
            "start_time": datetime.now().isoformat(),
            "auth_enabled": bool(os.environ.get("ADMIN_TOKEN", "").strip())
        },
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
