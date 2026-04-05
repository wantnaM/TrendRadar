# TrendRadar — 热点趋势雷达

## 项目概述

TrendRadar 是一个多平台热点新闻聚合 + AI 智能分析 + 多渠道推送平台。从 11+ 热榜平台和 RSS 源采集数据，通过关键词或 AI 进行过滤分析，生成情报报告，并推送到 8+ 通知渠道。同时提供 MCP Server 供 AI 客户端接入。

- **主版本**: 6.6.0 (trendradar) | **MCP**: 4.0.2 | **Python**: >=3.12
- **包管理**: uv + hatchling
- **入口点**: `trendradar.__main__:main` (CLI) | `mcp_server.server:run_server` (MCP)

## 项目结构

```
TrendRadar/
├── trendradar/                  # 核心应用
│   ├── __main__.py              # CLI 入口，编排采集→分析→推送全流程
│   ├── context.py               # AppContext 中央协调器，封装所有配置相关操作
│   ├── core/                    # 核心逻辑
│   │   ├── loader.py            #   YAML + ENV 配置加载
│   │   ├── analyzer.py          #   权重算法: rank(0.6) + frequency(0.3) + hotness(0.1)
│   │   ├── frequency.py         #   关键词组加载、正则匹配、全局过滤
│   │   ├── scheduler.py         #   Scheduler 时间线调度 (预设 + 自定义)
│   │   ├── data.py              #   当日数据读取、增量检测
│   │   └── config.py            #   多账号配置解析与验证
│   ├── crawler/                 # 数据采集
│   │   ├── fetcher.py           #   DataFetcher: NewsNow API, 11 平台, 重试
│   │   └── rss/                 #   RSS 采集
│   │       ├── fetcher.py       #     RSSFetcher: 多格式, 新鲜度过滤, 限速
│   │       └── parser.py        #     RSSParser: RSS 2.0 / Atom / JSON Feed
│   ├── ai/                      # AI 引擎 (LiteLLM → 100+ 模型提供商)
│   │   ├── client.py            #   AIClient: LiteLLM completion() 统一接口
│   │   ├── analyzer.py          #   AIAnalyzer: 5 维度深度情报分析
│   │   ├── filter.py            #   AIFilter: 2 阶段兴趣过滤 (标签提取→批量分类)
│   │   ├── translator.py        #   AITranslator: 单条/批量翻译
│   │   ├── formatter.py         #   AI 结果多平台渲染器
│   │   └── prompt_loader.py     #   Prompt 模板加载器
│   ├── notification/            # 通知分发 (8 渠道)
│   │   ├── dispatcher.py        #   NotificationDispatcher: 统一分发, 多账号
│   │   ├── renderer.py          #   飞书卡片 / 钉钉卡片 / 合并渲染
│   │   ├── splitter.py          #   智能分片 (平台字节限制 → 行边界拆分)
│   │   ├── senders.py           #   8 渠道发送: 飞书/钉钉/企微/TG/Email/ntfy/Bark/Slack
│   │   ├── batch.py             #   批次编号 + 字节截断
│   │   └── formatters.py        #   Markdown→纯文本, Slack mrkdwn 转换
│   ├── report/                  # 报告生成
│   │   ├── generator.py         #   数据重构 + HTML 文件生成
│   │   ├── html.py              #   响应式 HTML5 多区域渲染
│   │   ├── rss_html.py          #   RSS 专用 HTML 渲染
│   │   ├── formatter.py         #   平台标题适配 (排名图标/emoji/时间戳)
│   │   └── helpers.py           #   清洗 + HTML 转义 + 排名展示
│   ├── storage/                 # 多后端存储
│   │   ├── base.py              #   抽象基类 + 数据模型 (NewsItem/RSSItem)
│   │   ├── manager.py           #   StorageManager: 环境检测 + 后端路由
│   │   ├── local.py             #   LocalStorageBackend: SQLite + TXT/HTML
│   │   ├── remote.py            #   RemoteStorageBackend: S3/R2/OSS/COS
│   │   └── sqlite_mixin.py     #   共享 SQLite 逻辑
│   └── utils/                   # 工具函数
│       ├── time.py              #   时区感知时间函数
│       └── url.py               #   URL 归一化 (去跟踪参数, 去重)
├── mcp_server/                  # MCP 服务 (FastMCP 2.0, 26 Tools)
│   ├── server.py                # 主服务器: 注册 tools + resources
│   ├── services/                # 服务层
│   │   ├── data_service.py      #   DataService: 数据查询与统计
│   │   ├── cache_service.py     #   CacheService: TTL 内存缓存 (15min)
│   │   └── parser_service.py    #   ParserService: SQLite 数据解析
│   ├── tools/                   # 工具层 (8 模块, 26 工具)
│   │   ├── data_query.py        #   数据查询 (5 tools)
│   │   ├── analytics.py         #   高级分析 (7 tools)
│   │   ├── search_tools.py      #   统一搜索 (1 tool, 3 模式)
│   │   ├── config_mgmt.py       #   配置查询 (1 tool)
│   │   ├── system.py            #   系统管理 (3 tools)
│   │   ├── storage_sync.py      #   存储同步 (3 tools)
│   │   ├── article_reader.py    #   文章阅读 (2 tools, Jina API)
│   │   └── notification.py      #   通知发送 (2 tools)
│   └── utils/                   # MCP 工具函数
│       ├── errors.py            #   MCPError 异常体系
│       ├── validators.py        #   参数验证与解析
│       └── date_parser.py       #   自然语言日期解析 (中英文)
├── config/                      # 配置文件
│   ├── config.yaml              #   主配置 (v2.2.0, 11 板块)
│   ├── timeline.yaml            #   调度配置 (v1.2.0, 5 预设)
│   ├── frequency_words.txt      #   关键词过滤 (v1.1.0, 分组+正则)
│   ├── ai_interests.txt         #   AI 兴趣分类 (v1.1.0, 14 类目)
│   ├── ai_analysis_prompt.txt   #   AI 分析提示词 (v2.0.0, OSINT 框架)
│   ├── ai_translation_prompt.txt#   AI 翻译提示词 (v1.2.0)
│   ├── ai_filter/               #   AI 过滤提示词 (extract/classify/update)
│   └── custom/                  #   自定义配置 (ai/ + keyword/)
├── docker/                      # Docker 部署
│   ├── Dockerfile               #   多架构镜像 (python:3.12-slim + supercronic)
│   ├── docker-compose.yml       #   两个服务: trendradar + trendradar-mcp
│   ├── entrypoint.sh            #   启动脚本 (cron/once 模式 + Web 服务器)
│   └── .env                     #   环境变量模板
├── output/                      # 数据输出
│   ├── news/                    #   热榜数据 (YYYY-MM-DD.db)
│   └── rss/                     #   RSS 数据 (YYYY-MM-DD.db)
├── pyproject.toml               # 项目元数据 + 依赖
├── requirements.txt             # pip 依赖 (备选)
├── uv.lock                      # uv 锁文件
├── version                      # 主版本号
├── version_mcp                  # MCP 版本号
└── version_configs              # 配置文件版本映射
```

## 核心数据流

```
定时触发 (Cron/Scheduler)
  → 数据采集 (DataFetcher: 11 热榜 + RSSFetcher: RSS 源)
  → 数据存储 (SQLite: output/news/*.db, output/rss/*.db)
  → 数据分析 (权重计算 + 关键词匹配 或 AI 过滤)
  → AI 分析 (可选: AIAnalyzer 5 维度情报分析)
  → AI 翻译 (可选: AITranslator 多语言)
  → 报告生成 (HTML / Markdown / 飞书卡片 / 钉钉 等多格式)
  → 消息推送 (8 渠道并发: 飞书/钉钉/企微/TG/Email/ntfy/Bark/Slack)
```

## 关键架构模式

- **AppContext 模式**: `context.py` 是中央协调器，封装所有配置依赖操作（时间、存储、调度、AI、通知）
- **Scheduler 调度**: `timeline.yaml` 定义 Periods → Day Plans → Week Map，支持 5 种预设和自定义
- **StorageManager 路由**: 自动检测环境（GitHub Actions / Docker / 本地），路由到 local/remote 后端
- **LiteLLM 统一接口**: `ai/client.py` 通过 LiteLLM 支持 100+ AI 模型提供商
- **多账号多渠道**: 通知支持分号分隔的多账号配置，自动分片适配平台字节限制
- **MCP 分层**: FastMCP Server → Tools (8 模块) → Services (3 服务) → TrendRadar Core

## 开发指南

### 运行命令

```bash
# 安装依赖
uv sync

# 运行主程序
uv run trendradar

# 启动 MCP Server (HTTP)
uv run python -m mcp_server.server --transport http --host 0.0.0.0 --port 3333

# Docker 部署
cd docker && docker compose up -d
```

### 代码风格

- Python 3.12+，使用类型提示
- 日志使用 `logging` 模块，通过 DEBUG 环境变量控制级别
- 配置优先级: 环境变量 > YAML 文件 > 默认值
- 敏感信息（API Key、Webhook URL）必须通过环境变量或 GitHub Secrets 传入，不写入配置文件
- MCP 工具返回统一 JSON 结构: `{ success, data, error: { code, message, suggestion } }`
- 使用 `tenacity` 进行重试，`json-repair` 修复 AI 返回的损坏 JSON

### 配置修改注意事项

- 修改 `config.yaml` 结构时同步更新 `version_configs` 中的版本号
- 修改 `timeline.yaml` 预设时注意跨午夜时段和冲突检测逻辑
- `frequency_words.txt` 语法: `[组名]` 定义组，`/regex/ => 别名` 定义正则，`+` 必选，`!` 排除，`@N` 限制显示数
- AI 提示词修改后需测试 JSON 输出格式是否仍可被 `json-repair` 解析

### 新增通知渠道

1. 在 `notification/senders.py` 添加 `send_to_xxx()` 函数
2. 在 `notification/dispatcher.py` 注册新渠道
3. 在 `notification/renderer.py` 添加格式化逻辑（如需特殊格式）
4. 在 `notification/splitter.py` 配置字节限制
5. 在 `config.yaml` 添加配置项，在 `core/loader.py` 添加加载逻辑

### 新增 MCP 工具

1. 在 `mcp_server/tools/` 对应模块中添加工具类和方法
2. 在 `mcp_server/server.py` 中注册工具
3. 工具必须返回结构化 JSON，使用 `utils/validators.py` 验证参数
4. 错误使用 `utils/errors.py` 中的异常类

### 存储结构

- **SQLite 按日分库**: `output/news/YYYY-MM-DD.db` (news 表)，`output/rss/YYYY-MM-DD.db` (rss 表)
- **远程同步**: StorageManager 可将本地 DB 镜像到 S3 兼容存储 (R2/OSS/COS/AWS)
- **数据模型**: `NewsItem`（title, source_id, ranks[], timestamps, counts）, `RSSItem`（title, feed_id, url, published_at, summary）

## 避免的事项

- 不要直接修改 `.venv/`、`.git/`、`__pycache__/` 中的内容
- 不要在代码中硬编码 API Key 或 Webhook URL
- 不要跳过 `AppContext` 直接调用底层模块（会缺少配置注入）
- 不要在 MCP 工具中使用同步阻塞调用（所有工具需 async 兼容）
- 修改权重算法 (`core/analyzer.py`) 时注意 MCP 的 `analytics.py` 也引用了该逻辑
