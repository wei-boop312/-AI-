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
