# 百炼国内图片编辑接入

0056归档候选：原始异步提交回执可随PG保存并从租约受限函数恢复，原文/JSON唯一键/请求意图/任务ID/模型/业务空间都检查；私有本地响应文件丢失不能触发重发。此处归档的是提交响应，不等于SUCCEEDED查询的图片计量或人民币账单；后者仍待专门实现和验收。真正独立恢复的新flag须以当次CI成功为准。

0055补充：百炼编辑输出的总像素至少512²、至多项目4MP，单边256–6256且长短边比例不超过8；配置准备及PG报价/任务写入都独立检查。旧通用256×256选项不适用于百炼编辑，不会为了沿用它而静默放大或更改用户尺寸。

0054演练候选已准备百炼API报价到独立schema4预算、Worker、私有S3链路，等待原生CI。旧BFL预算不能复用；无百炼预算不产生供应商意图。schema4只允许固定Qwen模型、CNY生成与USD/Hubway单位检测，所有调用仍为显式MockTransport。原始供应商成本保持unknown，尚不接受百炼价格绑定，不能把内部16积分扣费视为阿里云人民币账单。前述0053“旧报价入口拒绝”是阶段记录，0054只为显式百炼演练开放，不自动改旧任务。

后续配置阶段：已实现Qwen+Gemini双MockTransport组合工厂及schema2运行身份登记候选，区别于旧BFL schema1；尚未开放百炼PG报价/预算与实际Worker任务。0053登记不等于授权执行，旧准备报价入口必须拒绝Qwen身份，避免错误套用BFL预算。

本地连接工具：`python scripts/bailian_connection.py --prepare-local --endpoint-origin https://ws-EXAMPLE.cn-beijing.maas.aliyuncs.com --output-dir .local/bailian-connection`。请用真实北京业务空间域名替换示例（示例本身不可用），工具仅从本机DASHSCOPE_API_KEY取指纹，写入全新私有目录，不保存密钥、不请求HTTP、不建立PG授权。`--config .local/bailian-connection/connection.json`默认不读凭据，附加`--check-credentials`才比较当前密钥指纹。配置输出仅供后续审阅，不能绕过真实样本/费率/预算/质量验收。

2026-11-15 用户已完成实名认证并确认创建北京默认业务空间项目专用API Key，控制台访问范围限定Qwen-Image-3.0。账号当时提示余额不足，未充值或调用模型。真实密钥、业务空间域名与账户标识不进入仓库。

## 当前交付边界

新增`providers/qwen_image.py`：固定qwen-image-3.0、北京业务空间域名，按官方异步编辑协议提交原图与编辑指令，再按同一业务空间查询已知任务。仅接受显式MockTransport；没有开放真实模型执行入口。原BFL/Gemini协议、默认Fake和既有报价/预算不自动切换。尚未接通百炼的PG报价/预算、计费版本和Worker组合，不能把创建密钥或离线契约通过称为真实出图成功。

官方[模型API文档](https://help.aliyun.com/zh/model-studio/qwen-image-generation-and-editing-api-reference)包含同步和异步两种不同地址。本适配选用异步：POST `/api/v1/services/aigc/image-generation/generation`，设置`X-DashScope-Async: enable`，收到task_id后GET `/api/v1/tasks/{task_id}`。同步multimodal地址、OpenAI兼容地址不可混用。输出usage是图片数量/分辨率档位，不是token、BFL积分或账户余额；费用仍未知，不推断免费额度或自动采用网页单价。

## 本机保存密钥

在自己的PowerShell运行：

```powershell
& ./scripts/configure_provider_key.ps1 -Provider bailian
```

输入遮蔽，变量名DASHSCOPE_API_KEY；仅写本机Windows用户/当前进程环境，不上传或调用接口。环境变量不是加密保险库。服务进程使用专有环境配置，浏览器端不放密钥。已有本机值不会无提示替换；显式空进程值不会回退旧用户值。`-ExplainOnly`仅说明、不读写密钥。下载的原始密钥文件不要放入工程目录，也不要发送到聊天。

## 传输与恢复边界

单次意图以排他本地文件先落盘，超时、429/5xx及未知结果均不自动重发。原始提交响应私有保存并用原始字节SHA关联回执；任务查询只读且验证任务ID/业务空间。下载仅允许明确的阿里云结果OSS主机，禁重定向、代理继承和认证头转发，限PNG/大小，后续仍须通过已有隔离解码及实际尺寸/保护像素校验。

图片输入最多3张、单图最多10MiB、输出限定项目4MP上限及供应商最小面积/宽高比；固定单张输出、不自动改写提示词。原任务必须保持原模型/商户/端点，百炼需要新的明确配置与审阅。持久化PG原文恢复、真实质量与账单验收仍待完成，现有BFL预算及费用不能套用于百炼。
