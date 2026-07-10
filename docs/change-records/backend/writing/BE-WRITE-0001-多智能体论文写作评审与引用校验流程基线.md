# BE-WRITE-0001｜多智能体论文写作、评审与引用校验流程基线

## 需求

- 基于知识库证据完成论文大纲、章节写作、评审和引用校验。
- 支持人工确认与可追踪的 Agent 执行过程。

## 功能

- 文献检索与证据整理。
- 大纲生成和确认。
- 分章节生成、评审、重写和连贯性维护。
- 引用解析、证据匹配和风险提示。
- LangGraph 工作流与 Agent Trace。

## 实现逻辑

- `coordinator.py` 判断任务阶段并调度专业 Agent。
- `literature.py` 调用 RAG 检索形成证据池。
- `outline.py` 生成结构化大纲。
- `writing.py` 按章节检索、生成正文并附带引用。
- `review.py` 给出结构、论证、证据和表达评分。
- `citation_verifier.py` 将正文论断与证据池匹配。
- `workflow.py` 串联节点、状态和人工确认分支。
- 项目与章节记忆用于保持术语和上下文一致。

## 代码范围

- `server/writing/`
- `server/api/routes/agent.py`

## 依赖边界

- 可以依赖 `core`、`rag` 和记忆能力。
- 不得依赖前端或评测模块。
