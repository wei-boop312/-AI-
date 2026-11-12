# 本地开发与私有账号

安装依赖：`uv sync --locked`。迁移只对专属PostgreSQL实例运行：设置MIGRATION_DATABASE_URL后执行`uv run python scripts/dev.py migrate`。迁移会创建集群级NOLOGIN权限组；不要在用户现有业务实例运行。

分别创建非超级用户、非owner、NOBYPASSRLS的LOGIN账号，仅授app_api、app_auth或ops_admin中一个权限组。API和认证连接池启动时拒绝超级用户及对象owner。

设置API_DATABASE_URL、AUTH_DATABASE_URL、JWT_PRIVATE_KEY_FILE、JWT_PUBLIC_KEY_FILE、APP_ORIGIN与COOKIE_SECURE。API启动：`uv run uvicorn visual_platform.api.main:app --app-dir src --host 127.0.0.1`。HTTP仅允许显式本机origin配COOKIE_SECURE=0，其余使用HTTPS和安全Cookie。

设置ADMIN_DATABASE_URL后创建私有用户：`uv run python scripts/dev.py create-user --email user@example.com --credits 100`。密码通过隐藏终端输入并确认，不写命令历史。授额：`uv run python scripts/dev.py grant --user-id UUID --amount 100 --operation-id UUID --reason "test credits"`。重试使用同operation-id。CLI必须使用ops_admin专用LOGIN，不能使用超级用户。

登录POST /api/v1/auth/login需要精确Origin，其他写请求还需要visual_csrf Cookie对应的X-CSRF-Token头。HttpOnly的access/refresh Cookie不会暴露给脚本。refresh轮换一次；旧refresh重放会提交会话族撤销，旧access也随即失效。退出/账号停用同样使访问令牌失效。

测试：`uv run python scripts/check.py unit`。原生PG测试需在已迁移的独立测试实例设置TEST_DATABASE_URL（专用测试owner，允许创建测试LOGIN），再运行`uv run python scripts/check.py integration`。集成测试会建立随机账号和角色，不能连接生产数据库。该入口已覆盖真实PG/MQ/S3用例，浏览器闭环另行在生产预览执行。

/health/ready检查有限API依赖（PG api/auth与S3），就绪200、不可用503；scope为api_dependencies，具有短超时、缓存和单轮并发探测。/health/live仅表示进程存活。MQ/Worker及供应商健康另行判断，不能由API就绪推导OFFLINE_READY。详见READINESS_AND_ROLES.md。

S3配置：S3_ENDPOINT、S3_ACCESS_KEY、S3_SECRET_KEY、S3_BUCKET（默认visual-private）、S3_REGION（默认us-east-1）。远程endpoint必须HTTPS，本机可HTTP。请提前创建私有bucket。原生S3测试另设TEST_S3_ENDPOINT/TEST_S3_ACCESS_KEY/TEST_S3_SECRET_KEY/TEST_S3_BUCKET；没有这些变量时S3用例会明确skip，不代表集成通过。临时解码文件在项目work目录并自动删除，已加入gitignore。

独立Worker单任务入口：设置WORKER_DATABASE_URL（仅app_worker权限组）、上述S3配置、PROVIDER_PROFILE=offline，执行`uv run python -m visual_platform.worker --task TASK_UUID`（PYTHONPATH=src）。FAKE_PROVIDER_DIR可设置持久fake结果目录，默认项目work/fake-provider。当前只支持offline，不应改成真实供应商或复用旧密钥。MQ消费入口见下文。Worker结果retryable表示仅可恢复安全步骤；uncertain/stopped需查看数据库状态和对账，不能新建同意图调用。

MQ入口：AMQP_URL（远程必须amqps，本机可amqp）、QUEUE_PREFIX（默认visual.v1）。设置DISPATCH_DATABASE_URL（仅ops_dispatcher权限组）后运行`uv run python -m visual_platform.events`，--once可单轮发布/恢复。Worker改用`uv run python -m visual_platform.worker --consume`长期消费。两进程仍需要PYTHONPATH=src，Worker还需S3/WORKER_DATABASE_URL/PROVIDER_PROFILE=offline。恢复超过5次进入QUEUE_PREFIX.manual供人工处理，不授权新付费调用。原生MQ测试额外设置TEST_AMQP_URL。

运营CLI（ADMIN_DATABASE_URL，仅ops_admin LOGIN）：

- `python scripts/admin.py inspect --task UUID`：读取对账所需任务/attempt/receipt摘要，不返回polling URL或凭据。
- `python scripts/admin.py review --task UUID --check UUID --reviewer USER_UUID --decision approved --reason "核验理由" --evidence-json refs.json --operation-id UUID`：refs.json为证据引用字符串数组，决定可approved/rejected/needs_review。自动报告不改写。
- `python scripts/admin.py accept-receipt --task UUID --attempt UUID --provider-id ID --response-digest SHA256 --reason "核验来源" --evidence-digest SHA256 --operation-id UUID`：只接纳人工核验的既有供应商回执，不发模型请求。
- `python scripts/admin.py reconcile --task UUID --action resume --receipt RECEIPT_UUID --reason "核验结论" --evidence-digest SHA256 --operation-id UUID`：只恢复已知回执；无回执不能resume。
- action=fail（不传receipt）为有记录的内部无法交付结案，释放用户冻结额度，不表示供应商费用已退款或已知。

操作重试必须复用原operation-id和同一payload。证据摘要仅是记录绑定，实际资料仍由运营者核验。Cookie注销/停用立即拒绝访问；人工通过结果标记human_review，与未核验自动规则分开展示。

浏览器验收会通过create_e2e_account.py在显式本机offline profile创建独立临时账号，使用work目录保存随机凭据；不再依赖共用demo账号。verify_browser_png.py独立校验下载文件与原图fixture的保护像素，结果保存在docs/evidence/browser-pixel-verification.json。


生产浏览器验收改用build后的5173 preview，不能同时运行同端口开发web。50对象/4MP/60秒与20并发500请求基准见docs/PERFORMANCE.md；只读性能测试不调用模型或创建任务。


只读视图、运行角色和隔离新实例初始化验证见docs/READINESS_AND_ROLES.md。新初始化会生成第6个只读LOGIN及READONLY_DATABASE_URL，既有profile不自动覆盖；--profile-dir仅允许.local或work内目录。


受控故障阶段使用scripts/run_fake_task.py --task UUID --mode failed/uncertain/late，只能针对本机offline profile，流程及恢复消费者要求见docs/CONTROLLED_BROWSER.md。unknown页面保持SSE，运营结案或晚到回执resume后自动更新；等待期间禁用同产品普通生成入口。
