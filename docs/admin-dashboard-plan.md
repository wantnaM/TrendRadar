# TrendRadar 管理仪表盘 · 开发计划书

> **版本**: v1.0 | **日期**: 2026-04-05 | **目标版本**: TrendRadar v6.7.0

---

## 一、项目背景与目标

### 现状

TrendRadar 目前完全依赖 YAML 配置文件管理所有设置，数据存储在 SQLite 数据库中，运行过程不可见，操作须通过命令行完成：

- 配置修改：手动编辑 `config/config.yaml`、`timeline.yaml`、`frequency_words.txt` 等
- 数据查看：无界面，须直接操作 SQLite 文件
- 运行触发：只能通过 Cron 定时或 `uv run trendradar` 手动执行
- 状态监控：无实时反馈

### 目标

开发一套 **Web 管理仪表盘**，通过浏览器即可完成所有日常管理操作：

| 能力 | 说明 |
|------|------|
| 数据可视化 | 实时查看采集数据、排名变化、趋势图表 |
| 配置管理 | 在线编辑所有配置文件，支持备份恢复 |
| 数据库浏览 | 分页查询新闻/RSS 数据，支持筛选搜索 |
| 手动操作 | 按需触发采集、分析、推送，实时查看日志 |
| 调度监控 | 可视化当前时段状态与执行历史 |

---

## 二、技术选型

### 后端

| 组件 | 选型 | 理由 |
|------|------|------|
| Web 框架 | **FastAPI** | 轻量异步，自动生成 OpenAPI 文档，与现有 Python 环境一致 |
| 数据库驱动 | **aiosqlite** | 异步读取现有 SQLite，无需迁移数据 |
| 进程管理 | **asyncio.subprocess** | 触发子进程执行 trendradar 采集/推送任务 |
| 实时推送 | **SSE (Server-Sent Events)** | 将子进程日志实时流式推送到前端，无需 WebSocket |
| 认证 | **Bearer Token**（可选） | 环境变量 `ADMIN_TOKEN` 控制，不配置则不启用 |
| 新增依赖 | `fastapi`, `uvicorn`, `aiosqlite`, `python-multipart` | |

### 前端

| 组件 | 选型 | 理由 |
|------|------|------|
| 响应式框架 | **Alpine.js 3.x**（CDN） | 无需构建工具，单 HTML 文件即可运行 |
| 样式 | **TailwindCSS**（CDN） | 快速构建暗色主题 UI |
| 图表 | **Chart.js**（CDN） | 折线图、柱状图，轻量无依赖 |
| 部署形式 | **单文件 SPA** | `webserver/static/index.html`，所有 CSS/JS 内联 |

### 端口与部署

- **端口**: `8080`（复用 Docker 中已规划的 `WEBSERVER_PORT=8080`）
- **启动命令**: `python manage.py start_webserver`（`docker/entrypoint.sh` 已预留此命令）
- **访问地址**: `http://localhost:8080`

---

## 三、新增文件结构

> **原则：不修改任何现有文件，全部为纯新增。**

```
TrendRadar/
├── manage.py                          # 新增：管理入口脚本
└── webserver/                         # 新增：Web 管理服务目录
    ├── __init__.py
    ├── app.py                         #   FastAPI 应用工厂 + 静态文件挂载
    ├── auth.py                        #   Bearer Token 认证中间件（可选）
    ├── routers/                       #   路由模块（每个功能独立文件）
    │   ├── __init__.py
    │   ├── dashboard.py               #   GET  /api/dashboard
    │   ├── news.py                    #   GET  /api/news/*
    │   ├── rss.py                     #   GET  /api/rss/*
    │   ├── config.py                  #   GET/PUT /api/config/*
    │   ├── schedule.py                #   GET  /api/schedule/*
    │   ├── actions.py                 #   POST /api/actions/* + SSE 日志
    │   └── system.py                  #   GET  /api/system/info
    ├── services/                      #   业务逻辑层
    │   ├── db_reader.py               #   SQLite 异步读取（只读）
    │   ├── config_editor.py           #   配置文件读写 + 备份管理
    │   └── process_runner.py          #   子进程执行 + SSE 日志流
    └── static/
        └── index.html                 #   单文件前端 SPA（内联所有 CSS/JS）
```

**`pyproject.toml` 新增依赖**：

```toml
"fastapi>=0.115.0",
"uvicorn>=0.34.0",
"aiosqlite>=0.21.0",
"python-multipart>=0.0.20",
```

---

## 四、manage.py 实现规范

```python
#!/usr/bin/env python3
"""
manage.py - TrendRadar 项目管理入口
用法:
  python manage.py start_webserver      # 启动 Web 管理服务
  python manage.py webserver_autofix    # Watchdog 健康检查（Docker 用）
"""
import sys, os

def start_webserver():
    import uvicorn
    from webserver.app import create_app
    host = os.environ.get("WEBSERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("WEBSERVER_PORT", "8080"))
    uvicorn.run(create_app(), host=host, port=port, log_level="info")

def webserver_autofix():
    """每 60 秒检查 /api/system/info，失败则重启（供 entrypoint.sh 调用）"""
    import time, subprocess, requests
    port = os.environ.get("WEBSERVER_PORT", "8080")
    while True:
        time.sleep(60)
        try:
            requests.get(f"http://localhost:{port}/api/system/info", timeout=5)
        except Exception:
            subprocess.Popen(["python", "manage.py", "start_webserver"])

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    {"start_webserver": start_webserver, "webserver_autofix": webserver_autofix}.get(
        cmd, lambda: print("用法: python manage.py [start_webserver|webserver_autofix]")
    )()
```

---

## 五、功能模块详细设计

### 5.1 系统仪表盘（Dashboard）

**路由**: `/#/`
**API**: `GET /api/dashboard`

#### 展示内容

**① 顶部状态卡片（4 格）**

| 卡片 | 数据来源 | SQL |
|------|----------|-----|
| 今日采集条数 | 当日 news DB · `news_items` | `SELECT COUNT(*) FROM news_items` |
| 今日 RSS 条数 | 当日 rss DB · `rss_items` | `SELECT COUNT(*) FROM rss_items` |
| 最近采集时间 | `crawl_records` 最新记录 | `SELECT crawl_time FROM crawl_records ORDER BY crawl_time DESC LIMIT 1` |
| 数据库文件数 | 列出 `output/news/` 和 `output/rss/` 的 `.db` 文件数 | Python `os.listdir()` |

**② 平台采集状态网格**

- 所有平台列表（来自 `platforms` 表）
- 每个平台最近一次采集状态
- 颜色标注：`success` = 绿，`failed` = 红，无记录 = 灰

```sql
SELECT p.id, p.name, cs.status, cr.crawl_time
FROM platforms p
LEFT JOIN crawl_source_status cs ON p.id = cs.platform_id
LEFT JOIN crawl_records cr ON cs.crawl_record_id = cr.id
WHERE cr.crawl_time = (SELECT MAX(crawl_time) FROM crawl_records);
```

**③ 今日热榜 Top 10**

- 最新批次前 10 条，显示：排名 · 平台 · 标题（可点击）

**④ 近 7 天采集量趋势图（Chart.js 折线图）**

- X 轴：日期，Y 轴：采集条数
- 两条线：新闻热榜 vs RSS

---

### 5.2 新闻数据浏览器（News Browser）

**路由**: `/#/news`
**API**: `GET /api/news`

#### 查询参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `date` | string | 今日 | 格式 YYYY-MM-DD |
| `platform` | string | 全部 | 平台 ID，可多选（逗号分隔） |
| `keyword` | string | - | 标题关键词模糊搜索 |
| `sort_by` | string | rank | rank / crawl_count / first_crawl_time |
| `page` | int | 1 | 页码 |
| `per_page` | int | 50 | 每页条数 |

#### 展示内容

1. **日期选择器**：下拉列表，仅展示有数据的日期（`GET /api/news/dates`）
2. **平台过滤器**：多选 Checkbox
3. **关键词搜索框**：实时过滤（防抖 300ms）
4. **数据表格**

| 列 | 说明 |
|----|------|
| 排名 | 当前排名，颜色区分 Top3/Top10/其他 |
| 平台 | 平台名称 |
| 标题 | 可点击跳转原文，超长截断 |
| 首次出现 | `first_crawl_time` |
| 最后更新 | `last_crawl_time` |
| 出现次数 | `crawl_count`，热度指标 |
| 操作 | 查看排名历史 |

5. **排名历史弹窗**：点击行尾图标，Chart.js 折线图展示该条新闻的 `rank_history`（X轴时间，Y轴排名，Y轴反转使排名1在顶部）
6. **分页控件**：首页/上页/页码/下页/末页

```sql
-- 数据查询
SELECT ni.id, ni.title, ni.url, ni.rank,
       ni.first_crawl_time, ni.last_crawl_time, ni.crawl_count,
       p.name AS platform_name
FROM news_items ni JOIN platforms p ON ni.platform_id = p.id
WHERE ni.title LIKE '%{keyword}%'
ORDER BY ni.{sort_by} ASC
LIMIT {per_page} OFFSET {(page-1)*per_page};

-- 排名历史
SELECT rank, crawl_time FROM rank_history
WHERE news_item_id = {id} ORDER BY crawl_time ASC;
```

---

### 5.3 RSS 数据浏览器（RSS Browser）

**路由**: `/#/rss`
**API**: `GET /api/rss`

#### 查询参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `date` | string | 日期 YYYY-MM-DD |
| `feed` | string | RSS 源 ID |
| `keyword` | string | 标题/摘要关键词 |
| `page` / `per_page` | int | 分页 |

#### 展示内容

1. **RSS 源状态卡片**（顶部横排）：每个 feed 显示名称、最近采集时间、条数、状态
2. **文章列表表格**

| 列 | 说明 |
|----|------|
| 来源 | Feed 名称 |
| 标题 | 可点击跳转，超长截断 |
| 作者 | `author` 字段 |
| 发布时间 | `published_at` |
| 摘要 | 前 80 字，点击行展开完整内容 |

---

### 5.4 配置编辑器（Config Editor）

**路由**: `/#/config`
**API**:
- `GET /api/config/{file}` — 读取原始内容
- `PUT /api/config/{file}` — 保存（写前自动备份）
- `GET /api/config/{file}/backups` — 列出备份
- `POST /api/config/{file}/restore` — 恢复指定备份

**file 枚举值**: `config_yaml` · `timeline_yaml` · `frequency_words` · `ai_interests` · `ai_analysis_prompt` · `ai_translation_prompt` · `ai_filter_extract` · `ai_filter_classify`

#### Tab 设计

**Tab 1 — config.yaml（结构化表单）**

按 Section 分组折叠展开：

| Section | 表单控件 |
|---------|---------|
| 基本设置 | 时区下拉、调度预设单选 |
| 热榜平台 | 每平台一个 Toggle 开关（enable/disable） |
| RSS 订阅 | 可增删行的动态表格（url / name / max_age_days） |
| 报告模式 | 单选：daily / current / incremental |
| 过滤策略 | 单选：keyword / ai + AI 参数子项 |
| 通知渠道 | 每渠道折叠卡片（URL/Token 字段，密码框隐藏） |
| AI 配置 | 模型名、API Key（密码框）、API Base URL |
| 高级设置 | 权重滑块（rank/frequency/hotness，三值之和=1） |

- 保存前显示 Diff 对比（修改前 vs 修改后 YAML）
- 保存按钮 + 恢复最近备份按钮

**Tab 2 — timeline.yaml**

- 左侧：原始 YAML 文本编辑器（等宽字体 `<textarea>`）
- 右侧：24h 时间轴预览（与 `docs/architecture.html` 风格一致）
- 实时解析，编辑时右侧同步更新

**Tab 3 — frequency_words.txt**

- 左侧：原始文本编辑器
- 右侧：解析预览（关键词组列表，显示组名 + 关键词数量 + 规则类型统计）
- 底部：语法速查卡片（`[组名]` · `/regex/=>别名` · `+必选` · `!排除` · `@N限制`）

**Tab 4 — ai_interests.txt**

- 文本编辑器 + 右侧解析预览（14 类目列表，带优先级排序）

**Tab 5 — Prompt 模板**

- 子 Tab 切换：`ai_analysis_prompt` · `ai_translation_prompt` · `ai_filter_extract` · `ai_filter_classify`
- 纯文本编辑器（等宽字体，行号显示）

---

### 5.5 调度监控（Schedule Monitor）

**路由**: `/#/schedule`
**API**: `GET /api/schedule`

#### 展示内容

**① 当前状态面板**

| 字段 | 说明 |
|------|------|
| 当前时间 | 配置时区的本地时间（实时刷新） |
| 当前时段 | 正在生效的 Period 名称 |
| 执行动作 | collect / analyze / push 的开关状态（图标+颜色） |
| 下一时段 | 名称 + 距离开始的倒计时 |

**② 24h 时间轴**

- 与 `architecture.html` 完全一致的彩色时间轴
- 当前时刻显示红色竖线标注

**③ 今日执行记录（来自 `period_executions` 表）**

- 时间线样式展示：时间 → 时段名 → 动作类型
- 颜色区分：collect=蓝，analyze=紫，push=绿

```sql
SELECT executed_at, period_key, action
FROM period_executions
WHERE execution_date = '{today}'
ORDER BY executed_at DESC;
```

---

### 5.6 手动操作（Manual Actions）

**路由**: `/#/actions`
**API**: `POST /api/actions/{action}`

#### 操作卡片列表

| 操作 | 接口 | 子进程命令 | 参数 |
|------|------|-----------|------|
| 触发采集 | `POST /api/actions/crawl` | `python -m trendradar --action collect` | 平台选择（全部/指定） |
| 触发分析 | `POST /api/actions/analyze` | `python -m trendradar --action analyze` | 无 |
| 触发推送 | `POST /api/actions/push` | `python -m trendradar --action push` | 报告模式选择 |
| 测试通知 | `POST /api/actions/test_notification` | 直接调用 notification 模块 | 渠道选择 + 测试消息 |
| 同步远程 | `POST /api/actions/sync` | `python -m trendradar --action sync` | 仅远程存储已配置时显示 |

**每张卡片包含**：
- 操作说明文字
- 参数配置区（如有）
- 执行按钮（点击弹出确认对话框）
- 实时日志输出区（黑底绿字等宽字体，滚动到底部）

**实时日志实现**：

```
POST /api/actions/crawl
  → 返回 { action_id: "uuid" }

GET /api/actions/{action_id}/logs  (SSE 流)
  → data: {"line": "开始采集 weibo...", "level": "INFO", "ts": "10:32:01"}
  → data: {"line": "weibo 采集完成，共 50 条", "level": "INFO", "ts": "10:32:03"}
  → data: {"done": true, "exit_code": 0}
```

**安全约束**：
- 同一时刻只允许运行一个 action（并发锁）
- 命令只允许预定义白名单，不接受外部参数注入

---

### 5.7 系统信息（System Info）

**路由**: `/#/system`（侧边栏底部）
**API**: `GET /api/system/info`

| 字段 | 说明 |
|------|------|
| 版本信息 | trendradar v6.6.0 · MCP v4.0.2 |
| Python 版本 | `sys.version` |
| 运行环境 | Docker / 本地 / GitHub Actions |
| 磁盘占用 | `output/` 目录大小 |
| 数据库列表 | 所有 `.db` 文件及大小 |
| 配置文件 | 各配置文件最后修改时间 |
| 启动时间 | 服务启动时间戳 |

---

## 六、完整 API 接口表

所有接口统一响应格式：

```json
{
  "success": true,
  "data": { },
  "error": null,
  "timestamp": "2026-04-05T10:30:00+08:00"
}
```

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/dashboard` | 仪表盘汇总数据 |
| GET | `/api/dashboard/chart` | 近 7 天趋势图数据 |
| GET | `/api/news` | 新闻列表（分页+过滤） |
| GET | `/api/news/dates` | 有数据的日期列表 |
| GET | `/api/news/{id}/rank-history` | 指定新闻排名历史 |
| GET | `/api/rss` | RSS 文章列表（分页+过滤） |
| GET | `/api/rss/feeds` | RSS 源状态列表 |
| GET | `/api/config/{file}` | 读取配置文件原始内容 |
| PUT | `/api/config/{file}` | 保存配置文件（写前备份） |
| GET | `/api/config/{file}/backups` | 列出所有备份文件 |
| POST | `/api/config/{file}/restore` | 恢复指定备份 |
| GET | `/api/schedule` | 当前调度状态 + 今日执行记录 |
| POST | `/api/actions/crawl` | 触发采集任务 |
| POST | `/api/actions/analyze` | 触发分析任务 |
| POST | `/api/actions/push` | 触发推送任务 |
| POST | `/api/actions/test_notification` | 测试通知渠道 |
| POST | `/api/actions/sync` | 触发远程存储同步 |
| GET | `/api/actions/{id}/logs` | SSE：实时日志流 |
| GET | `/api/system/info` | 系统信息 |
| GET | `/` | 前端 SPA（index.html） |

---

## 七、前端 UI 规范

### 整体布局

```
┌─────────────────────────────────────────────────────┐
│  ⚡ TrendRadar Admin          v6.6.0   [管理员]      │  ← 顶部固定导航
├──────────┬──────────────────────────────────────────┤
│          │                                          │
│  仪表盘  │                                          │
│  新闻    │          主内容区（路由切换）              │
│  RSS     │                                          │
│  配置    │                                          │
│  调度    │                                          │
│  操作    │                                          │
│  ──────  │                                          │
│  系统    │                                          │
└──────────┴──────────────────────────────────────────┘
```

### 设计规范

| 属性 | 值 |
|------|-----|
| 背景色 | `#06080d`（主背景）/ `#111827`（卡片） |
| 强调色 | `#00e5ff`（青色）/ `#8b5cf6`（紫色）|
| 成功色 | `#10b981` |
| 警告色 | `#f59e0b` |
| 失败色 | `#ef4444` |
| 中文字体 | `PingFang SC, Microsoft YaHei, sans-serif` |
| 等宽字体 | `Cascadia Code, Fira Code, Consolas, monospace` |
| 卡片圆角 | `12px` |
| 卡片边框 | `1px solid #1a2340`，hover 时 `#2d3f6a` |

### 响应式断点

- `≥ 1024px`：左侧固定侧边栏（宽 200px）
- `768px ~ 1024px`：侧边栏折叠为图标
- `< 768px`：底部导航栏

---

## 八、安全设计

### 访问认证（可选）

```bash
# 配置方式（环境变量）
ADMIN_TOKEN=your-secret-token-here

# 未配置时：不启用认证（适合本地使用）
# 已配置时：所有 /api/* 请求须携带 Header
Authorization: Bearer your-secret-token-here
```

前端在 `localStorage` 中存储 token，登录页面负责录入。

### 配置文件写入保护

1. 写入前自动备份：`{file}.bak.{YYYYMMDD-HHMMSS}`
2. YAML 写入前用 `yaml.safe_load()` 验证格式合法性
3. 每个文件保留最近 10 份备份，超出自动清理最旧的

### 子进程执行安全

- Actions 接口只允许执行**预定义白名单命令**，不拼接用户输入参数
- 全局并发锁：同一时刻只能运行一个 action 任务
- 超时保护：单次任务最长运行 10 分钟，超时强制终止

### Docker 网络隔离

- 默认绑定 `0.0.0.0:8080`，但 Docker Compose 已映射为 `127.0.0.1:8080`，不暴露公网

---

## 九、与现有代码的集成方式

> **核心原则：不修改 `trendradar/` 和 `mcp_server/` 任何现有代码。**

### 直接 import 复用

```python
# webserver/services/db_reader.py 中直接复用
from trendradar.core.loader import load_config          # 读取配置
from trendradar.core.scheduler import Scheduler         # 调度状态解析
from trendradar.utils.time import get_configured_time   # 时区时间

# 获取数据目录路径
config = load_config()
data_dir = config.get("storage", {}).get("local", {}).get("data_dir", "output")
```

### SQLite 路径约定

```python
import os
from datetime import date

def get_news_db(data_dir: str, target_date: date) -> str:
    return os.path.join(data_dir, "news", f"{target_date}.db")

def get_rss_db(data_dir: str, target_date: date) -> str:
    return os.path.join(data_dir, "rss", f"{target_date}.db")
```

### 数据库操作原则

- **只读**：webserver 只查询 SQLite，**不做任何写入**（写入由 trendradar 主程序负责）
- **异步**：使用 `aiosqlite` 异步读取，不阻塞 FastAPI 事件循环

---

## 十、开发阶段规划

### Phase 1 — 基础框架（优先完成）

- [ ] 创建 `manage.py`
- [ ] 创建 `webserver/` 目录结构及所有 `__init__.py`
- [ ] 实现 `webserver/app.py`（FastAPI 工厂，挂载静态文件，注册路由）
- [ ] 实现 `webserver/services/db_reader.py`（aiosqlite 基础查询）
- [ ] 实现 `GET /api/system/info` 和 `GET /api/dashboard`
- [ ] 前端骨架：侧边栏 + hash 路由框架 + 仪表盘页面
- [ ] 在 `pyproject.toml` 添加新依赖并 `uv sync`

**验收标准**：`python manage.py start_webserver` 启动后，访问 `http://localhost:8080` 可见仪表盘，显示今日采集条数和平台状态。

---

### Phase 2 — 数据浏览

- [ ] 实现 `GET /api/news` 系列（分页、筛选、排名历史）
- [ ] 前端：新闻浏览器页面（表格 + 筛选器 + 分页）
- [ ] 前端：排名历史弹窗（Chart.js 折线图）
- [ ] 实现 `GET /api/rss` 系列
- [ ] 前端：RSS 浏览器页面

**验收标准**：可查看任意日期的新闻列表，点击新闻可看到其排名历史曲线。

---

### Phase 3 — 配置管理

- [ ] 实现 `webserver/services/config_editor.py`（读写 + 备份）
- [ ] 实现 `GET/PUT /api/config/{file}` 及备份恢复接口
- [ ] 前端：config.yaml 结构化表单（所有 Section）
- [ ] 前端：timeline.yaml 文本编辑器 + 24h 预览
- [ ] 前端：frequency_words.txt 编辑器 + 解析预览
- [ ] 前端：ai_interests.txt 和 Prompt 编辑器

**验收标准**：可在界面修改平台开关，保存后 `config.yaml` 内容同步更新，原文件自动备份。

---

### Phase 4 — 操作与监控

- [ ] 实现 `webserver/services/process_runner.py`（asyncio 子进程 + SSE）
- [ ] 实现 Actions 系列 API（crawl / analyze / push / test）
- [ ] 前端：手动操作页面（操作卡片 + 实时日志滚动框）
- [ ] 实现 `GET /api/schedule` 及执行历史
- [ ] 前端：调度监控页面（当前状态 + 24h 时间轴 + 执行记录）

**验收标准**：点击"触发采集"后，日志框实时滚动显示采集进度，完成后显示结果。

---

### Phase 5 — 收尾与集成

- [ ] 完善全局错误处理（API 统一 error 格式）
- [ ] 实现可选 Token 认证（`auth.py`）
- [ ] 验证 Docker 环境下 `ENABLE_WEBSERVER=true` 正常启动
- [ ] 在 `version` 文件更新版本号为 `6.7.0`

---

## 十一、关键注意事项

### 给 AI 实现者的提示

1. **不要修改任何现有文件**（除 `pyproject.toml` 添加依赖外），所有代码在 `manage.py` 和 `webserver/` 中新增

2. **SQLite 只读**：所有数据库操作只使用 `SELECT`，不执行任何 `INSERT/UPDATE/DELETE`

3. **Docker entrypoint.sh 已预留**：文件中已有以下代码，实现 `manage.py` 的对应函数即可生效：
   ```bash
   python manage.py start_webserver
   python manage.py webserver_autofix
   ```

4. **前端单文件原则**：`webserver/static/index.html` 是唯一前端文件，不要创建额外的 `.js`、`.css` 文件，CDN 资源通过 `<script src>` 引入

5. **数据库路径**：从 `config.yaml` 读取 `storage.local.data_dir`（默认 `output`），拼接 `news/YYYY-MM-DD.db` 或 `rss/YYYY-MM-DD.db`

6. **数据库表结构速查**：
   - `news DB`: `platforms`, `news_items`, `rank_history`, `crawl_records`, `crawl_source_status`, `period_executions`
   - `rss DB`: `rss_feeds`, `rss_items`, `rss_crawl_records`, `rss_crawl_status`

7. **配置文件路径**：从环境变量 `CONFIG_PATH` 读取（默认 `config/config.yaml`），其他文件相对于 config 目录

8. **并发保护**：`process_runner.py` 需要用 `asyncio.Lock()` 保证同时只有一个子进程在运行

---

## 附录 A：SQLite 完整表结构

### news DB (`output/news/YYYY-MM-DD.db`)

```sql
-- 平台信息
CREATE TABLE platforms (
    id TEXT PRIMARY KEY,
    name TEXT,
    is_active INTEGER,
    updated_at TIMESTAMP
);

-- 新闻条目
CREATE TABLE news_items (
    id INTEGER PRIMARY KEY,
    title TEXT,
    platform_id TEXT REFERENCES platforms(id),
    rank INTEGER,
    url TEXT,
    mobile_url TEXT,
    first_crawl_time TEXT,
    last_crawl_time TEXT,
    crawl_count INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 排名历史（每次采集记录排名变化）
CREATE TABLE rank_history (
    id INTEGER PRIMARY KEY,
    news_item_id INTEGER REFERENCES news_items(id),
    rank INTEGER,
    crawl_time TEXT,
    created_at TIMESTAMP
);

-- 采集批次记录
CREATE TABLE crawl_records (
    id INTEGER PRIMARY KEY,
    crawl_time TEXT UNIQUE,
    total_items INTEGER,
    created_at TIMESTAMP
);

-- 各平台采集状态
CREATE TABLE crawl_source_status (
    crawl_record_id INTEGER REFERENCES crawl_records(id),
    platform_id TEXT REFERENCES platforms(id),
    status TEXT,  -- 'success' | 'failed'
    PRIMARY KEY (crawl_record_id, platform_id)
);

-- 调度执行记录
CREATE TABLE period_executions (
    id INTEGER PRIMARY KEY,
    execution_date TEXT,   -- YYYY-MM-DD
    period_key TEXT,
    action TEXT,
    executed_at TIMESTAMP,
    UNIQUE(execution_date, period_key, action)
);
```

### rss DB (`output/rss/YYYY-MM-DD.db`)

```sql
-- RSS 订阅源
CREATE TABLE rss_feeds (
    id TEXT PRIMARY KEY,
    name TEXT,
    feed_url TEXT,
    is_active INTEGER,
    last_fetch_time TEXT,
    last_fetch_status TEXT,
    item_count INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- RSS 文章条目
CREATE TABLE rss_items (
    id INTEGER PRIMARY KEY,
    title TEXT,
    feed_id TEXT REFERENCES rss_feeds(id),
    url TEXT,
    published_at TEXT,
    summary TEXT,
    author TEXT,
    first_crawl_time TEXT,
    last_crawl_time TEXT,
    crawl_count INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- RSS 采集批次
CREATE TABLE rss_crawl_records (
    id INTEGER PRIMARY KEY,
    crawl_time TEXT UNIQUE,
    total_items INTEGER,
    created_at TIMESTAMP
);

-- RSS 各源采集状态
CREATE TABLE rss_crawl_status (
    crawl_record_id INTEGER REFERENCES rss_crawl_records(id),
    feed_id TEXT REFERENCES rss_feeds(id),
    status TEXT,
    error_message TEXT,
    PRIMARY KEY (crawl_record_id, feed_id)
);
```

---

## 附录 B：环境变量参考

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `WEBSERVER_HOST` | `0.0.0.0` | 监听地址 |
| `WEBSERVER_PORT` | `8080` | 监听端口 |
| `ADMIN_TOKEN` | 无 | 访问 Token（不设则不启用认证） |
| `CONFIG_PATH` | `config/config.yaml` | 主配置文件路径 |
| `ENABLE_WEBSERVER` | `false` | Docker 中是否启动 Web 服务 |
| `WEBSERVER_WATCHDOG` | `false` | 是否启用 Watchdog 自动重启 |
| `WATCHDOG_INTERVAL` | `60` | Watchdog 检查间隔（秒） |
