# 供应商运行配置候选

Hubway未能核实图片编辑接口时，可以保留原FLUX 3 Image生成模型走BFL官方，并让Gemini检测继续走Hubway。用户已允许自行配置替代编辑服务；本阶段只实现配置审阅和离线组合，不创建账户/密钥、不充值、不执行付费请求。官方[模型介绍](https://bfl.ai/models/flux-3-image)、[API Swagger](https://api.bfl.ai/docs)及[价格页](https://bfl.ai/pricing)确认该模型具备生成/编辑入口；价格页不等于当前账号的账单证据，未自动发布费率。

将`ops/provider-runtime.example.json`复制到被Git忽略的私有目录。模板全零指纹和EXAMPLE分组只是占位，不代表商户已审阅；正文禁止API key、密码或额外字段。生成目前仅允许BFL官方精确origin和flux-3-image；检测允许google_gemini官方origin或hubway_gemini的两个精确origin，固定gemini-3.8-flash。没有核实Hubway编辑协议前不虚构该生成选项。

`python scripts/provider_runtime.py --config work/private-runtime/runtime.json`只核验结构，输出配置SHA、模型、端点及应使用的环境变量名，不读取密钥，不创建客户端，不连接数据库/供应商。返回RUNTIME_BINDING_REVIEW_READY表示可供审阅，不表示已经接通或授权费用。`--check-credentials`额外在本机读取所选环境变量，检查格式及与配置中credential_fingerprint是否相同，只返回每步布尔值。BFL使用BFL_API_KEY，Hubway使用HUBWAY_API_KEY，官方Gemini使用GEMINI_API_KEY。

credential_fingerprint是`SHA256(b"visual-provider-credential-v1\\x00" + key.encode("ascii"))`的领域隔离摘要；这里的\\x00表示一个NUL字节。可在本地通过`visual_platform.providers.runtime.credential_fingerprint`生成，不能将密钥贴进聊天、配置、命令行参数或公开日志。该摘要用于绑定同一把密钥，不能证明该密钥属于配置所声明的商户；商户指纹和计费组仍需运营独立核实。更换密钥也会要求新的配置摘要和完整报价/预算审阅，不能借旧授权换账户继续提交。

配置摘要覆盖版本、各步模型/origin、商户指纹、分组及密钥指纹。`execution_binding()`产生受信服务器快照字段provider_runtime_sha256、provider_models、provider_accounts和完整provider_endpoints，受原报价SHA及预算授权绑定；HTTP客户端无权注入这些字段。配置origin是明确选择，不跟随HUBWAY_BASE_URL等环境变量静默变化，也不会在默认/直连/官方地址之间自动回退。

`offline_runtime`将同一配置组合现有BFL与Gemini/Hubway适配器，但必须显式注入两份httpx.MockTransport；混合或缺失transport在创建目录/客户端前拒绝，密钥指纹不符同样拒绝。带运行配置的任务不能由没有该配置摘要的旧协议实例代领，模型/端点/商户/运行SHA不符在供应商意图前拒绝；已有原回执时保留未知与冻结，不自动重投。该组合仍标offline_protocol_mock，不能冒充live。

真实执行尚需live专用报价/预算/任务领取和传输观察接线、实际Hubway响应兼容性、真实样本与账单证据及明确费用上限；当前AGENTS仍禁止实际付费调用。不得因本地配置校验成功就把现有Fake消费者切到真实请求。配置与密钥存在也不构成PROVIDER_VERIFIED或上线完成。
