# 离线交付包

CI完成当前提交的静态、单元/契约、原生PG/MQ/S3、生产浏览器、完整Compose、冷恢复/重启和全部offline gate后，执行`python scripts/handoff.py`，生成`work/ci-public/offline-handoff.zip`和摘要报告`offline-handoff.json`。两者随该提交的GitHub Actions artifact上传；artifact按仓库现有设置保留3天。先核对报告commit，再下载对应包。

包内目录：

- `source/`：`git archive HEAD`的准确受版本控制源码，含锁文件、运行说明和历史证据。
- `frontend/`：当次生产构建，每个文件必须与原生浏览器测试记录的摘要一致。
- `evidence/`：当次5个原始门槛JSON，全部必须同commit、通过、零付费调用，静态报告明确实现目录干净。
- `supply-chain/`：当次生成的Python/npm SBOM、实际打包许可文本、NOTICE及其摘要引用。
- `HANDOFF.json`：每个文件的字节数/SHA256、源码提交和未验外部门槛。

下载后在已安装工程依赖的环境校验：

```sh
python scripts/handoff.py --verify <offline-handoff.zip的路径>
```

返回`OFFLINE_HANDOFF_VERIFIED`只证明包的内部完整性与对应离线证据约束。核对可信的GitHub运行来源、侧边报告SHA和commit，才能确认来源；ZIP清单并非数字签名。包内历史source/docs/evidence不替代本次evidence/，不同提交的绿灯不能互相外推。

验证器拒绝重复/大小写冲突成员、路径穿越、绝对路径、反斜线、私有.env/工作目录、符号链接、超限成员、摘要不符、陈旧/失败门槛、浏览器验收后变更的前端以及缺失/变更的许可文本。创建器再次运行现有P5构建校验，再从准确提交导出源码；输出文件仅新建，不覆盖既有包。默认测试用合成fixture校验拒绝条件，实际包生成必须由干净CI完成。

此包状态为`OFFLINE_READY`，provider_verified、production_deployed、release_authorized均false。P4-03真实供应商、质量与实际账单，以及P5-03目标环境、适用规则/权属与发布决定仍待完成。运行完整服务按包内RUNBOOK和Compose说明初始化专属环境和私有凭据；本包提供源码、前端构建和验证证据。原项目代码的许可状态见NOTICE说明，不因打包而赋予新的开源许可。


首次实际交付包已在[9248667 / CI43520402375](https://github.com/wei-boop312/-AI-/actions/runs/43520402375)生成：1282文件、4,467,445字节，下载到本机后再次独立校验通过。原始sidecar和嵌套ZIP SHA见docs/evidence/ci-43520402375；后续提交仍须生成/验证属于自身commit的新包。

最新完整基线[8f7687a / CI43531050538](https://github.com/wei-boop312/-AI-/actions/runs/43531050538)的实际包含1362文件、4,678,394字节，侧边SHA为7fc0d641bf1250e3d456dfe126fc3d8d1c6b71550461f0917dd41607bc534a65。本机下载后独立验证OFFLINE_HANDOFF_VERIFIED，原始sidecar、日志计数和来源摘要保存ci-43531050538。它不含后续上传/报价界面及SSE循环修正。

最新完整候选[c4d1105 / CI43536961836](https://github.com/wei-boop312/-AI-/actions/runs/43536961836)：181 Python单元/56契约/223原生/4普通+10受控浏览器及全部门槛PASS，实际包1404文件、5,179,941字节，SHA为07b29b7ab776831cd2ed9af712378f2c6eaa8f7c188793496c5d0362356f9b5f；下载后独立验证通过。原始sidecar和上传/报价专门PASS报告及原日志摘要保存在ci-43536961836。0046独立恢复重放和启动参数兼容是后续提交，不借用此包的已验范围。
