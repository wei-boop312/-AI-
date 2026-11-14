# 百炼国内图片编辑接入

当前适配固定使用北京业务空间的 `qwen-image-3.0`，检测保留独立 Gemini/Hubway 身份。百炼适配仅接受显式 MockTransport，默认 Fake 不变；创建密钥和离线验收不表示真实出图已接通。账号此前提示余额不足，尚未充值或调用真实供应商。

## 本机配置密钥

在自己的 PowerShell 执行下面命令，按遮蔽提示输入控制台密钥，不要发送到聊天或提交到仓库：

```powershell
& "C:/Users/MECHREVO/Documents/Codex/2026-11-12/ai/outputs/visual-production-platform/scripts/configure_provider_key.ps1" -Provider bailian
```

工具保存本机 Windows 用户/当前进程变量 `DASHSCOPE_API_KEY`，不请求模型；已有值不会无提示替换。环境变量不是加密保险库。若控制台已无法再次查看密钥，需要在控制台创建新的专用密钥，再本机输入。

本机连接预检使用下面命令；将示例域名替换为实际北京业务空间域名，输出目录必须全新：

```powershell
.venv/Scripts/python.exe scripts/bailian_connection.py --prepare-local --endpoint-origin https://ws-EXAMPLE.cn-beijing.maas.aliyuncs.com --output-dir .local/bailian-connection
```

该命令只读本机密钥、写连接身份与指纹，不保存密钥、不发 HTTP、不建立执行授权。`--config .local/bailian-connection/connection.json` 默认不读凭据，附加 `--check-credentials` 才比较本机密钥指纹。用户提供本机 CSV 路径后，密钥已保存本机用户环境，回读一致；`.local/bailian-csv-connection/connection.json` 本地预检 `credential_matches=true`。配置仅存身份与指纹，不存密钥。尚未请求远端，不能据此确认认证、余额、费率或模型可用。

## 协议与验收范围

按[阿里云官方接口文档](https://help.aliyun.com/zh/model-studio/qwen-image-generation-and-editing-api-reference)，适配使用异步 POST `/api/v1/services/aigc/image-generation/generation`，带 `X-DashScope-Async: enable`，再以已知 task_id 查询 `/api/v1/tasks/{task_id}`。不混用同步或 OpenAI 兼容接口。项目限定最多三张输入图、输出面积 512² 至 4MP；下载隔离认证信息、禁止重定向，并独立规范化 PNG。

显式运行身份采用 schema2，百炼演练预算采用 schema4，生成 CNY 与检测 USD/Hubway 单位分别约束，不换汇或合并。不能复用旧 BFL 预算。原始提交与成功查询回执分别保存到不可变私有 PG 记录，查询计量绑定原下载和规范图 SHA；缺失或不合规计量保持 unknown。

价格必须经过私有证据审阅发布，再以生成/检测两个版本 ID 与 SHA 显式绑定到报价。百炼四档图片计量不得套用 BFL 积分或 Gemini token。异步 POST/PENDING 不提前估算；成功查询有完整计量后才派生精确估算。缺失计量或超过 CNY 上限时停止后续检测、保留图片和冻结。估算不是账单，内部积分不是供应商人民币支出。

最新完整通过基线为 b122d1f2 / CI43633883081：209 单元、92 契约、268 原生、4 普通与 11 受控浏览器，以及 Compose、独立恢复和离线交付包验证。百炼非空冷恢复已由本轮独立验收证明，后续源码仍须自身 CI；详细候选及失败记录见 STATUS.md。

## 尚需完成

本机密钥及真实业务空间预检、实际价格证据与预算、经明确授权的真实图像样本、质量评估、真实账单核对及部署仍未完成。离线测试不替代这些验收；现阶段不开放真实付费调用。

## 请求前价格预测

0062候选新增只读 `python scripts/provider_budget.py project-generation --user <用户UUID> --quote <报价UUID>`，需要本机Ops数据库身份。按冻结请求的单张输入/输出面积和已审阅价格计算CNY预测；不读模型密钥、不请求模型、不创建成本账本或费用授权。未知费率返回unknown，不当作免费。PG在生成预算hold前再次核验，已知超上限时拒绝整个意图事务；真实供应商计量仍须从成功查询独立归档与估算，预测不等于账单。

0063候选增加真实原图前置检查：每边1–8000像素、宽高比最多10:1、项目保守大小上限10,000,000字节，不能用平台通用8192边长上传能力推断百炼能接收。PG依据所属不可变原图而非调用者JSON，在报价和任务写入前检查；请求适配器再次核规范PNG头与CRC。普通上传仍保留原能力，只有百炼路径应用此限制。
