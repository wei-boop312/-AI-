# 百炼可选视觉检测适配

用户已允许增加百炼qwen3.8-flash检测适配，保留Hubway/Gemini路径。独立协议适配器及schema 3双百炼离线组合已实现，0064增加运行登记候选；平台报价/预算、PG检测归档和默认Worker尚未开放。不能使用旧Gemini授权、费率或用量字段调用它。真实传输仍在构造前被拒绝，只接受显式MockTransport。

schema 3显式配对qwen-image-3.0与qwen3.8-flash，并要求同北京业务空间、密钥指纹、商户指纹及计费分组。schema 1/2的Hubway检测路径保留。两端事实、请求端点及用量分别绑定；旧Gemini执行范围不能替代新检测范围。登记仅保存身份元数据，准备报价明确返回`qwen_vision_quote_budget_path_not_enabled`，不会借用旧报价和预算开启支出。数据库登记与拒绝报价的真实验收等待该提交的Linux CI。

官方[模型页](https://help.aliyun.com/zh/model-studio/qwen3-8-flash)和[视觉接口](https://help.aliyun.com/zh/model-studio/vision/)确认模型支持图像理解，使用北京业务空间 `/compatible-mode/v1/chat/completions`。仅提交已隔离规范化的最终PNG内联字节，绑定SHA和实际尺寸；项目限制4MP/10,000,000字节。不开流式、工具或自动续轮，显式关闭思考并限制输出8192 token。

本机绑定连接的目录只读核验已得到HTTP200和精确qwen3.8-flash行。可用`bailian_metadata.py --probe --model qwen3.8-flash --config <私有连接> --output-dir <新的.local目录>`重新核验；不加--probe不读密钥或请求。目录存在不等于推理权限、质量或计费已验收；完整响应只留私有目录，不能提交供应商账户数据。

[结构化输出说明](https://help.aliyun.com/zh/model-studio/qwen-structured-output)明确多模态输入会将json_schema降级，不能假设服务端执行Schema。因此请求使用json_object并在系统提示附事实Schema，本地用既有严格Facts模型检查JSON唯一键、字段/尺寸/坐标和置信度。拒绝、截断、工具调用、错模型、无效JSON或不合规事实都保留人工复核，低置信度保留检出的文字/标志，不把未检出当作可靠不存在。模型不决定平台合规。

意图文件O_EXCL/0600/fsync先于HTTP，超时、显式失败或未知结果均不会重发同一意图。原HTTP字节/base64/SHA、最终图SHA、请求/提示/Schema摘要与派生事实/用量留不可变私有记录；读取时从原文重新校验，不信任被修改的结论。

OpenAI兼容用量与Gemini六计量规则分开：prompt包含缓存、completion包含思考；本请求已禁思考，计量必须有完整严格整数及缓存/思考明细，且总数相符。缺字段、布尔/浮点、额外收费量、错模型或意外思考时不生成精确数量，不推定零费用。金额/币种保持unknown，费用估算、账单和真实质量仍待后续独立接线及验收。
