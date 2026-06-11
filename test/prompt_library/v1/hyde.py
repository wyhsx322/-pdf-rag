"""
hyde v1 — HyDE（假设文档生成）提示词。

HyDE 让 LLM 生成一段"假设的论文段落"来回答查询，
用该段落的 embedding 向量代替查询向量进行检索，
缩小 query-document 之间的语义分布差距。

v1：通用学术段落风格，约 150-200 字。
v2 计划：按 intent 定制风格（分析型用论证结构，比较型用对比结构）。
"""

METADATA = {
    "version": "v1",
    "model_hint": "qwen-turbo",
    "max_tokens": 300,
    "temperature": 0.5,
    "output_type": "free_text",
    "use_when": ["analytical", "comparative"],
}

SYSTEM = """\
你是一位学术论文写作助手。根据用户给出的研究问题，撰写一段约 150-200 字的假设论文段落。

要求：
- 使用学术论文的语气和专业术语
- 内容围绕问题的核心概念展开，给出合理的学术性回答
- 不要直接复述问题，而是像论文正文一样自然地论述
- 输出纯文本，不加标题或编号
"""

USER_TEMPLATE = """\
研究问题：{query}

假设段落：\
"""
