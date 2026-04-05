# coding=utf-8
"""
手动操作 API
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from webserver.auth import require_auth
from webserver.services import process_runner

router = APIRouter(prefix="/api/actions", dependencies=[Depends(require_auth)])


class CrawlParams(BaseModel):
    platforms: Optional[list] = None  # 预留：指定平台


class TestNotificationParams(BaseModel):
    channel: str
    message: Optional[str] = "这是一条测试消息"


@router.post("/crawl")
async def action_crawl(params: CrawlParams = Body(default=CrawlParams())):
    """触发采集任务"""
    action_id = await process_runner.run_action("crawl", params.dict())
    
    if not action_id:
        return {
            "success": False,
            "data": None,
            "error": "Another action is already running",
            "timestamp": datetime.now().isoformat()
        }
    
    return {
        "success": True,
        "data": {"action_id": action_id},
        "error": None,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/analyze")
async def action_analyze():
    """触发分析任务"""
    action_id = await process_runner.run_action("analyze")
    
    if not action_id:
        return {
            "success": False,
            "data": None,
            "error": "Another action is already running",
            "timestamp": datetime.now().isoformat()
        }
    
    return {
        "success": True,
        "data": {"action_id": action_id},
        "error": None,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/push")
async def action_push():
    """触发推送任务"""
    action_id = await process_runner.run_action("push")
    
    if not action_id:
        return {
            "success": False,
            "data": None,
            "error": "Another action is already running",
            "timestamp": datetime.now().isoformat()
        }
    
    return {
        "success": True,
        "data": {"action_id": action_id},
        "error": None,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/sync")
async def action_sync():
    """触发远程存储同步"""
    action_id = await process_runner.run_action("sync")
    
    if not action_id:
        return {
            "success": False,
            "data": None,
            "error": "Another action is already running",
            "timestamp": datetime.now().isoformat()
        }
    
    return {
        "success": True,
        "data": {"action_id": action_id},
        "error": None,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/test_notification")
async def action_test_notification(params: TestNotificationParams):
    """测试通知渠道"""
    result = await process_runner.send_test_notification(
        channel=params.channel,
        message=params.message
    )
    
    return {
        "success": result.get("success", False),
        "data": result if result.get("success") else None,
        "error": result.get("error") if not result.get("success") else None,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/{action_id}/logs")
async def get_action_logs(action_id: str):
    """获取实时日志流（SSE）"""
    return StreamingResponse(
        process_runner.get_log_stream(action_id),
        media_type="text/event-stream"
    )


@router.get("/{action_id}/status")
async def get_action_status(action_id: str):
    """获取任务状态"""
    status = process_runner.get_task_status(action_id)
    
    if not status:
        return {
            "success": False,
            "data": None,
            "error": "Task not found",
            "timestamp": datetime.now().isoformat()
        }
    
    return {
        "success": True,
        "data": status,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
