# 聚合监控与进程心跳

迁移0023提供`ops_monitor` NOLOGIN组及`ops.monitor_snapshot()`。部署时创建独立非owner LOGIN，仅继承ops_monitor，通过私有环境变量MONITOR_DATABASE_URL传入；不得授予superuser、BYPASSRLS或表所有权。只返回全局数量、年龄、财务异常计数与24小时任务耗时p95，不返回用户ID、邮箱、对象地址、提示词或凭据。监控组不能直接读业务表或修改积分；本机CLI也拒绝高权限连接。

运行`python scripts/monitor.py --probe-dependencies`，或本机已有私有profile时`python scripts/run_local.py monitor`。退出码0正常、1警告、2严重、3监控无法完成。专用DSN优先；本机兼容回退到既有非owner ADMIN_DATABASE_URL。`--prometheus`生成文本；`ops/alerts.yml`为规则模板，尚未部署Prometheus/Alertmanager或配置通知接收人。运维采集器须以临时文件加原子替换写入textfile collector，并自行监控采集时间，禁止把陈旧指标当作持续健康。

连续publisher/worker每5秒写一次数据库服务时钟心跳，默认15秒过期；单任务/单次CLI不宣称常驻服务存活。心跳只是进程可访问DB，不代表每项供应商调用或MQ消费成功。可选MQ探测以非robust短连接被动检查既有generate队列；S3只做HeadBucket，不创建对象。API ready仍只代表其PG/S3依赖，不等于整个系统就绪。

财务等式、流水汇总、冻结任务与钱包关联、任务计费状态、重复终态异常为严重告警；unknown超过300秒、outbox超过30秒或租约过期为警告。告警只读，绝不自动释放冻结积分或重发供应商。阈值可用CLI参数调整；Prometheus规则中的默认阈值需同步修改。24小时任务耗时包含任务从创建到终态的全部等待，不是HTTP API延迟；无样本不导出伪造的p95。

证据：49项单元、74项原生PG/Rabbit/S3集成测试通过（monitor-unit/native-full-20261113.log）。专用LOGIN越权、unknown重复读取仍冻结、账本异常检测/回滚、心跳超时与配置错误脱敏有真实数据库覆盖。monitor-healthy.json、monitor-worker-stopped.json、monitor-worker-recovered.json记录实际常驻Worker停止后18.9秒触发严重告警，重启后恢复且全部账本异常为0。恢复脚本在精确快照核验后清空历史服务心跳，防止恢复库误报存活。

尚未在本轮完成MQ/S3真实重启演练或生产告警接收部署；不得据此宣告P5-02或整体上线验收完成。
