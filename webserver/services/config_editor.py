# coding=utf-8
"""
配置文件编辑器服务
支持读写、备份、恢复
"""
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


# 配置文件映射
CONFIG_FILES = {
    "config_yaml": "config.yaml",
    "timeline_yaml": "timeline.yaml",
    "frequency_words": "frequency_words.txt",
    "ai_interests": "ai_interests.txt",
    "ai_analysis_prompt": "ai_analysis_prompt.txt",
    "ai_translation_prompt": "ai_translation_prompt.txt",
    "ai_filter_extract": "extract_prompt.txt",
    "ai_filter_classify": "prompt.txt",
}


def get_config_dir() -> str:
    """获取配置目录"""
    config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")
    return str(Path(config_path).parent)


def get_file_path(file_key: str) -> Optional[str]:
    """获取文件实际路径"""
    if file_key not in CONFIG_FILES:
        return None
    return os.path.join(get_config_dir(), CONFIG_FILES[file_key])


def list_backups(file_key: str) -> List[Dict[str, Any]]:
    """列出所有备份文件"""
    file_path = get_file_path(file_key)
    if not file_path:
        return []
    
    backup_pattern = re.compile(re.escape(os.path.basename(file_path)) + r"\.bak\.(\d{8}-\d{6})")
    config_dir = get_config_dir()
    
    backups = []
    for f in os.listdir(config_dir):
        match = backup_pattern.match(f)
        if match:
            timestamp = match.group(1)
            backup_path = os.path.join(config_dir, f)
            stat = os.stat(backup_path)
            backups.append({
                "filename": f,
                "timestamp": timestamp,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    
    # 按时间倒序
    backups.sort(key=lambda x: x["timestamp"], reverse=True)
    return backups


def create_backup(file_key: str) -> Optional[str]:
    """创建备份，返回备份文件名"""
    file_path = get_file_path(file_key)
    if not file_path or not os.path.exists(file_path):
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"{os.path.basename(file_path)}.bak.{timestamp}"
    backup_path = os.path.join(get_config_dir(), backup_name)
    
    shutil.copy2(file_path, backup_path)
    
    # 清理旧备份，只保留最近 10 份
    backups = list_backups(file_key)
    if len(backups) > 10:
        for old_backup in backups[10:]:
            old_path = os.path.join(get_config_dir(), old_backup["filename"])
            try:
                os.remove(old_path)
            except OSError:
                pass
    
    return backup_name


def restore_backup(file_key: str, backup_filename: str) -> bool:
    """恢复指定备份"""
    file_path = get_file_path(file_key)
    if not file_path:
        return False
    
    backup_path = os.path.join(get_config_dir(), backup_filename)
    if not os.path.exists(backup_path):
        return False
    
    # 先备份当前文件
    create_backup(file_key)
    
    # 恢复
    shutil.copy2(backup_path, file_path)
    return True


def read_file(file_key: str) -> Tuple[str, bool]:
    """
    读取文件内容
    返回: (内容, 是否存在)
    """
    file_path = get_file_path(file_key)
    if not file_path:
        return "", False
    
    if not os.path.exists(file_path):
        return "", False
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read(), True
    except Exception as e:
        return f"# Error reading file: {e}", False


def write_file(file_key: str, content: str) -> Tuple[bool, str]:
    """
    写入文件内容
    返回: (是否成功, 错误信息)
    """
    file_path = get_file_path(file_key)
    if not file_path:
        return False, f"Unknown file key: {file_key}"
    
    # YAML 文件需要验证格式
    if file_key == "config_yaml" or file_key == "timeline_yaml":
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            return False, f"YAML format error: {e}"
    
    # 创建备份
    create_backup(file_key)
    
    # 写入
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True, ""
    except Exception as e:
        return False, str(e)


def parse_config_yaml(content: str) -> Dict:
    """解析 config.yaml 为结构化数据（用于前端表单）"""
    try:
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError:
        data = {}
    
    return {
        "app": data.get("app", {}),
        "schedule": data.get("schedule", {}),
        "platforms": data.get("platforms", {"enabled": True, "sources": []}),
        "rss": data.get("rss", {"enabled": True, "feeds": []}),
        "report": data.get("report", {}),
        "filter": data.get("filter", {}),
        "ai_filter": data.get("ai_filter", {}),
        "display": data.get("display", {}),
        "notification": data.get("notification", {}),
        "storage": data.get("storage", {}),
        "ai": data.get("ai", {}),
        "ai_analysis": data.get("ai_analysis", {}),
        "ai_translation": data.get("ai_translation", {}),
        "advanced": data.get("advanced", {}),
    }


def parse_frequency_words(content: str) -> List[Dict]:
    """解析 frequency_words.txt"""
    groups = []
    current_group = None
    
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        if line.startswith("[") and line.endswith("]"):
            # 新组
            if current_group:
                groups.append(current_group)
            current_group = {
                "name": line[1:-1],
                "keywords": [],
                "rules": {"required": 0, "excluded": 0, "limited": 0}
            }
        elif current_group:
            # 关键词
            current_group["keywords"].append(line)
            if line.startswith("+"):
                current_group["rules"]["required"] += 1
            elif line.startswith("!"):
                current_group["rules"]["excluded"] += 1
            elif "@" in line:
                current_group["rules"]["limited"] += 1
    
    if current_group:
        groups.append(current_group)
    
    return groups


def parse_ai_interests(content: str) -> List[Dict]:
    """解析 ai_interests.txt"""
    interests = []
    current = None
    
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        
        if not line.startswith("-") and not line.startswith("  "):
            # 新类别
            if current:
                interests.append(current)
            current = {
                "category": line.rstrip(":"),
                "keywords": [],
                "priority": len(interests) + 1
            }
        elif current and line.startswith("-"):
            # 关键词
            keyword = line[1:].strip()
            current["keywords"].append(keyword)
    
    if current:
        interests.append(current)
    
    return interests


def parse_timeline_yaml(content: str) -> Dict:
    """解析 timeline.yaml"""
    try:
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError:
        data = {}
    
    return {
        "presets": data.get("presets", {}),
        "custom": data.get("custom", {})
    }
