# Workspace Instructions

Apply the `karpathy-guidelines` skill behavior by default for all coding work:

- Surface assumptions and ambiguity before making changes.
- Prefer the minimum code that solves the request.
- Keep edits surgical and trace every changed line to the user's request.
- Match existing style and avoid unrelated cleanup.
- Define verifiable success criteria and verify changes when practical.

## 强制修改文档同步

任何需求修改、功能新增或调整、Bug 修复、重构、API、配置、数据结构、数据行为、UI 行为或相关测试修改，都必须调用 `sync-project-change-docs` skill。

修改前必须读取 `docs/change-records/agents-all.md`，优先使用文档 ID 检索历史记录；修改后必须新增或更新对应模块文档并同步纯标题索引。代码已修改但文档未同步时，任务不得视为完成。
