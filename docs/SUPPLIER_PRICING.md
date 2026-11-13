# 供应商价格证据与精确估算

## 当前范围

0032为供应商价表提供私有不可变版本、S3证据归档、明确运营审阅和精确估算。它与用户积分的trial price_version分开；不修改固定任务报价、钱包、原始用量观察或已确认费用，也不启用真实模型。没有默认/种子真实价格。当前估算仍是estimated或unknown，actual_spending_verified始终false。0033已接入任务估算、超额阻断与带数据冷恢复，9174020整轮通过。

当前普通API仍创建offline Fake报价；新价表绑定通过可信协议演练报价验证。SDK互斥计量、任务估算及保守超额阻断已实现；真实商户配置选择、显式多单位授权、供应商账单确认及live接线是后续工作，不能用此候选宣称费用已核实。

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

使用精确有理数/整数累加，合计后以整数除法向上取整到8位小数以避免有限精度吞掉微小尾数；溢出为unknown。即便所有明确数量为0且估算为0，仍不表示账单已确认或免费。缓存、思考、输入等计费项必须来自可核验的互斥计量，不能从totalTokenCount猜拆，也不假定SDK的prompt/candidate字段已覆盖全部供应商计费。当前不会把三项现有Gemini用量自动当作完整发票依据。

## 冻结身份与恢复

可信报价可在_execution.provider_price_versions按generate/detect冻结价格UUID及完整文档SHA，同时在provider_accounts冻结商户指纹/计费分组。PG逐项核对原价表、有效期、步骤、模型端点和账户；旧报价不随新价表改变。完整quote SHA继续被0027预算授权覆盖。

ProtocolProvider收到明确运行时商户范围后先验证结构（不允许密钥字段）并独立复制；每一阶段与报价中的范围精确比较。缺失/更换账户或组，先于任何新意图/POST被阻断；旧无账户范围的offline协议测试保持旧语义。该入口仍只接受MockTransport，不能用此配置绕过付费禁令。

备份引用收集包含价格证据对象，冷恢复校验原表/函数指纹后只改写恢复后的S3版本ID，保留价表正文/SHA/审计；新增独立恢复断言实际证据可读且SHA不变。原预算恢复撤销与检测降级重新审阅规则不变。

## 验证边界

本地新增10单元（合计121）、新增1协议契约（合计47）、Ruff与Linux/Windows各96生产/运营源码检查通过。8项PG/S3候选覆盖发布/实际归档、精确估算、并发幂等/不可变、审阅与S3失败拒绝、绕过Python的类型负例、权限、冻结报价与正确账户交付、错误账户零POST、错误账户/端点/SHA/过期报价拒绝；新增冷恢复价表证据实际读取。原生与整轮CI尚待执行，不将单元或SQL生成当作PG证明。

## 原始响应计量准备

Gemini HTTP响应在SDK转换数值前校验JSON与六项计数，缺失值不补0，布尔/数字字符串/浮点不能成为整数计费量；重复键、矛盾总数、未知计费字段、工具token或非标准serviceTier不标完整。异步响应使用每个submit独立ContextVar，禁止并发意图互换计量。SDK事实解析和原回执摘要不因此改成合规/费用确认。

[Google GenerateContent UsageMetadata](https://aistudio.google.com/api-reference/generate-content)说明prompt计数包含缓存，总量另含思考、工具和候选输出。因此后续互斥输入量必须扣除明确缓存项，思考不能静默漏掉；该字段语义依据不是Hubway真实兼容性或价表证明。当前只保存经原始响应核验的计量完整性，不写confirmed账单。

0032阶段实际全量证据：e714f7d / CI43495545487成功，121单元/47契约/153原生、4+7浏览器和完整Compose/独立恢复/重启/P5-02通过，包含supplier_price_archive_preserved实际冷恢复校验。原始计量a9cb71a及后续0033仍按各自提交验收，不将价表阶段的绿灯用于账单/live宣称。

## 0033任务估算与超额阻断候选

任务响应观察保持unknown/null，不覆盖原始记录；持有有效Worker租约者只能从已应用回执及不可变response_observation推导，不传入金额。新增规范化估算关联表把cost_record_kind=estimate、同用户/任务/意图的原始响应观察、原回执摘要和冻结价表UUID/SHA以复合FK绑定；货币值只保存在app.task_cost_records。发布新价表不能重写旧估算。

BFL数量来自已报告的BFL_CREDIT，必须有明确价表才能估算；Gemini必须有原始响应完整性、精确报告模型和六项明确整数计数，缓存从总输入扣除、思考独立计算；工具、缺项、未知新维度、模型不符或价表不覆盖全部互斥项都记录unknown/null，不补0。元数据缺失与供应商报不同模型均不触发新POST；报告也不会把明确不同模型的事实当作完整检查。

Python与PG分别以整数有理数累加，不经有限精度中间除法；最终向上取整到8位，溢出仍unknown。新增微小尾差边界单元验证超过普通Decimal上下文的正尾数不能被吞掉。没有二进制float或站内单位的隐式美元兑换。

超出步骤/合计授权，或明确绑定的价表无法与USD预算比较，将预算阻断；后续新付费意图与hold在同一事务拒绝，先前回执/归档可安全完成本地步骤，内部积分保留冻结等待人工结案。过期价表在第一步前拒绝并释放无付费意图的冻结；已有意图后过期保留冻结。预算原上限不增加，旧review-blocked不能绕过估算审阅阻断。此阻断是保守估算的风控，不证明真实发票超额。

```text
python scripts/supplier_pricing.py task-costs --task <uuid>
python scripts/provider_budget.py inspect --authorization <uuid>
```

私有输出含估算/未知金额、币种、价表来源、原因与ceiling_state；known_estimate_subtotal只是已知同币种估算的小计，不是全部实际支出。estimate_coverage_complete要求生成与检测两步都存在同币种已知估算；即使完整，actual_spending_verified仍false。用户积分、原始供应商观察与最终账单确认各自独立。

本地新租约/预算测试及有理数边界合计128单元、SDK计量与模型不符合计50契约已通过本地完整回归；新增11项PG/Worker/S3候选涵盖两步精确估算、原未知保留、一次结算、超额后零检测POST/保留冻结/禁止重开、非货币单位、缺计量/模型不符、并发单记录、中断与审计失败回滚、权限/FK/不可变、实际到期前置拒绝及小数向上取整。原生/完整冷恢复必须看新CI，不用本地单元冒充。

## 带数据的恢复候选

独立恢复演练新增非空估算账本：固定MockTransport和合成凭据在loopback profile生成已知回执与最终PNG，明确BFL_CREDIT价表不可比较USD预算，故不得产生检测POST。快照新增第5项被隔离任务，恢复验证原估算金额/单位/关联ID/价表SHA与待审阻断完整保留，不变成美元或实际已确认支出。源fixture仅通过受限fail结案释放内部积分，成本记录不删改；目标保持隔离。该演练不证明live私有SDK元数据或真实账单已验，必须单独看当次冷恢复CI结果。

0033与非空账本恢复最终证据：9174020/CI43503294037成功，128单元/50契约/164原生、4+7浏览器、完整Compose/独立冷恢复/重启/P5-02通过，包含cost_estimate_history_and_review_block_preserved。这里只验证合成供应商与估算，不代表真实发票、实际USD支出或Hubway live接通。
