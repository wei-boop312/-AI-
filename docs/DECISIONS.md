# ADR 001
采用 V4 Python/FastAPI、React/Konva、PostgreSQL、RabbitMQ、S3 路线。当前只构建离线领域内核，不以进程内钱包替代生产数据库账务。未复制旧项目源码，避免继承许可与已知缺陷。精确模式仅等尺寸平移；未知供应商提交禁止重发。SeaweedFS 服务配置待环境核验。

## ADR 002：原生数据库验证
缺Docker时采用EDB PostgreSQL 17.11 Windows二进制，在任务work目录初始化隔离实例，只监听127.0.0.1:55432，SCRAM随机密码。来源：https://www.enterprisedb.com/download-postgresql-binaries 。此证据属于真实PostgreSQL，不代表RabbitMQ/S3集成或生产部署。数据库角色为集群级，迁移必须在专属实例执行。
