# 跨境电商 AI 视觉生产平台

基于V4计划的私有图片工作台：FastAPI/Worker、PostgreSQL、RabbitMQ、私有S3、React/Konva。已验证的离线MVP包含私有登录、产品与外观配置、真实原图上传、保护区域平移、报价/任务、进度与历史、PNG/报告下载、积分账本，以及独立备份恢复和故障演练。规则证据不足时保持人工复核，不保证商城上架。

最新完整已验基线为[ed6b11be / CI43627774746](https://github.com/wei-boop312/-AI-/actions/runs/43627774746)：209单元、91离线协议契约、261原生PG/MQ/S3测试、4普通+11受控浏览器、完整8服务Compose、独立冷恢复与离线门槛通过。1621文件交付包sidecar及本机独立复验通过。包括私有回执归档、受限恢复摘要、显式百炼运行身份/分币种预算、价格证据与异步查询后费用估算；真实供应商仍仅由MockTransport替代。后续百炼非空查询与保护图冷恢复候选须看自身CI，不能外推。详见[状态](docs/STATUS.md)、[任务状态](docs/TASK_STATUS.md)和[原始证据](docs/evidence)。

**当前运行模式仍是offline Fake。百炼图片编辑和Hubway/Gemini检测已有离线适配与Worker演练，尚未真实接通；完整V4、真实供应商验收和生产发布均未完成。** 本机百炼密钥配置见[BAILIAN_SETUP](docs/BAILIAN_SETUP.md)，剩余条件见[REMAINING_WORK](docs/REMAINING_WORK.md)。

## 安装与本地运行

需要Python 3.13–3.14、Node 24、pnpm 11.25，以及独立PostgreSQL 17、RabbitMQ 4和私有S3服务。

```text
uv sync --locked
pnpm --dir apps/web install --frozen-lockfile
```

在隔离的本机环境配置MIGRATION_DATABASE_URL（专属DDL角色）、S3_ENDPOINT/S3_ACCESS_KEY/S3_SECRET_KEY/S3_BUCKET及AMQP_URL，然后执行：

```text
uv run python scripts/setup_local.py --demo-account
```

该命令迁移新实例，创建6个独立非owner LOGIN、JWT密钥、S3 CORS和体验账号；角色为集群级，仅用于专属测试实例。私有profile与账号写入被忽略的.local目录，已有profile不会覆盖。项目不包含公开注册、充值或用户配置模型密钥功能。

四个终端分别启动：

```text
uv run python scripts/run_local.py api
uv run python scripts/run_local.py publisher
uv run python scripts/run_local.py worker
uv run python scripts/run_local.py web
```

打开http://127.0.0.1:5173。本机HTTP profile仅用于loopback；其他环境需配置HTTPS安全Cookie。不要同时运行dev web和production preview占用同一端口。Docker独立基础服务及完整应用Compose说明见[COMPOSE](docs/COMPOSE.md)，不是托管发布。

## 验证

始终离线的单元与协议契约：

```text
uv run python scripts/check.py unit
uv run python scripts/check.py task P4-01 --profile offline
uv run python scripts/check.py task P4-02 --profile offline
pnpm --dir apps/web build
```

原生集成需要隔离的TEST_DATABASE_URL，以及TEST_S3_ENDPOINT/TEST_S3_ACCESS_KEY/TEST_S3_SECRET_KEY/TEST_S3_BUCKET/TEST_S3_REGION和TEST_AMQP_URL。缺依赖不能以skip作为验收证据。

```text
uv run python scripts/check.py integration
```

生产浏览器要求API/publisher/worker、.local/runtime.json和Chrome；停止本项目dev web后另一个终端启动preview，再运行e2e。测试创建隔离账号，不复用体验账号。

```text
uv run python scripts/run_local.py preview
pnpm --dir apps/web e2e
```

完整离线门槛是Linux CI下当前提交的原生、构建、生产浏览器、Compose、恢复和运行指标证据组合，不会隐式启动缺少的服务，也不会访问真实付费供应商：

```text
uv run python scripts/check.py all --profile offline
uv run python scripts/check.py task P5-02
```

逐任务命令与合并实现映射见[ACCEPTANCE](docs/ACCEPTANCE.md)。真实模型P4-03和发布P5-03保留独立门槛；不能用离线成功标记PROVIDER_VERIFIED或商业发布就绪。

生产性能基准见[性能验收说明](docs/ACCEPTANCE.md)：4MP、双画布50绘制对象、60秒真实指针、20并发500次非模型API。只证明所属CI环境，不代表生产容量或真实视觉质量。

## Hubway 与运营

用户指定检测供应商候选为Hubway，默认https://hubway.cc、可显式选择https://z.hubway.cc，已在登录网站确认gemini-3.8-flash。实际密钥仅放私有服务端环境；.env.example中为空。设置环境变量不会自动将普通Worker切到付费模式。

[Hubway接入与冻结路由](docs/HUBWAY_INTEGRATION.md)区分SDK MockTransport证明和真实服务端兼容性。FLUX图片编辑API尚未在Hubway核实，不能拿聊天文本接口冒充图像生成。费用、授权及未知结果处理见[PROVIDER_BUDGET](docs/PROVIDER_BUDGET.md)。

API/Cookie/CSRF与幂等使用见[API_USAGE](docs/API_USAGE.md)；角色/健康见[READINESS_AND_ROLES](docs/READINESS_AND_ROLES.md)；产品与外观管理见[PRODUCT_MANAGEMENT](docs/PRODUCT_MANAGEMENT.md)、[APPEARANCE_EXECUTION](docs/APPEARANCE_EXECUTION.md)。

备份与独立恢复见[BACKUP_RESTORE](docs/BACKUP_RESTORE.md)。原计划初始演练目标是RPO24h/RTO4h，已有对应CI演练证明；生产备份调度、保留策略和SLA仍需目标环境验证。监控及故障处理见[MONITORING](docs/MONITORING.md)、[RUNBOOK](docs/RUNBOOK.md)；锁文件、SBOM与实际许可文本见[SUPPLY_CHAIN](docs/SUPPLY_CHAIN.md)。原始12份规范保留在[specification](docs/specification)，不覆盖或改写。

检测不可用时按证据交付既有成品、保留供应商未知费用的受限运营候选见[ADR_DETECTION_MANUAL_DELIVERY](docs/ADR_DETECTION_MANUAL_DELIVERY.md)，该分支已在上述CI整轮通过，未证明真实供应商检测或费用。


完整离线CI通过后会生成准确源码/当次前端/原始证据/实际许可文本的ZIP交付包；下载与独立校验方法见[离线交付包](docs/HANDOFF.md)。真实供应商与生产发布按各自门槛另行验收。
