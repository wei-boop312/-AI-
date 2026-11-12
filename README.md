# 跨境电商 AI 视觉生产平台

V4 规格实施中，当前为首轮工程基础，尚非可用 MVP。

运行：`python scripts/dev.py doctor`、`python scripts/check.py unit`。
单元测试需要 Pillow（当前环境已存在）。未实现的集成检查明确失败，不返回虚假成功。

已实现：严格矩形坐标、无损像素回贴与保存后验证、纯领域钱包状态、保守规则判定、一次提交假供应商。
规格见 docs/specification；实际状态见 docs/STATUS.md。

安装：uv sync --locked；测试：uv run python scripts/check.py unit；启动健康API：uv run uvicorn visual_platform.api.main:app --app-dir src。ready当前返回503，业务API尚未实现。
