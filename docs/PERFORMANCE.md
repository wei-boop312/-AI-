# 本机生产构建性能基准

基准命令：`pnpm --dir apps/web exec playwright test performance.spec.ts`，exit 0。运行时间2026-11-12T18:25:28.789Z至2026-11-12T18:26:36.868Z，应用基础commit `aa28b9fe7e50257343b1d6f9f2c10a99984ea567`；被测dist资源名和SHA256、原始样本及设备字段保存在[evidence/performance-production.json](evidence/performance-production.json)。运行日志为performance-production-20261113.log，截图为browser-performance-50-objects.png。相应测试与合成fixture生成脚本随本阶段提交。

## 环境与负载

13th Gen Intel(R) Core(TM) i7-13620H，16逻辑CPU，31.7GiB RAM，Windows 10.0.26200，Chrome 157.0.8103.50（headless），视口1920×1200、DPR 1。本机原生PG 17、RabbitMQ 4、私有S3、Python API与Vite静态生产预览，服务已启动预热；单独测量API与画布阶段。

通过真实API上传2000×2000、4MP的确定性合成PNG，并以普通界面控件和鼠标在缩放、平移后的原图创建12个ROI。50对象定义为双画布共2个Image、24个Rect、24个Text，不把Stage/Layer/Group计入，也不宣称有50个独立保护区域（业务上限20区域）。Konva对象只作只读观测，没有通过内部store注入区域或替代交互。按缩放比例验证框选坐标误差，实际指针受显示像素量化；结束后验证源坐标不变、目标宽高不变且坐标为整数。

随后连续60.636秒执行滚轮缩放、源画布平移和目标ROI拖动；观测到4587个画布输入事件，最大事件间隔169.1ms（阈值1000ms）。矩形实际最大位移123.7 canonical像素，画布组位移25.1显示像素，绝对缩放范围0.1522–0.2577。

## 结果

| 指标 | p50 | p95 | p99 | 最大 | 目标 |
|---|---:|---:|---:|---:|---|
| RAF帧间隔（8834样本） | 6.1ms | 12.1ms | 24.4ms | 48.8ms | p95<33ms，通过 |
| Layer场景绘制CPU（4257样本） | 0.4ms | 1.3ms | 2.2ms | 5.5ms | 单独诊断 |
| 非模型API（500样本） | 100.0ms | 141.9ms | 219.7ms | 234.9ms | p95<500ms，通过 |

API使用同一隔离账号、20并发、500次已登录GET，混合产品列表/详情、任务列表、余额、平台规则和当前用户，包含本机HTTP代理、认证和真实PG查询，读取完响应体后记耗时。所有500次HTTP 200；5xx、非200、超时和网络失败均保留在样本与分位数总体中并使验收失败，不过滤失败样本。文件传输、模型等待不在此负载中。

CDP JSHeapUsedSize从15.45MiB变为19.46MiB，JSHeapTotalSize从48.63MiB变为84.63MiB；Documents仍为1，DOM Nodes从1204变为1212。保留全部RAF/绘制/输入样本会占内存，本次没有强制GC，不能据单次堆差额判定有无泄漏。记录到一次53ms长任务，原始时间点保留在JSON。没有任务POST、账号下任务数为0、页面异常和远程host均为0。

## 解释边界与复跑

RAF测量的是浏览器回调间隔和主线程停顿；beforeDraw到draw仅为Konva场景绘制的CPU时间。数据不包含完整GPU呈现、物理屏幕延迟或整个浏览器进程RSS。API结果适用于本机已预热服务、单账号只读混合负载；公网、冷启动、多租户写入和生产部署容量需在对应环境另测。合成图不是商品质量评估样本。

先运行API/publisher/worker，再`pnpm --dir apps/web build`，停止开发web后用`python scripts/run_local.py preview`在5173启动生产预览。Chrome与.local/runtime.json必须可用；测试自动新建本机离线隔离账号。基准明确检查HTML含哈希静态资源且没有Vite开发客户端。每次复跑会更新同名JSON/PNG/log，应在Git提交或另存后再进行后续比较。完整OFFLINE_READY还需要其他P0–P3门槛，不能仅凭本基准宣告完成。
