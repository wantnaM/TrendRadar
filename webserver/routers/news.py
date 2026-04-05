# coding=utf-8
"""
新闻数据 API
"""
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from webserver.auth import require_auth
from webserver.services.db_reader import NewsDBReader, get_news_db_path, get_available_dates
from trendradar.core.loader import load_config

router = APIRouter(prefix="/api/news", dependencies=[Depends(require_auth)])


def get_data_dir() -> str:
    """获取数据目录"""
    try:
        config = load_config()
        return config.get("STORAGE", {}).get("LOCAL", {}).get("DATA_DIR", "output")
    except Exception:
        return "output"


@router.get("/dates")
async def get_dates():
    """获取有数据的日期列表"""
    data_dir = get_data_dir()
    dates = get_available_dates(data_dir, "news")
    
    return {
        "success": True,
        "data": {"dates": dates},
        "error": None,
        "timestamp": datetime.datetime.now().isoformat()
    }


@router.get("")
async def get_news(
    date: Optional[str] = None,
    platform: Optional[str] = Query(None, description="平台 ID，可多选（逗号分隔）"),
    keyword: Optional[str] = None,
    sort_by: str = Query("rank", description="排序字段: rank / crawl_count / first_crawl_time"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100)
):
    """获取新闻列表"""
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
    
    db_path = get_news_db_path(data_dir, target_date)
    reader = NewsDBReader(db_path)
    
    # 查询
    data, total = await reader.get_news_list(
        platform=platform,
        keyword=keyword,
        sort_by=sort_by,
        page=page,
        per_page=per_page
    )
    
    # 获取平台列表（用于筛选器）
    platforms = await reader.get_platforms()
    
    return {
        "success": True,
        "data": {
            "items": data,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
            "platforms": platforms
        },
        "error": None,
        "timestamp": datetime.datetime.now().isoformat()
    }


@router.get("/{news_id}/rank-history")
async def get_rank_history(news_id: int):
    """获取指定新闻的排名历史"""
    data_dir = get_data_dir()
    db_path = get_news_db_path(data_dir, datetime.date.today())
    reader = NewsDBReader(db_path)
    
    history = await reader.get_rank_history(news_id)
    
    return {
        "success": True,
        "data": {"history": history},
        "error": None,
        "timestamp": datetime.datetime.now().isoformat()
    }
