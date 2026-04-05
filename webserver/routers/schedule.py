# coding=utf-8
"""
调度监控 API
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends

from webserver.auth import require_auth
from webserver.services.db_reader import ScheduleDBReader, get_news_db_path
from trendradar.core.loader import load_config
from trendradar.core.scheduler import Scheduler
from trendradar.utils.time import get_configured_time

router = APIRouter(prefix="/api/schedule", dependencies=[Depends(require_auth)])


def get_data_dir() -> str:
    """获取数据目录"""
    try:
        config = load_config()
        return config.get("STORAGE", {}).get("LOCAL", {}).get("DATA_DIR", "output")
    except Exception:
        return "output"


def get_timezone() -> str:
    """获取配置时区"""
    try:
        config = load_config()
        return config.get("TIMEZONE", "Asia/Shanghai")
    except Exception:
        return "Asia/Shanghai"


@router.get("")
async def get_schedule():
    """获取当前调度状态"""
    config = load_config()
    timezone = config.get("TIMEZONE", "Asia/Shanghai")
    
    # 获取当前时间
    now = get_configured_time(timezone)
    now_str = now.strftime("%H:%M")
    
    # 加载调度器
    schedule_config = config.get("SCHEDULE", {})
    timeline_data = config.get("_TIMELINE_DATA", {})
    
    # 创建调度器（不需要 storage backend 来获取状态）
    class DummyStorage:
        def has_period_executed(self, *args, **kwargs):
            return False
        def record_period_execution(self, *args, **kwargs):
            pass
    
    scheduler = Scheduler(
        schedule_config=schedule_config,
        timeline_data=timeline_data,
        storage_backend=DummyStorage(),
        get_time_func=lambda: now,
        fallback_report_mode=config.get("REPORT_MODE", "current")
    )
    
    # 解析当前状态
    resolved = scheduler.resolve()
    
    # 计算下一时段
    next_period = None
    next_period_in = None
    timeline = scheduler.timeline
    day_plan_key = timeline["week_map"].get(now.isoweekday(), "all_day")
    day_plan = timeline["day_plans"].get(day_plan_key, {})
    
    # 查找下一时段
    for period_key in day_plan.get("periods", []):
        period = timeline["periods"].get(period_key, {})
        start = period.get("start", "")
        if start > now_str:
            next_period = {
                "key": period_key,
                "name": period.get("name", period_key),
                "start": start
            }
            # 计算倒计时
            start_h, start_m = map(int, start.split(":"))
            start_minutes = start_h * 60 + start_m
            now_h, now_m = map(int, now_str.split(":"))
            now_minutes = now_h * 60 + now_m
            next_period_in = (start_minutes - now_minutes) * 60  # 转换为秒
            break
    
    # 获取今日执行记录
    data_dir = get_data_dir()
    today_str = now.strftime("%Y-%m-%d")
    db_path = get_news_db_path(data_dir, now.date())
    schedule_reader = ScheduleDBReader(db_path)
    executions = await schedule_reader.get_today_executions(today_str)
    
    return {
        "success": True,
        "data": {
            "current_time": now_str,
            "timezone": timezone,
            "period": {
                "key": resolved.period_key,
                "name": resolved.period_name,
                "day_plan": resolved.day_plan
            },
            "actions": {
                "collect": resolved.collect,
                "analyze": resolved.analyze,
                "push": resolved.push
            },
            "report_mode": resolved.report_mode,
            "ai_mode": resolved.ai_mode,
            "next_period": next_period,
            "next_period_in_seconds": next_period_in,
            "executions": executions,
            "timeline": {
                "preset": schedule_config.get("preset", "always_on"),
                "enabled": schedule_config.get("enabled", True),
                "periods": timeline.get("periods", {}),
                "day_plans": timeline.get("day_plans", {}),
                "week_map": timeline.get("week_map", {}),
                "default": timeline.get("default", {})
            }
        },
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
