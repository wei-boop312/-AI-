# V4 实现与验收现状

截至提交 `35694a4`。本文件为实现状态，原始 tasks.json 保留规划快照。PASS 只代表表述范围和对应提交的实测；代码变更后综合门槛要求新 CI，不能沿用历史 PASS 宣称当前提交全绿。

| 任务 | 已有实际结果 | 尚需满足 |
| --- | --- | --- |
| P0-01 | 12 份来源摘要核对通过；独立工程，无旧项目源码移植 | 新提交继续 CI 校验 |
| P0-02 | 锁定安装及四个 Linux 原生服务通过；Compose 已 bootstrap 及保卷读取 | 修正 Quorum fixture 清理后完整 Compose PASS |
| P0-03 | 严格 schema/Fake/未知/事实隔离测试通过 | 随当前 CI 回归 |
| P1-01 | 0024 实际迁移、重复 upgrade、FK/状态/财务约束通过；CI 新库及上一版升级已执行 | Compose 整体结束并生成 PASS 证据 |
| P1-02 | 6 非 owner LOGIN、FORCE RLS、readonly/事务上下文和取消/超时隔离通过 | 随当前 CI 回归 |
| P1-03 | 私有认证、轮换/重放、停用/退出、CSRF/Origin/限流通过 | 随当前 CI 回归 |
| P1-04 | 真实账本/终态竞争/余额守恒；20 同步请求及不同产品竞争通过 | 随当前 CI 回归 |
| P1-05 | 报价快照/幂等/outbox 回滚通过 | 随当前 CI 回归 |
| P2-01 | 分页/revision/归档/跨用户/外观快照通过 | 随当前 CI 回归 |
| P2-02 | 私有 S3 上传/不可变版本、恶意输入及规范化通过 | 随当前 CI 回归 |
| P2-03 | 真实 Rabbit confirm/return/ACK/DLX、条件领取及 fencing 通过 | 随当前 CI 回归 |
| P2-04 | 持久化意图/独立回执、未知保留、仅查已知 ID、归档重试及运营对账通过 | 真实供应商仍未验收 |
| P2-05 | RGB 精确回贴及实际浏览器 CSS/整数坐标/保存下载验证通过 | 当前提交综合门槛 |
| P2-06 | 规则快照、最终 hash 绑定、人工复核/重检/多平台保守结果通过 | 实际市场/类目政策完整证据，种子仍 unverified |
| P2-07 | Fake 及官方协议 MockTransport 两套真实 PG/MQ/S3 完整闭环通过 | 不等于真实模型质量/费用验证 |
| P3-01 | 中文页面、草稿、缩放/平移/框选、报价/任务通过 | 当前提交综合门槛 |
| P3-02 | SSE 游标、重放/乱序/reset、refresh/轮询恢复通过 | 当前提交综合门槛 |
| P3-03 | 取消竞争、复核追加、未知无普通重试、版本/最终下载通过 | 当前提交综合门槛 |
| P3-04 | 4 常规/性能 +5 受控浏览器实际通过；9e8f247 本机性能复测通过 | 最新完整 CI，尚不标 OFFLINE_READY |
| P4-01 | 18 BFL HTTP mock 契约及组合 Worker 流水线通过 | 真实传输/账户/生成结果/费用 NOT_RUN |
| P4-02 | 19 Gemini SDK mock 契约及组合 Worker 流水线通过 | 真实识别质量/置信度/费用 NOT_RUN |
| P4-03 | WAITING_EXTERNAL，零付费调用 | 明确样本、次数/费用上限、安全密钥及真实测试授权；实时 Worker 传输/预算接线待验收 |
| P5-01 | 历史 CI 两个非 root 镜像构建及原生/浏览器/依赖/秘密扫描通过；最终门槛已实现 | 最新 Compose、镜像与综合门槛全部通过 |
| P5-02 | 9e8f247 实际 PASS，见 operations-gate-9e8f247.json | 生产 RPO/RTO 目标未设；仅单节点演练，目标环境需另验 |
| P5-03 | WAITING_EXTERNAL，无部署 | 目标服务器/地区/域名、真实费用、政策/素材权属和发布决定 |

当前周额度最近剩余 51%，未触及用户 20% 停止线；不因测试阶段完成就称整个项目完成。代码持续上传到用户指定仓库。尚无付费模型请求、生产部署或旧用户数据库迁移。

主要证据：acceptance-native-90-20261113.log、ci-43321769038（整体 failure，保留失败）、backup-restore-drill.json、native-restart-drill.json、performance-production.json、operations-gate-9e8f247.json、acceptance-operations-final-monitor.json。完整来源和范围见各文件及 STATUS，不混淆原生验证、mock 协议和真实供应商验证。
