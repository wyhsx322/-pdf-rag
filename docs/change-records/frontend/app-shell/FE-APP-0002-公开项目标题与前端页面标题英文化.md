# FE-APP-0002｜公开项目标题与前端页面标题英文化

## 修改背景

- 项目准备提交到 GitHub，需要将面向公开展示和搜索的题目改为英文。

## 原始需求

- 用户希望将“更好的辅助论文写作”转为更适合英文搜索和传播的项目题目。
- 标题需要利于其他用户搜索、理解和使用。

## 历史与重复检查

- 已检查 `FE-APP-0001`，前端应用壳层负责页面入口、路由、布局与全局导航。
- 当前没有已有变更记录覆盖浏览器页面标题英文化。

## 问题原因

- 原浏览器标题为中文“论文 RAG 系统”，对 GitHub 和浏览器搜索中的英文关键词覆盖不足。

## 影响范围

- 影响前端入口 HTML 的浏览器标题展示。
- 不影响路由、页面组件、业务 API 或数据结构。

## 实现逻辑

- 将 `frontend/index.html` 的 `<title>` 更新为 `AI Research Paper Writing Assistant with PDF RAG`。
- 标题包含 `AI`、`Research Paper`、`Writing Assistant`、`PDF RAG` 等核心检索关键词。

## 变更文件

- `frontend/index.html`

## 验证方式

- 检查 Git diff，确认仅修改前端页面标题文本。
- 运行前端构建检查。

## 验证结果

- `npm.cmd run build` 通过，前端生产构建成功。

## 关联文档 ID

- `FE-APP-0001`
- `OPS-0003`
