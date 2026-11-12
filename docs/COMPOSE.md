# 隔离Compose基础服务

compose.yaml提供两套独立PostgreSQL17.11、RabbitMQ4.4.0和SeaweedFS4.53，均固定已核对的镜像digest。测试PG55432、开发PG55433、MQ5679、S318333仅绑定127.0.0.1；没有默认生产密码。默认启动范围只有基础设施，应用进程另行启动，不自行部署。

## 新环境启停

需安装可运行Linux镜像的Docker engine及Compose插件，并完成项目锁定依赖安装。本机当前没有Docker，原有原生服务验证不能代替Compose测试。

```text
python scripts/dev.py doctor
python scripts/dev.py up --profile-dir .local/compose
python scripts/dev.py migrate --compose-profile .local/compose
python scripts/dev.py bootstrap --compose-profile .local/compose --demo-account
python scripts/run_local.py api
python scripts/run_local.py publisher
python scripts/run_local.py worker
python scripts/run_local.py preview
python scripts/dev.py down --profile-dir .local/compose
```

preview要求先执行前端build。bootstrap会创建6个非owner LOGIN、JWT及私有runtime.json；已有profile会拒绝覆盖。demo-account仅在显式参数时生成，凭据留在忽略目录，不能上传。若需保留原有.local环境，可给bootstrap传`--profile-dir work/新目录/profile`，运行组件时也传同一个`--profile-dir`。

up生成私有state.json、compose.env、S3身份文件，项目名由该profile路径派生，另有随机owner标识。Docker容器/卷/网络操作前核对标签；遇到不属本profile的资源拒绝。首次启动遇到占用端口也拒绝，不停止既有原生或其他Docker服务。删除私有state文件不会授权接管原有数据卷，恢复时应保留相应私有配置。

down保留全部命名卷，不重置数据或凭据；不要用全局prune清理此项目。PG bootstrap超级用户只用于迁移/初始化，API、认证、Worker、发布器和只读视图各用独立运行身份。随机值和原始日志只在忽略.local/work，Windows文件ACL仍由运行者配置，不能把chmod当作完整Windows ACL隔离。

Linux私有profile目录为0700，state/env为0600。S3身份文件在该私有目录内设0644并只读绑定给非root容器；宿主其他用户仍无法穿过0700父目录，容器进程则能读取挂载文件。首轮Compose曾因该文件0600与容器UID不一致而读取被拒，已修正，保留实际失败记录。

Rabbit固定容器hostname以便重建后仍能读取原Mnesia数据；S3工作目录和master/volume/filer元数据放入/data命名卷，身份文件只读挂载。API、MQ、S3密钥不写进镜像或Git。若手工调用Compose，所有私有变量均必填，.env.example故意留空；推荐使用dev入口而不是把示例当生产凭据。

## 原生Compose验收

`python scripts/check.py task P0-02`创建全新work/compose-smoke-UUID profile，实际up、fresh bootstrap/全部迁移和重复upgrade、6角色/FORCE RLS/登录/产品/只读验证，然后写私有S3对象及quorum持久消息。执行保卷down/up后比较PG system identifier及用户数量、S3内容SHA、MQ消息；最后只删除已核对标签的该测试项目资源和测试卷。日常dev down没有删卷入口。

成功输出compose-smoke.json及bootstrap-health-readonly.json，绑定提交和环境；失败保留脱敏诊断，私有凭据不上传。无Docker返回exit3 BLOCKED_ENV，不能称验收成功。CI已加入该真实演练，并要求P5-01消费本次结果；当前候选尚待首次Linux Compose执行，不提前标通过。
