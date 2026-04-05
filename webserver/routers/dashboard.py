# coding=utf-8
"""
仪表盘 API
"""
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from webserver.auth import require_auth
from webserver.services.db_reader import (
    NewsDBReader, RSSDBReader, ScheduleDBReader,
    get_news_db_path, get_rss_db_path, get_available_dates
)
from trendradar.core.loader import load_config

router = APIRouter(prefix="/api/dashboard", dependencies=[Depends(require_auth)])


def get_data_dir() -> str:
    """获取数据目录"""
    try:
        config = load_config()
        return config.get("STORAGE", {}).get("LOCAL", {}).get("DATA_DIR", "output")
    except Exception:
        return "output"


@router.get("")
async def get_dashboard():
    """获取仪表盘汇总数据"""
    data_dir = get_data_dir()
    today = date.today()
    today_str = today.isoformat()
    
    # 数据库路径
    news_db_path = get_news_db_path(data_dir, today)
    rss_db_path = get_rss_db_path(data_dir, today)
    
    # 今日统计
    news_reader = NewsDBReader(news_db_path)
    news_stats = await news_reader.get_today_stats()
    
    rss_reader = RSSDBReader(rss_db_path)
    rss_stats = await rss_reader.get_today_stats()
    
    # 平台状态
    platforms = await news_reader.get_platforms_status()
    
    # Top 10 新闻
    top_news = await news_reader.get_top_news(10)
    
    # 数据库文件数
    news_dates = get_available_dates(data_dir, "news")
    rss_dates = get_available_dates(data_dir, "rss")
    
    return {
        "success": True,
        "data": {
            "today": {
                "news_count": news_stats["count"],
                "rss_count": rss_stats["count"],
                "last_crawl": news_stats["last_crawl"],
                "db_count": {
                    "news": len(news_dates),
                    "rss": len(rss_dates)
                }
            },
            "platforms": platforms,
            "top_news": top_news
        },
        "error": None,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/chart")
async def get_chart_data(days: int = 7):
    """获取近 N 天趋势图数据"""
    data_dir = get_data_dir()
    today = date.today()
    
    # 收集数据
    news_data = []
    rss_data = []
    
    for i in range(days - 1, -1, -1):
        target_date = today - timedelta(days=i)
        date_str = target_date.isoformat()
        
        # News
        news_db = get_news_db_path(data_dir, target_date)
        if os.path.exists(news_db):
            reader = NewsDBReader(news_db)
            stats = await reader.get_today_stats()
            news_data.append({"date": date_str, "count": stats["count"]})
        else:
            news_data.append({"date": date_str, "count": 0})
        
        # RSS
        rss_db = get_rss_db_path(data_dir, target_date)
        if os.path.exists(rss_db):
            reader = RSSDBReader(rss_db)
            stats = await reader.get_today_stats()
            rss_data.append({"date": date_str, "count": stats["count"]})
        else:
            rss_data.append({"date": date_str, "count": 0})
    
    return {
        "success": True,
        "data": {
            "news": news_data,
            "rss": rss_data
        },
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
