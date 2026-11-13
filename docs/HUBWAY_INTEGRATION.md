# Hubway 供应商接入候选

用户于2026-11-14指定使用Hubway中转。原始V4规范不改写；本文件记录新供应商决定和当前证据。

## 网站核实

已使用用户当前登录的Chrome查看现有项目专用密钥、可用渠道和在线聊天设置。项目密钥已绑定Gemini Ultra分组，聊天模型列表明确包含gemini-3.8-flash并已选择。保留原有密钥与额度，不创建、扩权、充值、发送消息或调用付费模型。公开模型广场仅列gemini-4-argon的情况不能覆盖登录后针对该密钥的模型选择器结果。站内使用说明给出GOOGLE_GEMINI_BASE_URL=https://hubway.cc，默认/直连端点分别为https://hubway.cc和https://z.hubway.cc。

截图仅保存在忽略的work目录（可能含账户信息），不提交Git。真实密钥不保存到仓库、日志、截图或配置示例，不将站点页面输出当作授权扩大访问。

## 代码与配置

HubwayGeminiProvider使用已锁定Google SDK和原Facts schema，不改为聊天文本冒充图片检测。from_environment读取私有服务端HUBWAY_API_KEY、HUBWAY_BASE_URL及HUBWAY_VISION_MODEL；示例只给空密钥。允许的origin严格为上述两个地址，不添加/v1、不接受URL凭据/查询/自定义端口/任意主机。模型固定gemini-3.8-flash，拒绝环境变量静默改成4-argon。GeminiProvider保留官方默认作为独立契约基线。

离线候选请求为POST /v1beta/models/gemini-3.8-flash:generateContent、x-goog-api-key头、精确最终PNG和结构化Facts配置。该路径和认证方式来自原Google SDK协议与网站Gemini CLI接入提示的组合推断，**只有MockTransport证据，未宣称Hubway服务端真实接受**。实际兼容性、账单和样本质量需明确付费额度及受控最小验收，当前AGENTS禁止真实付费模型。

私有intent记录endpoint_origin用于追溯。请求guard只允许所选精确host/路径，无环境代理、重定向或SDK自动重试。302/429/503等保留未知；相同intent跨默认/直连也不可再次提交，不照搬站点自行重试建议。无自动切回官方接口。

## 验证及剩余条件

45离线契约通过：两个Hubway origin的实际SDK请求路径/认证/图片字节及私有元数据、非法URL拒绝、私有环境与模型替换拒绝、限流/错误与跨origin禁止重投。所有测试使用合成key和MockTransport，不是供应商原生验收。

默认任务Worker、报价及预算授权仍offline/offline_protocol_mock；本次不将实验性网关自动接进生产消费者，也不将原预算授权改成新商户/费用。运行环境未写入实际密钥。FLUX图片编辑API/模型未核实；图片生成不能改成文本模型后声称完成。真实请求/响应、费用单位和账单证据、运行快照中的网关身份/授权绑定及后续live门槛仍待闭合。API供应商替换尚未完整完成。


## 冻结网关绑定候选

ProtocolProvider在Worker的每个阶段先核对_execution.provider_endpoints与生成/检测实例实际请求端点。旧协议mock快照未写此字段时固定解释为原官方BFL/Gemini地址，不跟随新环境变量。显式Hubway需在受信报价快照中记录完整端点对；原0027授权quote_input_sha256覆盖整个快照，因此运营审阅也绑定该选择。当前API仍只创建Fake报价，公开schema不允许用户传_execution；不新增未经审核的live报价入口。

无意图时地址不符会在读取源图/写意图/网络发送前拒绝并走无意图释放；已有未决回执时拒绝变更路径并按原函数转uncertain保留冻结，不写成未收费，不切换默认/直连重新提交。旧授权与旧任务记录不改写，不能仅凭相同模型名称跨中转。

46离线契约通过包括官方旧快照保留、两个Hubway精确绑定、缺失/空/额外字段和错误端点拒绝。3项新增原生候选验证：未冻结Hubway无意图无POST且退款；原回执后切Hubway只保留原一次POST和冻结；完整PG授权SHA绑定显式Hubway mock路径并完成真实S3交付。需新CI证明；所有供应商请求仍MockTransport。这解决内部路由约束，不证明真实账单或Hubway服务端兼容。

2026-11-14补充检索：[公开Model Plaza](https://api.hubway.cc/model-plaza)仍不足以核验本项目的FLUX图片编辑协议和3.8检测模型实际结算。页面站内单位说明不作为已核实USD或人民币兑换率；未检索到可归档的FLUX编辑接口文档，不推断该服务一定不提供。现有固定模型/登录选择器证据保留，不自行改为其他模型。
