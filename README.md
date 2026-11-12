# 跨境电商 AI 视觉生产平台

V4计划实施中的私有图片工作台：FastAPI/Worker、PostgreSQL、RabbitMQ、S3与React/Konva。当前仅启用离线假供应商，未达到完整OFFLINE_READY验收；真实模型、商业发布均未进行。

已可操作：私有登录、产品与外观、真实原图上传、矩形像素保护与目标平移、报价/任务、进度与历史、PNG/报告下载、积分流水。平台证据未验证时保持人工复核，不保证商城上架。

## 安装与本地运行

Python 3.13–3.14、Node 24、pnpm 11.25、独立PostgreSQL 17、RabbitMQ 4和私有S3服务。

```text
uv sync --locked
pnpm --dir apps/web install --frozen-lockfile
```

设置MIGRATION_DATABASE_URL（专属空实例的DDL角色）、S3_ENDPOINT/S3_ACCESS_KEY/S3_SECRET_KEY/S3_BUCKET、AMQP_URL，再执行：

```text
uv run python scripts/setup_local.py --demo-account
```

该命令迁移并创建6个独立非owner LOGIN（含只读权限组）、JWT密钥、S3 CORS和本地体验账号；不安装系统服务。角色为集群级，不要对日常业务实例运行。秘密只写被忽略的.local目录；账号在.local/account.json，不应上传。已有profile不会覆盖。

分别在四个终端启动：

```text
uv run python scripts/run_local.py api
uv run python scripts/run_local.py publisher
uv run python scripts/run_local.py worker
uv run python scripts/run_local.py web
```

打开http://127.0.0.1:5173。默认本地HTTP profile仅允许loopback；其他环境应配置HTTPS安全Cookie。当前没有一键托管发布或充值功能。

## 验证

```text
uv run python scripts/check.py unit
uv run python scripts/check.py integration
pnpm --dir apps/web build
# 停止开发web进程；另一个终端启动生产预览，再执行浏览器验收
uv run python scripts/run_local.py preview
# 另一个终端
pnpm --dir apps/web e2e
```

原生集成需要TEST_DATABASE_URL，以及TEST_S3_ENDPOINT/TEST_S3_ACCESS_KEY/TEST_S3_SECRET_KEY/TEST_S3_BUCKET和TEST_AMQP_URL，必须使用可建测试角色的隔离实例。E2E需要API/publisher/worker和5173生产预览、.local/runtime.json与Chrome；测试自动创建隔离账号，不复用体验账号。不能让开发web与preview同时占用5173。可用PLAYWRIGHT_CHANNEL指定另一个已安装的Playwright浏览器。没有配置的集成会明确skip，不能作验收证据。测试不调用真实付费模型。

实际状态和缺口见docs/STATUS.md；运维细节见docs/RUNBOOK.md；V4规格保留在docs/specification。


单独重跑生产性能基准：`pnpm --dir apps/web exec playwright test performance.spec.ts`。包含4MP合成原图、双画布50个绘制对象（2图像+24矩形+24标签）、60秒真实指针缩放/平移/区域拖动，以及20并发500次已登录只读API请求。完整原始样本与设备记录写入docs/evidence/performance-production.json，目标为帧间隔p95<33ms、API p95<500ms，失败请求也计入分位数。此基准不代表真实商品视觉质量或生产集群容量。


API健康检查、只读权限与新实例验证见[docs/READINESS_AND_ROLES.md](docs/READINESS_AND_ROLES.md)。原生PG角色专项入口：`python scripts/check.py task P1-02`；尚未实现的其他task/all入口会明确NOT_RUN。


受控故障浏览器配置与单任务Fake CLI见[docs/CONTROLLED_BROWSER.md](docs/CONTROLLED_BROWSER.md)。普通e2e和受控配置分别验收；后者要求显式离线标记并暂停本项目publisher/consumer，完成后恢复。


原生同步快照备份、独立PG/S3恢复、会话撤销及未结束任务隔离见[docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md)。归档和私有profile只保存在忽略目录，Git中仅包含脱敏结果；生产RPO/RTO目标尚未设定。

只读聚合监控、常驻进程心跳与告警模板见[docs/MONITORING.md](docs/MONITORING.md)。`python scripts/run_local.py monitor`同时探测本机MQ/S3；尚未部署告警采集与通知服务。
