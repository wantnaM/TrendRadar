# coding=utf-8
"""
RSS 数据 API
"""
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from webserver.auth import require_auth
from webserver.services.db_reader import RSSDBReader, get_rss_db_path, get_available_dates
from trendradar.core.loader import load_config

router = APIRouter(prefix="/api/rss", dependencies=[Depends(require_auth)])


def get_data_dir() -> str:
    """获取数据目录"""
    try:
        config = load_config()
        return config.get("STORAGE", {}).get("LOCAL", {}).get("DATA_DIR", "output")
    except Exception:
        return "output"


@router.get("/feeds")
async def get_feeds():
    """获取 RSS 源状态列表"""
    data_dir = get_data_dir()
    db_path = get_rss_db_path(data_dir, datetime.date.today())
    reader = RSSDBReader(db_path)
    
    feeds = await reader.get_feeds_status()
    
    return {
        "success": True,
        "data": {"feeds": feeds},
        "error": None,
        "timestamp": datetime.datetime.now().isoformat()
    }


@router.get("")
async def get_rss_items(
    date: Optional[str] = None,
    feed: Optional[str] = Query(None, description="RSS 源 ID"),
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100)
):
    """获取 RSS 文章列表"""
    data_dir = get_data_dir()
    
    # 默认今天
    target_date_str = date
    if not target_date_str:
        target_date_str = datetime.date.today().isoformat()
    
    # 解析日期
    try:
        target_date = datetime.date.fromisoformat(target_date_str)
    except (ValueError, TypeError):
        target_date = datetime.date.today()
    
    db_path = get_rss_db_path(data_dir, target_date)
    reader = RSSDBReader(db_path)
    
    # 查询
    data, total = await reader.get_items(
        feed_id=feed,
        keyword=keyword,
        page=page,
        per_page=per_page
    )
    
    # 获取源列表
    feeds = await reader.get_feeds_status()
    
    return {
        "success": True,
        "data": {
            "items": data,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
            "feeds": feeds
        },
        "error": None,
        "timestamp": datetime.datetime.now().isoformat()
    }
