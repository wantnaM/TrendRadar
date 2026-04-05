# coding=utf-8
"""
配置管理 API
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel

from webserver.auth import require_auth
from webserver.services import config_editor

router = APIRouter(prefix="/api/config", dependencies=[Depends(require_auth)])


class ConfigContent(BaseModel):
    content: str


@router.get("/{file_key}")
async def get_config(file_key: str, parsed: bool = False):
    """读取配置文件"""
    content, exists = config_editor.read_file(file_key)
    
    if not exists:
        return {
            "success": False,
            "data": None,
            "error": f"File not found: {file_key}",
            "timestamp": datetime.now().isoformat()
        }
    
    data = {"content": content}
    
    # 解析特定文件
    if parsed:
        if file_key == "config_yaml":
            data["parsed"] = config_editor.parse_config_yaml(content)
        elif file_key == "frequency_words":
            data["parsed"] = config_editor.parse_frequency_words(content)
        elif file_key == "ai_interests":
            data["parsed"] = config_editor.parse_ai_interests(content)
        elif file_key == "timeline_yaml":
            data["parsed"] = config_editor.parse_timeline_yaml(content)
    
    return {
        "success": True,
        "data": data,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }


@router.put("/{file_key}")
async def update_config(file_key: str, body: ConfigContent):
    """保存配置文件"""
    success, error = config_editor.write_file(file_key, body.content)
    
    if not success:
        return {
            "success": False,
            "data": None,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
    
    return {
        "success": True,
        "data": {"message": "Saved successfully"},
        "error": None,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/{file_key}/backups")
async def list_backups(file_key: str):
    """列出备份文件"""
    backups = config_editor.list_backups(file_key)
    
    return {
        "success": True,
        "data": {"backups": backups},
        "error": None,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/{file_key}/restore")
async def restore_backup(file_key: str, body: dict = Body(...)):
    """恢复指定备份"""
    backup_filename = body.get("backup_filename")
    if not backup_filename:
        return {
            "success": False,
            "data": None,
            "error": "backup_filename is required",
            "timestamp": datetime.now().isoformat()
        }
    
    success = config_editor.restore_backup(file_key, backup_filename)
    
    if not success:
        return {
            "success": False,
            "data": None,
            "error": "Failed to restore backup",
            "timestamp": datetime.now().isoformat()
        }
    
    return {
        "success": True,
        "data": {"message": "Restored successfully"},
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
