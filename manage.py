#!/usr/bin/env python3
"""
manage.py - TrendRadar 项目管理入口
用法:
  python manage.py start_webserver      # 启动 Web 管理服务
  python manage.py webserver_autofix    # Watchdog 健康检查（Docker 用）
"""
import sys
import os


def start_webserver():
    import uvicorn
    from webserver.app import create_app
    host = os.environ.get("WEBSERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("WEBSERVER_PORT", "8080"))
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


def webserver_autofix():
    """每 60 秒检查 /api/system/info，失败则重启（供 entrypoint.sh 调用）"""
    import time
    import subprocess
    import urllib.request
    import urllib.error
    
    port = os.environ.get("WEBSERVER_PORT", "8080")
    interval = int(os.environ.get("WATCHDOG_INTERVAL", "60"))
    
    while True:
        time.sleep(interval)
        try:
            req = urllib.request.Request(
                f"http://localhost:{port}/api/system/info",
                method="GET",
                timeout=5
            )
            with urllib.request.urlopen(req) as resp:
                if resp.status == 200:
                    continue
        except Exception:
            pass
        
        print(f"[Watchdog] Webserver health check failed, restarting...")
        subprocess.Popen([sys.executable, "manage.py", "start_webserver"])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    commands = {
        "start_webserver": start_webserver,
        "webserver_autofix": webserver_autofix,
    }
    
    if cmd in commands:
        commands[cmd]()
    else:
        print("用法: python manage.py [start_webserver|webserver_autofix]")
        sys.exit(1)
