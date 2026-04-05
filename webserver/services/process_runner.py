# coding=utf-8
"""
子进程执行服务 + SSE 日志流
"""
import asyncio
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncGenerator, Dict, Optional


# 全局并发锁，保证同时只有一个 action 在运行
_action_lock = asyncio.Lock()

# 存储正在运行的任务
_running_tasks: Dict[str, "ProcessTask"] = {}


@dataclass
class LogEntry:
    """日志条目"""
    line: str
    level: str = "INFO"
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


@dataclass
class ProcessTask:
    """进程任务"""
    action_id: str
    action_type: str
    process: asyncio.subprocess.Process
    logs: asyncio.Queue
    start_time: datetime
    end_time: Optional[datetime] = None
    exit_code: Optional[int] = None
    done: bool = False


async def run_action(action_type: str, params: Optional[Dict] = None) -> Optional[str]:
    """
    启动一个 action 任务
    返回 action_id，如果已有任务在运行则返回 None
    """
    if _action_lock.locked():
        return None
    
    async with _action_lock:
        action_id = str(uuid.uuid4())[:8]
        
        # 构建命令
        cmd = await _build_command(action_type, params)
        if not cmd:
            return None
        
        # 启动进程
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.getcwd()
        )
        
        # 创建任务
        task = ProcessTask(
            action_id=action_id,
            action_type=action_type,
            process=process,
            logs=asyncio.Queue(),
            start_time=datetime.now()
        )
        
        _running_tasks[action_id] = task
        
        # 启动日志读取协程
        asyncio.create_task(_read_logs(task))
        
        return action_id


async def _build_command(action_type: str, params: Optional[Dict] = None) -> Optional[list]:
    """构建命令（白名单，不允许外部参数注入）"""
    python = sys.executable
    
    commands = {
        "crawl": [python, "-m", "trendradar", "--action", "collect"],
        "analyze": [python, "-m", "trendradar", "--action", "analyze"],
        "push": [python, "-m", "trendradar", "--action", "push"],
        "sync": [python, "-m", "trendradar", "--action", "sync"],
    }
    
    if action_type not in commands:
        return None
    
    return commands[action_type]


async def _read_logs(task: ProcessTask):
    """读取进程输出并放入队列"""
    try:
        if task.process.stdout:
            while True:
                line = await task.process.stdout.readline()
                if not line:
                    break
                
                decoded = line.decode("utf-8", errors="replace").rstrip()
                
                # 检测日志级别
                level = "INFO"
                if "[ERROR]" in decoded or "error" in decoded.lower():
                    level = "ERROR"
                elif "[WARN]" in decoded or "warning" in decoded.lower():
                    level = "WARN"
                elif "[DEBUG]" in decoded:
                    level = "DEBUG"
                
                entry = LogEntry(line=decoded, level=level)
                await task.logs.put(entry)
        
        # 等待进程结束
        task.exit_code = await task.process.wait()
        task.end_time = datetime.now()
        task.done = True
        
        # 发送结束标记
        await task.logs.put(LogEntry(line="", level="DONE"))
        
    except Exception as e:
        await task.logs.put(LogEntry(line=f"Process error: {e}", level="ERROR"))
        task.done = True
        task.exit_code = -1


async def get_log_stream(action_id: str) -> AsyncGenerator[str, None]:
    """
    获取日志流（SSE 格式）
    生成格式: data: {"line": "...", "level": "...", "ts": "..."}
    """
    task = _running_tasks.get(action_id)
    if not task:
        yield f'data: {{"done": true, "error": "Task not found"}}\n\n'
        return
    
    while True:
        try:
            # 等待日志，最多 10 分钟
            entry = await asyncio.wait_for(task.logs.get(), timeout=600)
            
            if entry.level == "DONE":
                yield f'data: {{"done": true, "exit_code": {task.exit_code or 0}}}\n\n'
                break
            
            import json
            data = json.dumps({
                "line": entry.line,
                "level": entry.level,
                "ts": entry.timestamp
            }, ensure_ascii=False)
            yield f"data: {data}\n\n"
            
        except asyncio.TimeoutError:
            yield f'data: {{"done": true, "error": "Timeout"}}\n\n'
            break


def get_task_status(action_id: str) -> Optional[Dict]:
    """获取任务状态"""
    task = _running_tasks.get(action_id)
    if not task:
        return None
    
    return {
        "action_id": task.action_id,
        "action_type": task.action_type,
        "done": task.done,
        "exit_code": task.exit_code,
        "start_time": task.start_time.isoformat(),
        "end_time": task.end_time.isoformat() if task.end_time else None
    }


async def send_test_notification(channel: str, message: str) -> Dict:
    """发送测试通知"""
    # 这里直接调用 notification 模块
    try:
        from trendradar.notification.dispatcher import NotificationDispatcher
        from trendradar.core.loader import load_config
        
        config = load_config()
        dispatcher = NotificationDispatcher(config)
        
        # 构建测试消息
        test_title = "🔔 TrendRadar 测试通知"
        test_content = message or "这是一条测试消息，如果您收到说明通知配置正确。"
        
        # 根据渠道发送
        result = {"success": False, "error": "Channel not supported"}
        
        if channel == "feishu":
            result = await _send_to_channel(dispatcher, "feishu", test_title, test_content)
        elif channel == "dingtalk":
            result = await _send_to_channel(dispatcher, "dingtalk", test_title, test_content)
        elif channel == "wework":
            result = await _send_to_channel(dispatcher, "wework", test_title, test_content)
        elif channel == "telegram":
            result = await _send_to_channel(dispatcher, "telegram", test_title, test_content)
        elif channel == "email":
            result = await _send_to_channel(dispatcher, "email", test_title, test_content)
        elif channel == "ntfy":
            result = await _send_to_channel(dispatcher, "ntfy", test_title, test_content)
        elif channel == "bark":
            result = await _send_to_channel(dispatcher, "bark", test_title, test_content)
        elif channel == "slack":
            result = await _send_to_channel(dispatcher, "slack", test_title, test_content)
        
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _send_to_channel(dispatcher, channel: str, title: str, content: str) -> Dict:
    """发送到指定渠道"""
    try:
        # 使用 dispatcher 的原始方法发送
        if hasattr(dispatcher, f'_send_{channel}'):
            method = getattr(dispatcher, f'_send_{channel}')
            await method(title, content)
            return {"success": True}
        
        # 或者使用通用方法
        from trendradar.notification.senders import send_notifications
        result = await send_notifications(
            title=title,
            content=content,
            config=dispatcher.config,
            channels=[channel]
        )
        return {"success": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


import sys
