# 实施状态

当前摘要（2026-11-13）：提交 35694a4 的 CI 43323370220 首次完整全绿、综合门槛 OFFLINE_READY；包括49单元、39 mock契约、90原生集成、4+5生产浏览器、Compose迁移/持久化、两个非root镜像和供应链检查。P5-02另在9e8f247完成当前迁移恢复/重启/性能实测。新提交ec2a155加强实际容器任务闭环，正在CI，尚不把其新增要求称为通过。真实供应商、目标环境和发布待外部条件。逐任务现状见 [TASK_STATUS.md](TASK_STATUS.md)，入口与范围见 [ACCEPTANCE.md](ACCEPTANCE.md)。

以下是按时间追加的历史实施记录；早期“未接入/尚缺”描述只对应其记录阶段，最新结论见顶部摘要和末尾更新。

完整主计划复核还发现应用Compose、完整运行指标等具体要求超出早期综合门槛覆盖，详见[PLAN_GAPS.md](PLAN_GAPS.md)。早期门槛返回OFFLINE_READY只证明其实际检查范围，不能据此宣称完整V4已完成；继续补实现和证据。

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

## 2026-11-13：真实PG/S3离线Worker闭环

0013/0014加入Worker完整上下文、离线费用记录、持久阶段事件和安全释放租约。实现持久假供应商、受限进程回贴与保存后像素验证、严格视觉事实、阶段恢复Worker、20秒续租、只恢复查询/归档/本地处理、最终PNG与JSON报告私有下载。SSE支持持久游标重放/重置、授权复核、终态关闭，等待期间不占数据库连接。

18项单元测试通过；完整PG/S3集成39项通过，之后新增独立Worker CLI进程专项1项通过。证据：docs/evidence/worker-full-pg-s3-20261113.log、offline-worker-pg-s3-20261113.log、worker-process-pg-s3-20261113.log。实际完成真实上传→假生成→S3归档→平移回贴→最终图事实检测→未验证规则人工复核→报告存储→单次结算→PNG/报告下载，下载字节hash及保护区域RGB一致。

故障测试：归档失败后用新provider对象/连接池恢复，generate intent仍只有1；未知结果冻结且不重发；明确fake失败退款；恶意/错误结构事实不能自行判合规，交付manual_review。CLI专项确实运行独立Python进程；之前状态恢复测试是对象/连接池重建，不冒充强杀进程恢复。

尚未接入RabbitMQ confirm/ack/DLX与恢复扫描，也未完成中文React/Konva界面及浏览器验证；因此仍不能标OFFLINE_BACKEND_READY或OFFLINE_READY。下一步接MQ和本地启动脚本，再完成前端。

## 2026-11-13：原生RabbitMQ投递与恢复

0015/0016增加publisher租约token、持久恢复outbox、5次恢复上限和可信消息引用验证；取消同步dispatch状态。实现durable direct exchange/quorum queue、persistent message、publisher confirms、mandatory return、manual ACK、prefetch=2、DLX与人工quorum队列、数据库恢复扫描。新增独立publisher进程入口与Worker --consume入口。

RabbitMQ 4.4.0 / Erlang 29.1.2 ZIP在任务work内启动，未安装系统服务或改全局PATH；AMQP 127.0.0.1:5679、distribution 127.0.0.1:25679，EPMD仅loopback。密码及cookie只在work。初启遇到Erlang cookie位置和重复-home参数问题，采用显式随机cookie后启动；没有写用户home配置。

18项单元、47项真实PG/RabbitMQ/S3集成通过，完整证据docs/evidence/full-pg-rabbit-s3-20261113.log。覆盖并发publisher唯一claim、真实确认/持久消费完整生成闭环、确认丢失重复投递不重发/重扣、无路由时保留outbox、非法消息DLX、超过5次恢复入人工队列、完成事务后ACK丢失重投、ACK后归档失败由DB扫描恢复。人工队列首次测试发现内部dispatch UPDATE RLS使FOR UPDATE扫描为空，0016前向修复并复测。

离线后端关键链路已有真实服务证据，但尚缺完整运维/迁移干净实例和综合安全验收，未正式宣布阶段门槛。中文React/Konva、浏览器断线恢复/选区/对比尚未实现，仍非OFFLINE_READY。下一步完成本地初始化与前端。

## 2026-11-13：中文React/Konva工作台与浏览器闭环

新增React/TypeScript/Vite、Ant Design、Konva与Zustand及pnpm锁文件。页面连接真实API，实现登录、产品/外观创建、原图上传/重新校验、原图切换、缩放/平移/矩形框选、独立目标映射、整数目标坐标微调、报价确认、SSE/轮询代码、当前任务/历史、原图与成品对比、检查报告及积分流水。列表新增原图查询，任务返回固定源版本以保证历史对比使用正确原图。

setup_local.py在新的专属PG实例55433完成0001–0016迁移、独立服务LOGIN、JWT、S3私有bucket CORS及随机本地体验账号；run_local.py可启动API/publisher/worker/web。秘密.local及work均确认被Git忽略。

TypeScript和生产构建exit0；18项单元、47项PG/Rabbit/S3回归通过。真实Chrome E2E通过：登录→产品→跨域S3上传→Konva实际鼠标框选/目标拖动→数值定位→报价确认→MQ/Worker→报告→浏览器下载→390px手机无横向溢出，未捕获页面JS异常。缩小视口下指针按物理像素量化，测试按拖动起点验证位移误差≤一个显示像素，随后数值输入精确设定目标。下载文件另用Python核对DB文件hash和保护区RGB逐像素一致，证据browser-pixel-verification.json。

已视觉检查登录、画布与手机截图，截图与browser-e2e-20261113.log位于docs/evidence。生产bundle当前约1.46MB（gzip462KB），有antd use-client和chunk体积警告，尚待性能拆包。浏览器断线/refresh重放/多账号切换、完整复核与重算、干净部署/备份恢复、CI/SBOM/供应商适配仍未全部验收；未标OFFLINE_READY。

## 2026-11-13：人工复核、对账与客户端恢复

0017–0019增加只追加人工复核、受限运营回执接纳、unknown恢复/人工结案、操作编号幂等及审计。新增scripts/admin.py的inspect/review/accept-receipt/reconcile，仅专用ops_admin LOGIN可用。人工复核提供effective来源，原auto结果、报告hash及下载JSON保持不变；网页没有开放管理员写路由。晚到已知回执恢复原attempt查询，禁止重新generate；内部积分释放不冒称供应商退款。

真实测试暴露审计表WITH CHECK策略不提供SELECT，导致对账重放未读到历史；0019补充仅NOLOGIN执行角色的审计读取策略后复测通过。复核并发同operation只追加一次，旧终态回执不能被当成未知步骤恢复。

前端按用户/产品保存sessionStorage草稿和最后产品，恢复前校验服务端原图归属/版本/边界；账号变化先清空界面并等待新资料，异步旧请求不能回填主要列表。刷新恢复最近任务，源图比较绑定任务固定版本。SSE保留原生EventSource重连与Last-Event-ID语义，5秒故障转3秒轮询，Cookie过期通过refresh恢复。事件清理至空也发送reset。

18项单元、54项真实PG/Rabbit/S3集成通过。新增3个管理/对账测试和3个事件游标/清理重置测试；登录限流为每账号10次/15分钟、每IP100次/15分钟（避免共享IP跨账号误锁），负例已覆盖。证据reviews-events-full-20261113.log。

3个真实Chrome用例通过（browser-comprehensive-20261113.log）：完整指针生产流程+刷新草稿+下载独立像素验证；断网/轮询/恢复/丢失access Cookie后的refresh、CLI人工复核展示及同一页面账号切换隔离；产品A/B草稿隔离、刷新保留选择、编辑只访问本机且没有任务。各用例创建独立私有测试账号，密码不入日志或Git。仍需生产构建浏览器与50对象基准、重算规则/报告版本、运维恢复、CI及真实供应商门槛，未标OFFLINE_READY。

## 2026-11-13：规则引擎接入成品检测闭环

新增严格规则配置及证据元数据模型，Worker按报价固定规则快照与最终成品Facts计算逐项结论，保留本地解码和像素保护检查；支持尺寸/字节、白底、后加文字/Logo/水印、商品长边占比、人工身份判断和确定性抽检。未知来源、低置信度、不完整或未验证规则不能自动通过。配置损坏降级人工；Facts schema_version拒绝布尔值冒充整数。

29项单元和54项真实PG/MQ/S3集成通过；单元verified规则仅为合成策略。默认平台规则仍未验证，Fake事实不完整，实际任务保持manual_review。详见RULE_ENGINE.md及rule-engine-*.log。规则发布/证据归档、报告重算版本、生产构建与50对象性能、运维/CI和供应商适配仍待后续，未标OFFLINE_READY。

## 2026-11-13：规则发布、证据归档与报告版本重算

0020–0021增加只追加平台规则、严格配置/来源约束、版本唯一及发布审计；scripts/rules.py使用非owner ops_admin LOGIN，归档证据文件到私有S3并比对SHA，verified还需显式人工核验声明。加入三平台unverified空阈值种子，未导入真实政策。数据库加强原始报告和重算的自动通过守卫，空/不完整/未验证规则、错误版本、抽检或不完整事实均不能通过。

仅规则重算校验既有报告与成品S3摘要、PNG元数据、固定Facts；新报告保留原抽检和像素保护证据，追加报告/审计，不改任务原报告、资产、supplier attempt、积分或旧复核。API按check_id查询各版本/下载/复核，默认仍原报告；网页独立报告弹窗支持版本切换与当前JSON下载。

30项单元和61项真实PG/Rabbit/S3集成通过：发布/重算并发幂等、不可改写/版本冲突、证据私有403、坏摘要/错范围拒绝、跨用户已知ID 404、原复核与重算隔离、无新增intent/扣费。Chrome对实际生产dist验证3个完整用例及2个恢复/版本复跑，含规则CLI→版本切换→下载指向和余额不变，已视觉检查。浏览器改用run_local.py preview固定5173；API/Worker已更新，dev PG升级至0021。证据rule-versions-*.log、browser-production-rule-versions*.log。

周额度查询used21%，剩余79%。仍待50对象性能基准、完整运行门槛/健康检查/只读运维视图、干净部署备份恢复、CI及真实供应商适配，未标OFFLINE_READY。

## 2026-11-13：生产构建画布与非模型API性能

新增performance.spec.ts及确定性4MP合成PNG生成脚本。通过真实上传/普通界面鼠标在缩放平移后创建12个ROI；双画布50个绘制叶对象（2图像+24矩形+24标签，不计容器）持续缩放、平移、目标拖动60.636秒，结束验证源坐标不变、目标等尺寸整数平移。只读Konva观测证明实际Rect/Group位移及缩放变化，无内部store注入。

最终实测8834个RAF帧间隔，p95 12.1ms（目标<33ms），p99 24.4ms、最大48.8ms；4257次场景绘制CPU p95 1.3ms。20并发500次已登录混合只读API均200，包含所有失败样本的p95 141.9ms（目标<500ms）、p99 219.7ms、最大234.9ms。4500余个画布输入、最大间隔169.1ms；无任务创建、页面异常或远程host。

完整原始帧/绘制/API样本、设备、静态dist hash及CDP堆内存记录在performance-production.json，日志/截图已保存并视觉检查。单次JS堆从15.45MiB至19.46MiB，保留探针样本且未强制GC，不据此宣称无泄漏；53ms长任务也保留。环境为i7-13620H/16逻辑CPU/约31.7GiB、Windows、Chrome157 headless/DPR1/1920×1200，不能外推到公网部署或其他设备。详见PERFORMANCE.md。

README修正浏览器必须使用生产preview及隔离账号；基准加入常规E2E。周额度used22%、剩余78%。性能目标本机通过，仍缺完整检查命令/故障浏览器/健康就绪/只读视图及运维发布准备，未标OFFLINE_READY。

## 2026-11-13：有限API就绪、只读角色与干净实例

0022新增10个显式列security_invoker/security_barrier视图，逐列授权app_readonly；无密码、邮箱、会话、S3定位、输入/模型payload，无写权限或自定义SECURITY DEFINER权限。原生LOGIN测试证明当前受信任租户上下文只读、无上下文0行、越权UUID不可见，行安全关闭/角色提升/修改积分均拒绝。共享DB角色的GUC由受信任服务设定，不是直接给终端用户的数据库隔离账号。

/health/ready从占位503改为PG api/auth与S3 HeadBucket实测，scope api_dependencies。单项1.5秒async预算、S3原生短超时单次尝试、3秒健康/0.5秒失败缓存、single-flight；请求取消或超时保留并复用仍在执行的唯一存储探测。live仍只表示存活，MQ/Worker/供应商不由该响应证明。实际本机API更新并返回200，dev实例升级0022。

35项单元、68项真实PG/Rabbit/S3全回归通过，最终生命周期再跑3个健康用例通过；覆盖连接池耗尽有界503后恢复、S3拒绝访问仅storage失败、并发健康探测缓存、请求取消/线程复用、readonly并发/取消/语句超时复用清空GUC。P1-02 task入口补齐AST/模块导入及8个原生PG专项检查；其他未实现gate保持NOT_RUN。

setup_local新建6个非owner LOGIN并支持忽略目录内独立--profile-dir；verify_bootstrap.py在新建且独立PG17.11集群实际验证0001–0022、24个表FORCE RLS、6角色、重复upgrade schema不变、真登录/授额/产品写入/只读过滤。临时PG已关闭；凭据和profile只在忽略目录，证据bootstrap-health-readonly.json。完整说明及日志清单见READINESS_AND_ROLES.md。

周额度used24%、剩余76%。仍需完整task/all门槛、故障/unknown浏览器场景、运营备份恢复、CI/部署产物和供应商适配，未标OFFLINE_READY。

## 2026-11-13：受控故障浏览器与未知状态恢复

前端unknown不再作为SSE终态，持续接收运营结案和回执resume；同产品待对账禁用普通生成入口，其他产品可独立编辑。取消按钮加忙碌保护，提交防连点与异步用户归属保护；取消/失败明确指内部积分释放，成品提示按auto_overall显示。

DurableFake late现保存图像/事实回执后丢失响应，允许对既有结果人工接纳/查询，禁止重发。Worker增加仅offline的CLI --fake-mode，run_fake_task.py严格读取本机忽略profile；HTTP业务请求没有故障参数。受控配置独立于常规e2e，无skip冒充验收。

37项单元和69项真实PG/Rabbit/S3回归通过。Chrome生产构建4常规+5受控通过：排队重复取消一次refund；明确失败刷新不重试；已创建意图取消409、unknown冻结184/16且普通入口禁用；运营结案无刷新释放；晚到回执无刷新完成且generate/detect各一次；创建响应丢失后同key HTTP200重放、唯一task/freeze/charge。截图和带时间/命令/版本/hash的browser-controlled-faults.json已保留。专属故障阶段暂停了本项目发布/消费进程，测试完成已恢复。

完整常规流程含真实MQ闭环、断网/refresh、草稿/账号切换、报告版本及独立PNG像素验证、手机视口和性能。最新60.430秒/50对象帧间隔p95 12.1ms；20并发500请求均200，API p95 359.0ms/p99 583.0ms/最大818.0ms，原始尾部未过滤。增加render_performance_report.py使摘要跟随新证据，未据单项性能宣告综合完成。

详见CONTROLLED_BROWSER.md、PERFORMANCE.md及browser-fault-*/browser-production-complete日志。周额度used27%、剩余73%。仍待完整任务/all命令及要求审计、备份恢复、CI/部署说明和供应商适配，未标OFFLINE_READY。

## 2026-11-13：同步快照备份与独立PG/S3恢复

新增backup.py create/restore、原生PowerShell演练及API/任务验证脚本。导出PG同步快照供pg_dump与逐表数量/内容摘要共用，复制DB引用的不可变原图/canonical/生成/最终图、报告、规则证据及离线Fake结果缓存。私有归档仅在忽略work/.local，数据文件校验与路径逃逸预检失败不会进入网络/写入；源角色密码/JWT私钥不入归档，运行身份恢复为NOLOGIN并重新签发新身份。

恢复只接受不同PG system_identifier的空目标和独立空S3服务；保留函数所有者/ACL，避免--no-owner扩大SECURITY DEFINER权限。pg_restore单事务，原initdb public空命名空间经验证后无CASCADE重建。先核对DB精确指纹及全部对象SHA，再仅适配新的storage_version_id、撤销旧会话，并把全部queued/processing/uncertain隔离为uncertain/manual，保留冻结额度、fencing和审计，不自动计费或重发。快照之后可能已有供应商调用，不能把缺失意图当成从未提交。

原生PG17.11/Seaweed4.53独立进程实测成功：25张表、183对象引用、148个Fake缓存文件校验；函数定义/所有者匹配，账本守恒/流水汇总/单一终态零异常。原成品/报告SHA、保护区RGB、人工复核和规则快照保留；三个未结束样本任务隔离，排队/未知Worker不能领取；已核验ID人工resume只查询归档、generate仍一次。源fixture正常结案且重复清理通过，临时目标进程已关闭，本地publisher/worker已恢复。

快照后产品标记未恢复，演练恢复起点快照年龄2.63秒；备份1.11秒，冷目标初始化到API/下载/安全恢复验证RTO24.15秒。修正PowerShell UTC/本地时间混算，RTO采用Stopwatch，RPO年龄采用DateTimeOffset。RPO/RTO目标NOT_SET，本机小体积演练不代表生产SLA。43项单元通过；说明及脱敏结果见BACKUP_RESTORE.md、backup-restore-drill/environment.json和对应日志。

周额度used30%、剩余70%。P5-02的重启/积压告警、完整task/all门槛、CI/部署说明和供应商适配仍未完成；未标OFFLINE_READY/RELEASE_READY。

## 2026-11-13：只读全局监控与Worker心跳恢复

0023新增ops_monitor及窄权限聚合SECURITY DEFINER函数，专用LOGIN仅能读取固定计数/年龄/耗时指标，无业务明细、凭据或写权限。连续publisher/worker每5秒心跳，默认15秒过期；单任务CLI不冒充常驻。监控CLI使用只读事务，独立有界MQ被动队列/S3 HeadBucket探测，输出JSON或Prometheus；ops/alerts.yml为未部署模板。财务异常严重、unknown/outbox积压警告，绝不自动改账或重发。恢复库在精确校验后清除历史心跳。

49项单元、74项原生PG/Rabbit/S3全回归通过，含5项新增真实监控权限/异常/心跳测试。实际暂停本项目Worker，18.9秒心跳年龄触发critical；重启后心跳0.51秒、MQ/S3 ready、alerts空且财务异常全0。证据monitor-healthy/worker-stopped/worker-recovered.json及monitor-native-full-20261113.log。修正Prometheus unknown告警标签匹配on()，正常采集显式输出scrape_error=0。说明见MONITORING.md。

周额度used32%、剩余68%，继续执行。MQ/S3真实重启、完整task/all门槛、CI/部署说明和供应商适配尚未完成；未标OFFLINE_READY/RELEASE_READY。

## 2026-11-13：原生MQ/S3重启与常驻进程恢复

新增native_restart_drill.ps1及restart_probe.py，固定隔离节点/端口、停止S3前核对监听PID/路径/数据目录/创建时间。真实Rabbit stop_app/start_app（保留Erlang VM）期间mq_unavailable严重告警；真实S3硬停止并新进程复用同数据目录期间storage_unavailable严重告警。恢复后持久化quorum消息redelivered、ack后fixture队列空；对象SHA保留、等长冲突覆写拒绝、签名下载成功且匿名拒绝。专用fixture已清理，既有业务队列与资产保留，零付费模型调用。

保留早期失败：第一轮短覆写收到file_size异常，fixture已清理并改等长；第二轮HeadBucket已成功但master/volume尚未可读，GET超时。第三轮加入有界实际对象读恢复后通过，对象读取至全部对象检查13.101秒，应用GET调用1次（SDK可内部重试），不宣称完整服务RTO。脱敏证据native-restart-drill.json；私有状态与诊断仅在忽略work。RUNBOOK保留原有开发配置说明并链接新增OPERATIONS_RECOVERY.md，覆盖告警分流、对账禁重发、备份/恢复与故障演练边界。

不重启常驻Publisher/Worker，重连后生产preview三项浏览器流程通过（36.6秒），包含新任务真实MQ闭环、报告/下载像素/移动端、会话/版本/隔离。随后74项真实PG/Rabbit/S3全回归通过（147.746秒）；最终monitor空告警、全部财务异常0、pending outbox 0，完成任务从28增至30。日志restart-browser/native-full-20261113.log及restart-final-monitor.json。截图更新并目视检查成品页。

周额度used33%、剩余67%，继续。P5-02实际演练证据已补充，但完整task/all可执行门槛、CI/部署产物、供应商离线适配及外部真实验证仍未完成；未宣告OFFLINE_READY/RELEASE_READY。

## 2026-11-13：BFL FLUX 3 官方协议离线契约

新增providers/bfl.py及tests/contract/test_bfl.py，独立验收入口python scripts/check.py task P4-01 --profile offline。重新读取官方生成/编辑/集成指南及当前OpenAPI；schema现列精确width/height，不照搬第三方width拒绝描述。脱敏源URL/时间/完整schema响应SHA在bfl-official-contract.json。httpx升为运行依赖，uv锁文件离线检查一致。

请求严格映射prompt/images/base64 canonical PNG/width/height/grounding=false，不泄露私有S3定位或内部用户/ROI/积分字段。固定官方POST，API主机轮询与delivery下载隔离，HTTPS/路径/id校验、无重定向、无环境代理、无压缩HTTP正文、大小上限；独立下载客户端不带API key或API Cookie。返回原图字节/MIME/SHA，隔离解码/实际尺寸与回贴仍由调用方完成。

PG意图之前提保持，额外本机UUID.intent排他fsync防并发/重建后重复提交；超时、5xx、畸形回执与429均不自动重发。已知回执私有留存；cost畸形保留id待对账，数量只记供应商BFL_CREDIT，currency/money未知，不伪造法币或混同用户积分。18项离线MockTransport契约测试通过，49项单元回归通过；日志bfl-contract/unit-regression-20261113.log。覆盖真实HTTP请求对象及响应处理，不是源码字符串断言，也不是账户调用证明。

BFL仍未接入当前仅offline的Worker源图传递、真实成本DB和报告标识；P4-02 Gemini与组合适配、P4-03明确授权真实调用仍待完成，不能标PROVIDER_VERIFIED。说明见BFL_PROTOCOL.md。周额度used34%、剩余66%，继续。完整task/all、CI/部署产物及外部样本/费用验证仍未完成，未标OFFLINE_READY/RELEASE_READY。

## 2026-11-13：Gemini官方SDK一次检测与结构化事实

新增providers/gemini.py及test_gemini.py，SDK精确锁定google-genai3.3.0和uv依赖哈希，模型保留gemini-3.8-flash。官方模型/结构化输出/SDK文档响应SHA与schema/提示摘要在gemini-sdk-contract.json。当前SDK默认5次尝试且自动CONTINUATION续发；明确attempts=1、automatic_continuation=false、禁用自动工具/函数调用，真实SDK加离线HTTP计数证明429/503/超时/续发场景仅一次POST。

提交前校验最终PNG SHA并用既有隔离子进程验证MIME/实际尺寸；SDK inlineData的mime_type/URL-safe base64按实际锁定编码解码后与全部最终字节一致，不传原图URL/用户生成提示/平台规则。固定Google HTTPS API及模型路径，环境不能改主机或Vertex/Enterprise后端；无代理/重定向，响应1MiB上限、拒绝压缩HTTP正文。PG意图仍为前提，额外本机排他fsync防重复；取消后保留意图。

单候选STOP纯文本JSON仍经Facts严格校验；截断/阻止/缺候选/工具调用/畸形或缺字段/额外compliant/越界框/非法置信度/尺寸不符均人工降级。低于0.75保留观察但analysis_complete=false及uncertainties，不宣称校准准确率。SDK/schema/提示摘要、真实response_id或null、最终SHA和实际usage落私有归档；本地gemini-UUID仅缓存标识，fetch_facts不重检测。缺usage及法币金额/币种保持null，不猜价格。Facts schema快照统一为min/max=1与原const=1等价，并加入一致性测试。

python scripts/check.py task P4-02 --profile offline：19项真实SDK/MockTransport契约通过；49项现有单元、18项BFL契约回归通过。uv锁文件和已安装60包兼容性通过；无真实模型调用、无付费。日志gemini-contract/unit-regression/bfl-regression-20261113.log，说明GEMINI_PROTOCOL.md。

周额度used35%、剩余65%，继续。组合Worker源图接线/最终PNG检测/真实成本记录与provider_profile报告仍待实现；完整task/all、CI/部署产物、P4-03外部真实验收未完成，不标OFFLINE_READY/PROVIDER_VERIFIED/RELEASE_READY。

## 2026-11-13：官方协议组合的原生Worker闭环

新增ProtocolProvider及0024迁移，显式offline_protocol_mock报价快照与bfl_mock/gemini_mock意图标签，默认API/CLI仍Fake。构造器拒绝真实或混合传输；Worker执行前核对锁定profile，协议请求构建前校验源图SHA和尺寸，实际BFL请求摘要绑定PG意图。支持同步Fake及异步SDK；BFL按DB既有id/polling_url只查询，Pending归还租约等待恢复，下载PNG/JPEG隔离canonical化、核验实际输出尺寸、本地保护回贴后将最终PNG完整字节交给Gemini。

报告明确offline_protocol_mock。移除组合链路对record_fake_cost的调用；新增intent/response追加观察，保留credit/token与回执摘要，货币/金额NULL、unknown且来源标识模拟；内部模拟积分仍只结算一次。观察写入仅app_worker、有效lease/任务/attempt归属、回执摘要约束、同内容幂等、不同内容拒绝、不可覆写。已有PG观察和回执优先，丢本地BFL费用元数据不重发也不阻止只查询归档。

9项原生PG/S3组合测试通过：JPEG→canonical→RGB回贴→最终PNG检测/报告/一次charge；BFL请求哈希、四条费用观察；Pending与重建、元数据丢失、归档失败安全恢复；生成/检测响应丢失冻结且零charge/refund、不再提交；明确终态一次释放、错误尺寸隔离且不检测；profile错配零调用；权限/fencing/不可变验证。完整样本protocol-pipeline.json及sample日志明确两供应商各1次假HTTP POST、真实PG17.11/S3和SDK3.3.0，零付费。

49项单元、39项协议契约、83项真实PG/Rabbit/S3全回归（170.918秒）通过；新版本机Worker重启后3项生产preview浏览器通过（37.5秒），截图更新并目视检查手机布局。test/dev都在0024、四个函数定义摘要一致；最终监控MQ/S3 ready、无告警、财务异常全0。说明PROTOCOL_PIPELINE.md，日志protocol-unit/contract/native-full/browser-20261113.log。未重复无改动的60秒性能基准。

周额度used37%、剩余63%，继续。协议假传输组合已完成本轮验证，但真正供应商传输、明确预算配置、真实任务报价/成本确认、P4-03样本/账户调用与完整task/all、CI/部署产物仍待完成；不标OFFLINE_READY/PROVIDER_VERIFIED/RELEASE_READY。

## 2026-11-13：CI与容器构建候选（等待实际运行）

新增GitHub Actions offline-native：固定Actions提交SHA、Python3.13/Node24.22.1/uv0.13.7/pnpm11.25.0，锁文件安装、单元/协议契约、gitleaks提交历史扫描、生产前端构建、原生服务及浏览器、无发布的容器构建。ci_native.py仅在Linux CI且无既有profile/端口占用时创建专属两PG集群、MQ及S3容器，随机临时凭据只留忽略.local，按唯一标签核对并清理。运行真实集成、常规/性能及暂停消费者后的受控浏览器；产出公开结果/构建hash，不上传私有profile或服务日志。

新增API/Worker及web多阶段Dockerfile、非root运行和白名单.dockerignore；基础镜像已从官方公开Registry核对并固定digest（ops/build-images.json）。web候选Nginx代理/api到api:8000。工作流contents只读，不含付费秘密或推镜像/部署步骤。

本机无Docker，当前仅脚本AST、action SHA长度及diff检查通过；实际Linux安装、镜像构建、服务与浏览器CI尚未运行，不称CI绿或P5-01完成。下一步推送后观察实际Actions并修复；SBOM/NOTICE、依赖漏洞检查、Compose与完整task/all入口仍待补齐。保留此前周额度used37%、剩余63%，继续。

CI首轮43311633840已实际通过Linux锁定安装、单元/契约、提交历史gitleaks与前端生产构建；两套PG迁移/初始化、原生集成均exit0，但独立API就绪等待超时，浏览器与镜像阶段未执行。当前尚无启动日志公开诊断，新增仅失败时脱敏输出启动尾部及最后ready响应，继续复跑定位；不把首轮失败改写成成功。SBOM/NOTICE与漏洞检查开发中，尚未阶段验收。

## 2026-11-13：依赖审计、实际许可文本与CI探针修复

pip-audit2.10.1、PyYAML6.0.3、jsonschema4.26.0纳入开发锁文件；新增dependency_audit.py和dependency_artifacts.py。已安装88 Python与100 npm组件生成CycloneDX1.6并严格schema校验，清单明确当前Windows构建环境/含开发工具/不含基础OS或未安装平台变体；绑定两个锁文件SHA，不冒充完整Linux镜像SBOM。保留上游实际许可声明与逐文件原文/SHA；不是将全部组件归MIT/Apache，也不替自有代码授开源许可。

初次缺5项法律文本已核实处理：pip-requirements-parser的mit.LICENSE后缀、packageurl-python已校验sdist内mit.LICENSE、icons-svg npm gitHead固定源码根LICENSE、is-mobile发布README完整MIT段、rolldown平台绑定同版本父包LICENSE/THIRD-PARTY-LICENSE。清单逐项注明来源、supplements/sources.json记录外部原件及摘要；目前缺原文数0。添加gitattributes保证法律文本字节不被换行转换破坏SHA。镜像候选复制第三方文本，CI在实际Linux环境重新生成并上传。LGPL/MPL和基础OS再分发义务仍需发布前核对，不宣称完成法律审查。说明SUPPLY_CHAIN.md。

本机pip-audit与pnpm audit均exit0：88项Python无已知漏洞、无跳过包，npm各级0；结果绑定锁文件，不能证明未知漏洞不存在。49项单元回归、uv锁文件/包兼容性和脚本/YAML检查通过，证据dependency-audit.json及相关日志。

两轮真实Actions（43311633840、43312752792）已通过干净Linux锁定安装、单元/契约、全历史gitleaks和前端构建；两套PG初始化及原生集成都exit0。后者脱敏诊断确认API已正常启动，但CI误用/health/ready得到404。已修正为实际/api/v1/health/ready，并更正RUNBOOK/OPERATIONS_RECOVERY的路径；本机该URL实际200、三项依赖ready。下一轮继续验证浏览器、性能、镜像构建；此前失败保留，不标CI绿/P5-01完成。

当前周额度used41%、剩余59%，继续。完整task/all、Compose、镜像完整审计/API交付说明及真实供应商授权/预算验收仍未完成；未标OFFLINE_READY/PROVIDER_VERIFIED/RELEASE_READY。

## 2026-11-13：Linux完整原生/浏览器通过，前端镜像构建修复

Actions43314133380实际通过89包锁定安装、49单元/39协议契约、Linux依赖审计/SBOM与全历史gitleaks、前端生产构建；83项真实PG/MQ/S3集成和4常规/性能+5受控浏览器全部通过，重启消费者后监控exit0。CI设备画布60.484秒/帧p95 16.7ms，500请求均200、APIp95 104.28ms，均保留失败样本与原始证据。后端Docker镜像已构建，但前端镜像pnpm build触发非交互依赖清理错误，整体仍failure，不称CI全绿。

日志确认前端Docker上下文177.54MB，原忽略规则目录重包含会带入主机node_modules。已明确末尾排除所有node_modules/dist/tsbuildinfo及.git/.local/work，并设前端builder CI=true；继续真实构建验证，不绕过pnpm锁定检查。

刷新当前31路径OpenAPI；新增API_USAGE.md及P5-01可执行门槛verify_delivery.py/check.py task P5-01：校验API schema、镜像/Actions固定引用、268法律文本引用SHA、188组件SBOM及锁摘要，再要求当前提交的新鲜原生/全部浏览器/性能、审计和实际非root镜像结果。当前Windows无Docker，本机门槛正确返回exit3 BLOCKED_ENV，静态检查PASS；不会用历史已提交报告假通过。新门槛已加入后续CI。

周额度最近used41%、剩余59%。CI镜像与新增门槛待复跑；Compose、完整task/all与外部真实供应商/预算验收仍未完成，不标P5-01完成或OFFLINE_READY/PROVIDER_VERIFIED/RELEASE_READY。

CI43315437241已实际通过全部原生/浏览器/性能及两个镜像构建、非root导入/Nginx校验；最终新P5-01脚本因在同进程发现unit/integration重名test_monitoring模块而失败。已修复为各套件独立解释器发现，本机正确统计49/39/83；不跳过测试或放松证据绑定。该轮公开原生/镜像证据与失败门槛原样保存docs/evidence/ci-43315437241，provenance明确整体failure。继续完整复跑至新门槛实际通过，尚不宣告P5-01完成。

## 2026-11-13：Compose启停候选与受控测试路由生命周期修复

新增compose.yaml及compose_runtime.py：两个独立PG17.11、Rabbit4.4.0、Seaweed4.53固定digest，必要端口仅回环；私有随机bootstrap凭据、路径派生项目名+随机owner、容器/卷/网络标签核对。dev up/down/bootstrap及migrate --compose-profile入口补齐，日常down保留卷，已有profile拒绝覆盖；run_local支持显式忽略目录profile，doctor报告Linux镜像支持。Rabbit固定hostname，S3在/data保存filer/master/volume状态；无默认生产密码或应用迁移owner复用。

P0-02入口新增独立work项目Compose演练：fresh bootstrap全部迁移/6角色/RLS/API/只读、写S3对象与quorum消息、保卷down/up比较PG身份/用户数、S3SHA及消息，最终仅清理该临时项目和测试卷。P5-01要求本次Compose证据。Windows无Docker，实际P0-02/P5-01本机均exit3 BLOCKED_ENV，YAML/AST及49单元通过；尚未把候选称为Compose已验收，待Linux CI首次运行。说明COMPOSE.md，私有日志失败时脱敏后供诊断。

上一轮CI43316645913原生/常规性能通过，但受控取消竞争用例撤销路由时在途handler仍await，出现Route is already handled导致该轮失败，未到镜像/最终门槛。按Playwright unrouteAll behavior=wait在释放barrier后等待当前handler完成，不忽略错误、不改业务断言。该竞争用例本机重复5次全通过（约1分钟），随后完整5受控用例通过（38.1秒）；日志controlled-route-race-repeat/full-20261113.log，截图/案例证据更新。独立账号/本项目消费者暂停后已恢复，最终monitor无告警、所有财务异常0。

当前周额度used45%、剩余55%，继续。下一轮真实CI继续镜像/交付门槛及新增Compose验证；完整task/all与真实供应商/预算验收仍待完成，未标OFFLINE_READY/PROVIDER_VERIFIED/RELEASE_READY。

## 2026-11-13：原生验收补齐与 Compose 配置权限修正

审计将账务及 HTTP 幂等提交改为 Barrier 同步起跑的 20 请求，新增同一钱包、不同产品竞争仅够一单余额的验收。补充 4 项跨租户/产品/资产版本外键及状态/财务删除约束负例、2 项迁移实体/FORCE RLS/重复升级不变检查。针对 18 项全通过；完整原生 PG/MQ/S3 共 90 项通过（168.694 秒，无跳过），证据 acceptance-db-gaps-20261113.log 与 acceptance-native-90-20261113.log。协议流水线证据随实际重跑刷新；未调用付费模型。

Actions 43319072663 在新增 Compose 阶段失败：S3 镜像非 root UID 无法读取宿主 0600 配置。修复为 0700 私有目录下只读绑定 0644 S3 文件；其他 state/env 保持 0600，不改容器为 root。Compose 另补空库升级 head、上一 revision 升级 head，并由交付门槛核对 revision。当前 Windows 无 Docker，等待下一轮 Linux CI 实际验收，尚未宣告 Compose 或最终门槛通过。

P0-01 新增真实来源摘要检查并接入 CI。source-map 保留 12 份规范原始 SHA，补 Git blob SHA，严格只容许已记录换行规范化；本机 PASS。ADR 更新已验证原生服务范围及用户远端推送授权，原始计划文档保持不改。交付静态门槛仍 PASS：31 API 路径、188 依赖组件、268 法律文本引用。

周额度 used48%、剩余52%，继续；完整 task/all、当前 Compose/镜像门槛及真实供应商/预算验收仍待完成，未标 OFFLINE_READY/PROVIDER_VERIFIED/RELEASE_READY。

## 2026-11-13：逐任务入口与综合离线证据门槛

补齐 P0/P1/P2 的实际行为测试映射，严格拒绝无测试或 skipped；原执行包中的计划文件名与实际合并套件对照见 ACCEPTANCE.md。P1-01 仍要求独立 Compose 新库/上一版升级，P2-05 还需真实生产浏览器 CSS/像素证据，未降级为仅单元测试。

P3-01..04 及 all --profile offline 现在核验当前提交完整原生/生产浏览器/性能/Compose/镜像/依赖证据，CI 增加该门槛；实现文件未提交或旧报告均拒绝。综合成功仅 OFFLINE_READY，明确排除真实供应商、P5-02 独立运维演练和发布。P4-03/P5-03 返回 WAITING_EXTERNAL，不做模型调用/部署。P5-02 增加当前 commit/schema 的恢复、重启、500 请求性能证据校验，Windows 演练开始写 commit，旧报告正确返回 BLOCKED_ENV。

驱动验证：49 单元通过、P0-03 的 11 项通过、全部映射文件存在、AST 编译/差异检查通过。当前 Windows 缺 Docker，综合门槛返回 3；P5-02 现存旧恢复报告也返回 3。未把新增入口称为已全验收。提交 d04777b 的 CI 43321769038 正在原生/浏览器阶段，随后验证 Compose 权限修正。

## 2026-11-13：当前迁移原生恢复/重启/性能与 P5-02 通过

在提交 9e8f247 上暂停本项目发布器/Worker，实际将 schema 0024 的 26 张表、244 个 S3 对象引用和 196 个 Fake 缓存文件恢复到独立 PG/S3。函数所有者/表指纹、已交付 SHA/保护 RGB、规则/人工复核、会话撤销、3 个未结束任务隔离、未知/排队不可提交和已知 ID 仅查询恢复均通过。冷目标 RTO25.40 秒，快照年龄3.39 秒，备份1.88 秒；生产 RPO/RTO 目标仍 NOT_SET。临时恢复进程关闭、测试 fixture 结案后恢复本项目发布器/Worker。

继续原生 Rabbit stop_app/start_app 及 S3 硬停止/新进程重启，MQ/S3 故障告警和恢复、持久消息重投、S3 SHA/不可覆写/私有签名下载与匿名拒绝全通过。随后当前提交生产性能：60.393 秒真实指针操作、50 绘制对象；帧 p95 12.1ms，20 并发500请求均200，API p95 239.89ms。P5-02 门槛实际 PASS，结果 operations-gate-9e8f247.json；最终监控无告警、各账务异常0。报告严格说明单节点和未知生产目标，不外推高可用/SLA。PERFORMANCE/BACKUP_RESTORE 摘要按本轮原始数据更新。

CI43321769038 原生90项和全部9浏览器已通过；Compose 已达到新库/上一版升级、6角色验证和保卷重建后的 PG/S3/MQ 读取，但最后专用 quorum 测试队列 if_empty 条件删除被 Rabbit 拒绝，整体仍 failure。按官方问题记录 https://github.com/rabbitmq/rabbitmq-server/issues/10543 改为 ACK 后 passive 验证消息数为0，再无条件删除本临时项目专用队列；不操作业务队列。本机真实 Rabbit 相同流程已 PASS，日志 compose-quorum-cleanup-20261113.log。原轮失败诊断和来源保存 ci-43321769038，未将部分结果称为 Compose PASS，继续复跑。

周额度 used49%、剩余51%。真实供应商及发布仍未授权/未验收；综合离线门槛待当前 CI 实际全绿，不标 OFFLINE_READY/PROVIDER_VERIFIED/RELEASE_READY。

## 2026-11-13：真实镜像运行闭环候选与现状索引

新增 container_smoke.py 并接 CI 镜像构建后：独立临时基础服务及私有 bootstrap，实际刚构建 API/Nginx/Publisher/Worker 四容器均非 root，按服务只传对应非owner角色，JWT单文件只读挂载。经 Nginx 登录/上传/报价/提交、MQ实际消费、最终 PNG/报告 SHA 与保护RGB、manual_review、200→184且单一charge验收；报告绑定当前提交/两个镜像ID，P5-01新增必需证据。只使用offline Fake，Linux host network仅回环演练、不代表生产TLS拓扑；一次性容器可写层不证明缓存持久性。只清理随机owner标签相符的专用容器/临时卷。异常日志脱敏后公开，私有profile留忽略目录。

本机 AST/静态交付检查通过，Windows入口正确exit3且未动原生服务；没有Docker，故此为待真实CI验收候选，不标容器任务闭环已通过。API_USAGE/ACCEPTANCE明确命令、权限及边界。新增TASK_STATUS逐项汇总并在STATUS顶部区分最新状态与历史日志，避免早期记录被误认为当前未实现功能。

CI43323370220（35694a4）已实际通过新的Compose完整阶段，正在构建镜像及综合门槛；9e8f247旧运行在取消请求前已结束，因此无需取消。下一提交继续验证新增容器闭环，不提前宣告整项目完成。

## 2026-11-13：首次完整 Linux CI 全绿与 OFFLINE_READY 基线

提交35694a4的 Actions43323370220全部成功：https://github.com/wei-boop312/-AI-/actions/runs/43323370220 。锁定安装、49单元/39契约、审计/SBOM/法律文本/全历史秘密扫描、生产构建、90原生PG/MQ/S3、4常规/性能+5受控浏览器、Compose新库/0023→0024/保卷PG与S3与MQ、两个非root镜像、P5-01与all离线门槛均实际PASS；综合报告为OFFLINE_READY。Linux186组件/264法律引用，Windows188/268，平台依赖差异如实保留。

该轮Compose38.909秒。API镜像sha256:3f8e7026d389232d0eaa254fbce807545befe9cda97d8e7b4ba96496949a2013，web镜像sha256:ac018b0c8a8bd6e1c853229a3ead2e821850741339938c890b8b360784367631，revision均绑定35694a4；只构建未发布。19份公开原始报告与下载归档SHA/来源保存ci-43323370220，artifact私有下载包留忽略目录，避免三天保留期后只剩叙述。旧失败记录保留。

该轮不包含后续ec2a155新增的实际容器任务闭环，不能把较早绿灯扩展到新要求；ec2a155的CI43324484300正在原生/浏览器阶段。STATUS顶部/TASK_STATUS按已验范围更新。真实供应商/预算、规则适用范围完整证据和目标发布仍未验收；不标PROVIDER_VERIFIED/RELEASE_READY，不将离线MVP完成冒充整个项目完成。周额度最近剩余51%，继续。

## 2026-11-13：受控丢失响应同步与公共签名指纹扫描误报

CI43324484300实际通过90原生/4常规浏览器，受控第5项等待按钮恢复失败，未到容器闭环。原测试在handler刚进入时就递增intercepted，在真实POST201及abort完成前开始5秒UI断言，存在时序缺口。改为等待实际201/解析任务ID/abort完成的lossInjected，再严格检查只拦截1次、手工再次确认返回200、相同key/ID、唯一task/freeze/charge；不重试整个用例、不改业务断言。该用例本机连续10次通过（1.2分钟），完整5项通过（36.8秒），日志controlled-lost-response-repeat/full-20261113.log。原轮失败保留ci-43324484300；仍待Linux证实修正，未声称CI已恢复。测试仅暂停本项目消费者，之后恢复，最终monitor空告警/财务异常全0。

另CI43324941200在扫描新增原始Docker检查证据时失败。固定版本Gitleaks本机定位唯一命中为公共Python镜像GPG签名指纹，官方Dockerfile明确用于下载公钥验证Python源包，不是API密码/私钥。新增.gitleaks.toml继承全部默认规则，唯一allowlist限定generic-api-key、确切指纹和归档docker-images路径AND匹配；其他情况仍扫描。通过官方发行包digest/checksums验证的8.30.1真实全历史34提交扫描无其他命中；4个正负范围用例全部符合预期。CI显式配置并保存redacted JSON，不移除原始证据或重写历史；SUPPLY_CHAIN写明依据和边界。

静态交付门槛PASS（31路径、188组件、268法律引用），差异检查通过；当前尚无新容器运行验收结果。周额度最近used51%、剩余49%，继续。

## 2026-11-13：完整主计划复核与恢复初始目标修正

除tasks映射外逐条复核原主计划§13，发现旧报告RPO/RTO写NOT_SET遗漏原有“RPO24h/RTO4h初始演练目标”。保留旧原始证据不回填；新增ops/recovery-objectives.json（来源/原计划SHA）、严格评估及恢复报告目标摘要，P5-02重新计算、拒绝目标不符/超标。NaN/Infinity/负数/布尔及无效阈值拒绝，边界/超标保留失败结果，不把单次快照年龄外推生产备份频率/SLA。52单元通过，新增3项边界/负例通过；Windows恢复脚本AST通过，实际新恢复报告待提交后重跑。Docker候选包含同目标配置。

补主计划命令check.py all默认offline别名、受保护check.py e2e（本项目offline回环5173 profile/生产dist/真实浏览器），default all本机正确因未提交代码/缺新证据返回3。e2e真实入口待后续实际运行。

新增PLAN_GAPS：完整应用Compose（不只是4个基础服务或手写docker run）、持久缓存/资源/健康/优雅退出、主计划列举的全量运行指标、后端格式/类型门槛和真实供应商预算/Worker接线尚未闭合。不能只凭早期较窄gate绿灯认定完整V4。STATUS顶部/TASK_STATUS明确范围，继续按完整主计划制作，没有把差距改为可选或声称项目完成。
