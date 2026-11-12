# 本地开发与私有账号

安装依赖：`uv sync --locked`。迁移只对专属PostgreSQL实例运行：设置MIGRATION_DATABASE_URL后执行`uv run python scripts/dev.py migrate`。迁移会创建集群级NOLOGIN权限组；不要在用户现有业务实例运行。

分别创建非超级用户、非owner、NOBYPASSRLS的LOGIN账号，仅授app_api、app_auth或ops_admin中一个权限组。API和认证连接池启动时拒绝超级用户及对象owner。

设置API_DATABASE_URL、AUTH_DATABASE_URL、JWT_PRIVATE_KEY_FILE、JWT_PUBLIC_KEY_FILE、APP_ORIGIN与COOKIE_SECURE。API启动：`uv run uvicorn visual_platform.api.main:app --app-dir src --host 127.0.0.1`。HTTP仅允许显式本机origin配COOKIE_SECURE=0，其余使用HTTPS和安全Cookie。

设置ADMIN_DATABASE_URL后创建私有用户：`uv run python scripts/dev.py create-user --email user@example.com --credits 100`。密码通过隐藏终端输入并确认，不写命令历史。授额：`uv run python scripts/dev.py grant --user-id UUID --amount 100 --operation-id UUID --reason "test credits"`。重试使用同operation-id。CLI必须使用ops_admin专用LOGIN，不能使用超级用户。

登录POST /api/v1/auth/login需要精确Origin，其他写请求还需要visual_csrf Cookie对应的X-CSRF-Token头。HttpOnly的access/refresh Cookie不会暴露给脚本。refresh轮换一次；旧refresh重放会提交会话族撤销，旧access也随即失效。退出/账号停用同样使访问令牌失效。

测试：`uv run python scripts/check.py unit`。原生PG测试需在已迁移的独立测试实例设置TEST_DATABASE_URL（专用测试owner，允许创建测试LOGIN），再运行`uv run python scripts/check.py integration`。集成测试会建立随机账号和角色，不能连接生产数据库。该测试入口尚未覆盖MQ/S3/浏览器完整闭环。

/health/ready当前仍返回503，表示完整生产链路尚未就绪；/health/live只表示API进程存活。不会据此声称MVP可用。
