# FE-APP-0001｜前端启动、路由、布局与全局导航基线

## 需求

- 提供统一的应用入口、路由和页面布局。
- 全局装配层不承载具体业务实现。

## 功能

- 挂载 React 应用和全局样式。
- 注册问答、知识库、检索、写作和设置路由。
- 提供侧边栏导航与统一内容区域。

## 实现逻辑

- `main.tsx` 将应用挂载到 DOM，并注册全局提示组件。
- `App.tsx` 组合 Router、页面和会话 Provider。
- `Layout.tsx`、`Sidebar.tsx` 实现全局页面框架和导航。

## 代码范围

- `frontend/src/main.tsx`
- `frontend/src/index.css`
- `frontend/src/app/`

## 依赖边界

- 可以依赖 `pages`、`features`、`entities` 和 `shared`。
- 其他前端层不得反向依赖 `app`。
