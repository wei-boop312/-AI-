# 供应商运行配置候选

Hubway未能核实图片编辑接口时，可以保留原FLUX 3 Image生成模型走BFL官方，并让Gemini检测继续走Hubway。用户已允许自行配置替代编辑服务；本阶段只实现配置审阅和离线组合，不创建账户/密钥、不充值、不执行付费请求。官方[模型介绍](https://bfl.ai/models/flux-3-image)、[API Swagger](https://api.bfl.ai/docs)及[价格页](https://bfl.ai/pricing)确认该模型具备生成/编辑入口；价格页不等于当前账号的账单证据，未自动发布费率。

将`ops/provider-runtime.example.json`复制到被Git忽略的私有目录。模板全零指纹和EXAMPLE分组只是占位，不代表商户已审阅；正文禁止API key、密码或额外字段。生成目前仅允许BFL官方精确origin和flux-3-image；检测允许google_gemini官方origin或hubway_gemini的两个精确origin，固定gemini-3.8-flash。没有核实Hubway编辑协议前不虚构该生成选项。

`python scripts/provider_runtime.py --config work/private-runtime/runtime.json`只核验结构，输出配置SHA、模型、端点及应使用的环境变量名，不读取密钥，不创建客户端，不连接数据库/供应商。返回RUNTIME_BINDING_REVIEW_READY表示可供审阅，不表示已经接通或授权费用。`--check-credentials`额外在本机读取所选环境变量，检查格式及与配置中credential_fingerprint是否相同，只返回每步布尔值。BFL使用BFL_API_KEY，Hubway使用HUBWAY_API_KEY，官方Gemini使用GEMINI_API_KEY。

credential_fingerprint由前缀ASCII字节visual-provider-credential-v1、一个NUL字节、再拼接密钥ASCII字节计算SHA256。可在本地通过`visual_platform.providers.runtime.credential_fingerprint`生成，不能将密钥贴进聊天、配置、命令行参数或公开日志。该摘要用于绑定同一把密钥，不能证明该密钥属于配置所声明的商户；商户指纹和计费组仍需运营独立核实。更换密钥也会要求新的配置摘要和完整报价/预算审阅，不能借旧授权换账户继续提交。

配置摘要覆盖版本、各步模型/origin、商户指纹、分组及密钥指纹。`execution_binding()`产生受信服务器快照字段provider_runtime_sha256、provider_models、provider_accounts和完整provider_endpoints，受原报价SHA及预算授权绑定；HTTP客户端无权注入这些字段。配置origin是明确选择，不跟随HUBWAY_BASE_URL等环境变量静默变化，也不会在默认/直连/官方地址之间自动回退。

`offline_runtime`将同一配置组合现有BFL与Gemini/Hubway适配器，但必须显式注入两份httpx.MockTransport；混合或缺失transport在创建目录/客户端前拒绝，密钥指纹不符同样拒绝。带运行配置的任务不能由没有该配置摘要的旧协议实例代领，模型/端点/商户/运行SHA不符在供应商意图前拒绝；已有原回执时保留未知与冻结，不自动重投。该组合仍标offline_protocol_mock，不能冒充live。

真实执行尚需live专用报价/预算/任务领取和传输观察接线、实际Hubway响应兼容性、真实样本与账单证据及明确费用上限；当前AGENTS仍禁止实际付费调用。不得因本地配置校验成功就把现有Fake消费者切到真实请求。配置与密钥存在也不构成PROVIDER_VERIFIED或上线完成。

## 受限离线协议报价准备

0049候选先持久化登记已审阅的运行元数据（不包含密钥）：`python scripts/provider_runtime.py --config work/private-runtime/runtime.json --register-config --reviewed-sha256 <运行配置SHA> --operation-id <登记操作uuid> --reason <配置审阅原因>`。此模式与check-credentials、prepare-protocol-quote互斥，单独配置审阅不是费用授权。版本正文和摘要存入Ops私有FORCE RLS表，只能追加，API/Worker无原始读写权限；登记与唯一审计同事务，相同正文可复用版本但不同审阅操作各留审计。

数据库在新报价和调用意图插入时独立核对登记的完整模型/端点/商户绑定，未登记的运行SHA和与登记正文不一致的字段拒绝；未使用运行配置的历史Fake/mock任务保持原兼容性。登记版本可通过受限provider_runtime_context函数读取并重建对象，不依赖创建时的本地JSON文件。密钥只保留领域隔离摘要，商户归属和兼容性仍未验证；备份恢复不会因此恢复费用授权。

0048候选提供Ops入口，使用普通API刚创建且未消费的Fake报价作为业务来源：

`python scripts/provider_runtime.py --config work/private-runtime/runtime.json --prepare-protocol-quote --user <uuid> --source-quote <uuid> --reviewed-sha256 <运行配置SHA> --operation-id <uuid> --reason <审阅原因>`

仅此显式模式读取ADMIN_DATABASE_URL并写入新报价及唯一审计；结构预检不写数据库。来源用户、产品、源图、生成参数、规则与外观快照保持一致，PG独立拒绝业务改写、模型替换、NULL或任意端点、账户字段中夹带密钥。新报价标offline_protocol_mock并使用现有试验积分规则，不是供应商真实费率；原报价不覆盖，新报价仍须单独登记费用范围预算，再提交任务并显式调用匹配的离线Worker。CLI不登记预算、不创建任务、不执行模型。

相同operation/来源/用户/配置/原因重放返回原报价和原SHA，即使来源后续已消费也不新建或延长授权；任何改动不得复用操作。新的操作要求来源仍有效且未消费。审阅方随后使用provider_budget.py review-quote取得新报价完整input_sha256，不能把运行配置SHA当作完整费用范围SHA。普通API/Worker没有这两个Ops函数权限，未开放通用数据库写权或公开供应商切换参数。
