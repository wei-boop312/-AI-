# 供应商价格证据与精确估算

## 当前范围

0032为供应商价表提供私有不可变版本、S3证据归档、明确运营审阅和精确估算。它与用户积分的trial price_version分开；不修改固定任务报价、钱包、原始用量观察或已确认费用，也不启用真实模型。没有默认/种子真实价格。当前估算仍是estimated或unknown，actual_spending_verified始终false。

当前普通API仍创建offline Fake报价；新价表绑定通过可信协议演练报价验证。真实商户配置选择、SDK用量到互斥计费项的转换、任务估算记录、供应商账单确认、超额处置及live接线是后续工作，不能用此候选宣称费用已核实。

## 私有发布与查看

需要非owner的ops_admin LOGIN（ADMIN_DATABASE_URL）。发布另需S3_ENDPOINT、S3_ACCESS_KEY、S3_SECRET_KEY、S3_BUCKET及可选S3_REGION。文档与原始证据保留在私有本地目录，不提交真实账单/商户材料。

```text
python scripts/supplier_pricing.py publish --document <private-price.json> --evidence-file <private-evidence> --attest-reviewed --operation-id <uuid> --reason <review-reason>
python scripts/supplier_pricing.py inspect --price <uuid>
python scripts/supplier_pricing.py estimate --price <uuid> --metering-context <private-usage.json>
```

发布必须明确审阅，证据1..20MiB且SHA与文档一致。先校验专属运营身份，再将证据按operation与SHA写入私有不可变对象；数据库发布、审计和唯一版本在同一事务。S3失败不产生价格记录；精确operation重放返回原版本，改文档/理由不能覆盖。API/Worker不能直接读取或发布价格表。CLI不输出对象key、签名URL或凭据。

价格文档采用严格schema_version=1：provider、固定model、精确endpoint_origin、不可逆merchant_fingerprint、billing_group、version、currency、UTC valid_from/valid_until、evidence_kind、evidence_sha256、complete_meter_coverage=true和rates。额外字段（包括API key）、布尔冒充整数、浮点价格、指数/NaN、重复计费项均拒绝。SQL再次独立校验，不能仅靠Python。每次人工核验有效期最长31天是本工程的保守运营规则；过期不自动续期，不代表供应商承诺31天不变价。

支持USD/CNY，以及明确标为BFL_CREDIT/HUBWAY_BALANCE_UNIT的非货币单位。没有内建credit、站内余额、人民币、美元或用户积分之间的兑换率。非货币单位的估算不能与USD预算比较，也不能冒充实际美元支出。

## 互斥计量与估算

rate包含measure、精确十进制字符串amount与正整数per。允许bfl_credit、input_tokens、output_tokens、cached_input_tokens、cache_write_tokens、thinking_tokens；生成只接受bfl_credit，视觉检测只接受token项。价格与数量都不使用二进制浮点。

计量上下文必须明确provider/model/endpoint_origin/merchant_fingerprint/billing_group、UTC observed_at及quantities。数量集合必须与价表项完全一致：缺失项不补0，多出项不忽略；未知新增计费维度、过期或任一身份不符均返回unknown且amount/currency为null。BFL credit数量须精确十进制字符串；token数量须非负整数，布尔、float与负数不是有效数量。

使用高精度Decimal，合计后向上取整到8位小数以避免低估；溢出为unknown。即便所有明确数量为0且估算为0，仍不表示账单已确认或免费。缓存、思考、输入等计费项必须来自可核验的互斥计量，不能从totalTokenCount猜拆，也不假定SDK的prompt/candidate字段已覆盖全部供应商计费。当前不会把三项现有Gemini用量自动当作完整发票依据。

## 冻结身份与恢复

可信报价可在_execution.provider_price_versions按generate/detect冻结价格UUID及完整文档SHA，同时在provider_accounts冻结商户指纹/计费分组。PG逐项核对原价表、有效期、步骤、模型端点和账户；旧报价不随新价表改变。完整quote SHA继续被0027预算授权覆盖。

ProtocolProvider收到明确运行时商户范围后先验证结构（不允许密钥字段）并独立复制；每一阶段与报价中的范围精确比较。缺失/更换账户或组，先于任何新意图/POST被阻断；旧无账户范围的offline协议测试保持旧语义。该入口仍只接受MockTransport，不能用此配置绕过付费禁令。

备份引用收集包含价格证据对象，冷恢复校验原表/函数指纹后只改写恢复后的S3版本ID，保留价表正文/SHA/审计；新增独立恢复断言实际证据可读且SHA不变。原预算恢复撤销与检测降级重新审阅规则不变。

## 验证边界

本地新增10单元（合计121）、新增1协议契约（合计47）、Ruff与Linux/Windows各96生产/运营源码检查通过。8项PG/S3候选覆盖发布/实际归档、精确估算、并发幂等/不可变、审阅与S3失败拒绝、绕过Python的类型负例、权限、冻结报价与正确账户交付、错误账户零POST、错误账户/端点/SHA/过期报价拒绝；新增冷恢复价表证据实际读取。原生与整轮CI尚待执行，不将单元或SQL生成当作PG证明。

## 原始响应计量准备

Gemini HTTP响应在SDK转换数值前校验JSON与六项计数，缺失值不补0，布尔/数字字符串/浮点不能成为整数计费量；重复键、矛盾总数、未知计费字段、工具token或非标准serviceTier不标完整。异步响应使用每个submit独立ContextVar，禁止并发意图互换计量。SDK事实解析和原回执摘要不因此改成合规/费用确认。

[Google GenerateContent UsageMetadata](https://aistudio.google.com/api-reference/generate-content)说明prompt计数包含缓存，总量另含思考、工具和候选输出。因此后续互斥输入量必须扣除明确缓存项，思考不能静默漏掉；该字段语义依据不是Hubway真实兼容性或价表证明。当前只保存经原始响应核验的计量完整性，不写confirmed账单。
