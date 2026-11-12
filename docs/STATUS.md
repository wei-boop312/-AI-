# 实施状态

2026-11-12；当前为开发阶段，未达到 OFFLINE_READY。

## 已实现并验证

- 隔离工程、规格归档、来源哈希、Python虚拟环境及uv.lock。
- 严格请求schema、规范化业务哈希、RGB精确矩形回贴、图像标准化、保守规则、假供应商防重复提交。
- Argon2密码及固定RS256令牌模块；refresh仅生成与摘要，持久会话轮换尚未接入。
- Alembic 0001–0004：产品/外观/资产/版本/认证/钱包、quote/task/账本/events/outbox/dispatch/audit/provider attempt。
- NOBYPASSRLS权限组、租户RLS、复合外键、不可变账本；受控授额、原子任务创建/冻结及取消退款函数。
- 13项单元测试通过；原生PostgreSQL 17.11上6项集成测试通过，包括20并发同键只创建1任务/冻结/outbox、幂等冲突、跨用户外键、RLS、API不可写余额/账本/凭据及不可切换executor角色、取消仅退款一次。

## 证据与已发现问题

- docs/evidence/native-pg-20261112.log。数据库运行在本任务work/pg-data，127.0.0.1:55432；随机密码不进仓库。
- 真实迁移发现`:queued`被SQLAlchemy误识别为参数，已转义；真实锁检查发现缺少列权限，0004补充UPDATE(archived_at)给不可登录executor。目录测试排除索引。
- uv sync --locked、compileall和离线Alembic生成通过。基线首次缺迁移URL被拒属于预期保护。

## 未完成与下一步

P0-02/P0-03/P1整体均未全部验收。尚缺upload/rules/cost/compliance实体、数据库结算与fencing、完整认证与会话、API业务路由、S3/MQ/worker/前端及浏览器验收。
真实PG已可用；RabbitMQ/S3尚未运行。测试角色采用SET SESSION AUTHORIZATION模拟真实权限，服务LOGIN凭据及连接池隔离仍待验证。
没有付费模型调用、部署或用户数据迁移。不能称PROVIDER_VERIFIED/RELEASE_READY。
下一步：剩余实体与结算函数，连接池隔离，认证会话及CLI。

## GitHub与额度

origin/master已连接，阶段成果持续推送。周额度阶段起始剩余96%；每阶段复查，剩余<=20%按用户要求停止。

## 2026-11-13：认证与业务API阶段

新增0005会话族/登录限流，0006私有账号受控创建；完整接入登录、me、refresh轮换、重放撤销、logout、停用检查、Origin/CSRF、安全Cookie。产品创建/列表/详情/版本更新/归档、外观创建与列表、余额及流水API已接数据库。appearance更新仍待补齐。

连接池使用独立真实LOGIN并检查非superuser/非owner/NOBYPASSRLS。15项原生PG集成通过（包括API及并发连接池异常/取消后上下文清理）；13项单元测试通过。证据：docs/evidence/auth-pool-pg-20261113.log。私有账号与授额CLI已实现，尚未用完整终端流程验收。0006初次测试发现POLICY语句顺序问题，已在未发布迁移中修正并真实执行通过。

下一步：quote/task API与快照一致性、剩余实体/结算/fencing、上传存储及Worker。仍未达到OFFLINE_READY，MQ/S3/前端未验收。
