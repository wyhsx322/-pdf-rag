# FE-SHARED-0001｜HTTP、渲染、状态与通用 UI 能力基线

## 需求

- 为所有页面提供无业务倾向的通用能力。
- 防止领域逻辑被错误放入共享层。

## 功能

- 提供统一 HTTP 客户端。
- 提供 Markdown、公式和代码渲染。
- 提供全局轻量状态和样式工具。
- 提供 Button、Dialog、Input、Tabs 等通用 UI。

## 实现逻辑

- `api/http.ts` 设置 `/api` 基础地址和请求超时。
- `components/Markdown.tsx` 组合 Markdown、GFM、KaTeX 和代码高亮插件。
- `state/useAppStore.ts` 使用 Zustand 保存跨页面状态。
- `lib/cn.ts` 合并条件样式。
- `ui/` 通过无业务属性构建基础组件。

## 代码范围

- `frontend/src/shared/`

## 依赖边界

- 不得导入 `entities`、`features`、`pages` 或 `app`。
- 仅当能力被多个业务域复用且不包含领域含义时才放入本模块。
