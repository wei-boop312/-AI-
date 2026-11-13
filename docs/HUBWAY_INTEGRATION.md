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
