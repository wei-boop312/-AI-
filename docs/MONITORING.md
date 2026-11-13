# 聚合监控与进程心跳

新增0025候选通过`ops.business_metrics_snapshot()`提供24小时业务聚合，monitor JSON的business_metrics字段包含：合并连续重复事件后的已结束阶段墙钟跨度、供应商提交意图/已知回执/未知状态数量、每个attempt优先采用settlement→response→intent→estimate的一项费用观察，以及成品规则检查人工率。费用按供应商/币种/状态分组，金额以十进制字符串保留；未知币种和未知金额仍是null，绝不把估算与结算双计或跨币种相加。平台规则重算属于新的检查记录，人工复核决定不冒充自动规则结果。

阶段跨度只包含24小时窗口内开始并已结束的持久阶段，包含阶段内I/O/等待，不能称为CPU耗时或每个内部函数耗时。提交意图不是已确认计费HTTP调用。Prometheus增加固定阶段/供应商/步骤标签的数量、p95和人工率、未知费用次数；精确币种金额保留在JSON中。读取仍只授予受限ops_monitor/ops_admin的聚合函数；不授予其业务表、事件载荷或可切换reader身份。新增4项原生正负例等待CI，67单元及离线迁移SQL生成通过；不能把该候选称为原生已验证。

API时延/5xx与归档失败计数仍明确列在missing_measurements中，完整运行指标门槛继续阻断，后续补采集及真实负例。历史监控证据如下。

迁移0023提供`ops_monitor` NOLOGIN组及`ops.monitor_snapshot()`。部署时创建独立非owner LOGIN，仅继承ops_monitor，通过私有环境变量MONITOR_DATABASE_URL传入；不得授予superuser、BYPASSRLS或表所有权。只返回全局数量、年龄、财务异常计数与24小时任务耗时p95，不返回用户ID、邮箱、对象地址、提示词或凭据。监控组不能直接读业务表或修改积分；本机CLI也拒绝高权限连接。

运行`python scripts/monitor.py --probe-dependencies`，或本机已有私有profile时`python scripts/run_local.py monitor`。退出码0正常、1警告、2严重、3监控无法完成。专用DSN优先；本机兼容回退到既有非owner ADMIN_DATABASE_URL。`--prometheus`生成文本；`ops/alerts.yml`为规则模板，尚未部署Prometheus/Alertmanager或配置通知接收人。运维采集器须以临时文件加原子替换写入textfile collector，并自行监控采集时间，禁止把陈旧指标当作持续健康。

连续publisher/worker每5秒写一次数据库服务时钟心跳，默认15秒过期；单任务/单次CLI不宣称常驻服务存活。心跳只是进程可访问DB，不代表每项供应商调用或MQ消费成功。可选MQ探测以非robust短连接被动检查既有generate队列；S3只做HeadBucket，不创建对象。API ready仍只代表其PG/S3依赖，不等于整个系统就绪。

财务等式、流水汇总、冻结任务与钱包关联、任务计费状态、重复终态异常为严重告警；unknown超过300秒、outbox超过30秒或租约过期为警告。告警只读，绝不自动释放冻结积分或重发供应商。阈值可用CLI参数调整；Prometheus规则中的默认阈值需同步修改。24小时任务耗时包含任务从创建到终态的全部等待，不是HTTP API延迟；无样本不导出伪造的p95。

证据：49项单元、74项原生PG/Rabbit/S3集成测试通过（monitor-unit/native-full-20261113.log）。专用LOGIN越权、unknown重复读取仍冻结、账本异常检测/回滚、心跳超时与配置错误脱敏有真实数据库覆盖。monitor-healthy.json、monitor-worker-stopped.json、monitor-worker-recovered.json记录实际常驻Worker停止后18.9秒触发严重告警，重启后恢复且全部账本异常为0。恢复脚本在精确快照核验后清空历史服务心跳，防止恢复库误报存活。

尚未在本轮完成MQ/S3真实重启演练或生产告警接收部署；不得据此宣告P5-02或整体上线验收完成。
