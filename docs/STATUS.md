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

## 2026-11-13：报价与任务API阶段

0007加入平台规则表、不可改报价内容、固定服务端trial-fake-v1/16积分报价函数，以及绑定业务输入hash的新任务入口；旧未绑定报价输入的函数已撤销app_api执行权。报价快照固定源版本hash/尺寸、外观版本和规则证据；无证据保持unverified。

已接通quote、task创建/查询/分页/取消、规则查询与外观版本更新API。当前task结果字段仍为空，等待Worker和归档模块接入，不代表已生成。

13项单元测试通过；21项原生PG集成通过。新增HTTP 20并发同键仅一创建、两个报价抢一单余额、过期报价重放已有任务、报价不可改、外观修改不影响快照、像素尺寸拒绝、归档拒绝报价，以及outbox写失败时任务/钱包/报价/冻结全部回滚。完整日志：docs/evidence/quote-task-pg-20261113.log。故障注入仅由隔离测试owner执行。

下一步补upload/cost/compliance实体、Worker领取与fencing、结算/退款受控函数；真实MQ/S3与前端仍未验收。

## 2026-11-13：Worker状态与结算数据库阶段

0008–0011补齐upload intents、cost records、compliance/reviews和只追加provider receipts；原图版本/报告/复核/费用均有不可改触发器及归属外键。新增可信dispatch领取、60秒租约续期、fencing、一次intent、晚到receipt追加与当前租约应用、生成/最终资产登记、报告绑定、成功结算、明确失败退款及unknown冻结函数。当前状态函数仅授权app_worker；不能直接写业务表。

13项单元测试、26项原生PG集成测试通过，证据docs/evidence/worker-ledger-pg-20261113.log。新增并发领取唯一性、旧/NULL fencing拒绝、unknown租约恢复不重发、晚到receipt不允许旧worker推进、报告前禁止结算、manual_review成功交付、结算重放只charge一次、charge/refund竞争单终态。静态检查发现NULL token比较可能绕过，已用IS DISTINCT FROM和0011前向修复；未解决attempt的明确退款被数据库拒绝。

这些测试为真实PostgreSQL状态/财务验证，资产元数据由测试fixture登记，**没有真实S3归档、MQ投递、模型生成或完整Worker进程证据**。任务查询现在返回已成功结果摘要和只读报告。下一步接入真实S3上传及Worker进程，随后MQ与浏览器；仍未达到OFFLINE_READY。

## 2026-11-13：真实S3上传与隔离解码阶段

0012增加上传意图、校验租约、双版本归档及释放函数；实现S3预签名PUT/GET、条件不可覆盖写入、读取后hash验证、私有资产/版本查询及下载。完成接口在短事务之外读取S3与解码；解码子进程限制768MiB、10秒CPU/12秒墙钟，整个完成流程20秒，最多2个并行校验；子进程不继承DB/S3秘密环境。

原生SeaweedFS 4.53在本任务work目录运行，S3端口18333，所有监听均127.0.0.1，随机密钥仅存work，不进Git。首次volume.max=3导致bucket不能分配volume，已调整隔离实例为16后真实复测通过。

15项单元测试通过（含EXIF1..8与ICC/调色板透明）；原生PG+S3完整集成33项通过，另新增并发complete专项1项通过。证据docs/evidence/pg-s3-upload-20261113.log、s3-concurrent-complete-20261113.log。验证了原始字节与标准化PNG两版本、重复/并发完成仅两版本、EXIF清除/旋转、透明白底一致、动画及MIME伪造拒绝、已知他人资源404、匿名S3读取403、不可变对象条件写入保持原字节。

未运行浏览器跨域上传；S3 CORS和完整本地初始化脚本待接线。Worker/MQ尚未把真实上传接成完整任务，不能标OFFLINE_READY。下一步实现fake Worker真实生成/回贴/检测/归档/结算与MQ投递。
