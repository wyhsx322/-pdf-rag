# BE-MEM-0001｜短中长期对话记忆与人工审核机制基线

## 需求

- 控制长对话上下文规模，同时保留跨轮次的重要信息。
- 长期记忆必须支持人工审核，避免错误信息自动固化。

## 功能

- 管理最近消息和 Token 窗口。
- 生成会话摘要并维护中期上下文。
- 提取、审核、检索和记录长期记忆。

## 实现逻辑

- `short_term.py` 截取近期消息，超限后生成摘要。
- `mid_term.py` 将会话摘要持久化到 SQLite。
- `long_term.py` 保存候选记忆状态、正式记忆和使用记录。
- `manager.py` 聚合三类记忆，为聊天接口生成统一上下文包。

## 代码范围

- `server/memory/short_term.py`
- `server/memory/mid_term.py`
- `server/memory/long_term.py`
- `server/memory/manager.py`

## 依赖边界

- 依赖 `server/core`。
- 记忆模块不负责 HTTP 返回和页面状态。
