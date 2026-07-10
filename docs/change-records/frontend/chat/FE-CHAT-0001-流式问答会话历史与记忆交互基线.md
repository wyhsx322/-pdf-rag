# FE-CHAT-0001｜流式问答、会话历史与记忆交互基线

## 需求

- 提供流式知识库问答和可恢复的历史会话。
- 展示答案证据、图表和记忆处理状态。

## 功能

- 选择知识库并发送问题。
- 接收 SSE 文本、来源、图表和记忆事件。
- 创建、加载、删除历史会话。
- 审核长期记忆候选项。

## 实现逻辑

- `pages/chat/Chat.tsx` 管理输入、流式消息、来源面板和交互状态。
- `features/chat-session/api.ts` 封装问答 SSE、会话和记忆接口。
- `ChatContext.tsx` 在页面和侧边栏之间共享当前会话状态。
- `entities/chat/model.ts` 定义消息和会话模型。

## 代码范围

- `frontend/src/pages/chat/`
- `frontend/src/features/chat-session/`
- `frontend/src/entities/chat/`

## 依赖边界

- 依赖知识库实体和 `shared`。
- 会话能力不依赖具体页面实现。
