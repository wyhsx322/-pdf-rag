# AI 应用开发面试准备与项目优化路线

## 市场 JD 归纳

AI 应用开发岗通常不只看“会调大模型 API”，更看能否把 LLM 做成稳定产品。结合近期公开岗位描述与主流工程文档，可以把要求归纳为 6 类：

1. 后端与服务化：Python、FastAPI/Flask、异步任务、SSE/流式输出、接口设计、错误处理。
2. RAG 工程：文档解析、切片、Embedding、向量库、关键词检索、混合检索、Reranker、引用溯源。
3. Agent 与工具调用：任务拆解、工具编排、多轮状态、长任务进度、失败恢复、人机协同。
4. Prompt/Context Engineering：系统提示词、Few-shot、结构化输出、上下文压缩、引用约束、防幻觉。
5. 评测与观测：Recall@K、MRR、NDCG、Faithfulness、Answer Relevancy、成本/延迟监控、线上反馈闭环。
6. 前端产品化：React/TypeScript、可解释结果展示、配置面板、上传/处理/问答完整流程。

参考方向：

- [AWS：What is Retrieval-Augmented Generation?](https://aws.amazon.com/what-is/retrieval-augmented-generation/) 强调：RAG 用外部权威知识源增强 LLM，提升准确性、来源可追溯和开发者控制力。
- [LangSmith Evaluation](https://docs.smith.langchain.com/evaluation) 强调：LLM 应用需要离线评测、线上监控和持续改进闭环。
- [LlamaIndex Evaluating](https://docs.llamaindex.ai/en/stable/module_guides/evaluating/) 强调：RAG 不只评回答，也要独立评估检索质量，常用 MRR、hit-rate、precision 等指标。

## 当前项目适合讲的亮点

这个项目可以定位为“面向论文研究场景的多模态 RAG 与写作 Agent 工作台”，比普通聊天机器人更有作品集价值：

1. 数据侧：PDF 解析、图片/表格摘要、切片策略、知识库管理。
2. 检索侧：向量检索 + BM25 + RRF，可选查询改写、HyDE、BGE reranker。
3. 生成侧：流式问答、引用来源、图文证据、多轮记忆。
4. 工程侧：FastAPI + React + TypeScript，SSE、SQLite、ChromaDB、成本记录。
5. 优化侧：已有检索评测脚本，并新增了搜索质量诊断面板。

面试表达建议：

> 我重点解决的是 RAG 质量不稳定的问题。项目不是只把 PDF 丢进向量库，而是做了混合检索、查询改写、重排序、引用溯源和评测指标，并在前端展示检索诊断，让调参有可观察依据。

## 本次新增能力

搜索接口新增 `diagnostics` 字段，前端搜索页新增“检索质量诊断”面板，展示：

- 结果数量、文档覆盖、图表证据数量、平均片段长度。
- RRF 分数区分度、最高向量/BM25/RRF 分数。
- 可信度等级：high / medium / low。
- 风险信号：召回过少、分数过近、片段过短/过长、跨文档覆盖不足等。
- 优化建议：开启查询改写、调整 chunk_size/overlap、开启 reranker、补充关键词等。

这让项目从“能用”走向“可调优”，更贴近 AI 应用开发岗对效果优化的要求。

## 后续优化优先级

### P0：效果闭环

1. 建黄金测试集：按精确查找、概念解释、方法对比、跨论文综合、图表理解分 5 类问题。
2. 做自动评测页面：把 `evaluations/eval_retrieval.py` 的 Recall@K、MRR、NDCG 接到前端。
3. 做 A/B 策略对比：baseline、rewrite、HyDE、reranker、不同 chunk 参数并排对比。
4. 做回答评测：Faithfulness、引用覆盖率、答案相关性、无法回答时的拒答质量。

### P1：回答质量

1. 引用校验：回答中的 `[^N]` 必须来自检索上下文，禁止编造来源。
2. 上下文压缩：按 query relevance 压缩长 chunk，减少噪声和 token 成本。
3. 冲突证据处理：当不同论文结论冲突时，要求模型分来源说明。
4. 不确定性表达：证据不足时明确说明缺口，而不是强答。

### P2：Agent 工作流

1. 论文综述 Agent：检索 -> 观点聚类 -> 提纲 -> 段落写作 -> 引用校验。
2. 质量审稿 Agent：检查逻辑跳跃、引用缺失、重复表达、术语不一致。
3. 长任务队列：后台任务状态、失败重试、断点续跑。

### P3：工程化

1. 配置版本化：保存每次评测使用的模型、chunk 参数、top_k、reranker 开关。
2. 权限与隔离：多用户知识库隔离，文件访问安全。
3. 部署说明：Docker Compose，一键启动前后端和向量库。
4. 可观测性：请求日志、token 成本、延迟分位数、错误率。

## 学习路线

1. Python Web：FastAPI、Pydantic、异步、SSE、后台任务。
2. RAG 基础：Embedding、向量库、BM25、RRF、reranker、chunk 策略。
3. RAG 评测：Recall@K、Precision@K、MRR、NDCG、Faithfulness、Answer Relevancy。
4. Prompt/Context：Few-shot、结构化输出、引用约束、上下文压缩、防 prompt injection。
5. Agent：工具调用、状态机、LangGraph/LangChain、失败恢复、人机协同。
6. 前端：React + TypeScript、状态管理、流式渲染、诊断可视化。
7. 部署与观测：Docker、日志、成本监控、CI、基础云服务。

## 简历项目描述示例

> 学术论文多模态 RAG 与写作 Agent 工作台：基于 FastAPI + React + ChromaDB 实现 PDF 解析、图表摘要、混合检索、流式问答与引用溯源。检索链路采用 Embedding + BM25 + RRF，并支持查询改写、HyDE 和 BGE reranker；构建 Recall@K/MRR/NDCG 评测脚本，并新增检索质量诊断面板，从文档覆盖、分数区分度、切片粒度等维度给出风险信号和调优建议。
