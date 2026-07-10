"""
集中配置文件。

所有硬编码参数（模型名、路径、阈值、分块大小等）统一在此管理，
其他模块从此导入，避免分散在多个文件中重复定义。
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# 项目根目录
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parents[2]

# ---------------------------------------------------------------------------
# API / 服务
# ---------------------------------------------------------------------------

DASHSCOPE_API_KEY_ENV = "DASHSCOPE_API_KEY"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# ---------------------------------------------------------------------------
# 模型
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = "text-embedding-v4"
EMBEDDING_DIM = 1024          # text-embedding-v4 输出维度
EMBEDDING_BATCH_LIMIT = 10    # 单次 API 最大文本数

RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

# 查询处理 LLM（轻量、快速）
QUERY_LLM_MODEL = "qwen-turbo"
QUERY_LLM_TEMPERATURE = 0.3
QUERY_LLM_MAX_TOKENS = 512

# 多模态视觉模型（图片摘要）
VL_API_KEY_ENV = "DASHSCOPE_API_KEY"
VL_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
VL_MODEL = "qwen-vl-plus"
VL_TEMPERATURE = 0.3
VL_MAX_TOKENS = 800

# Modelscope 缓存路径
MODELSCOPE_CACHE_DIR = os.path.join(
    os.path.expanduser("~"), ".cache", "modelscope", "hub", "models"
)

# ---------------------------------------------------------------------------
# API 重试
# ---------------------------------------------------------------------------

MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# 文本分块
# ---------------------------------------------------------------------------

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
CHUNK_SEPARATORS = ["\n\n", "\n", "。", ".", "！", "？", "；", ";", " ", ""]

# 参考文献节标题正则模式（用于分块前删除文献部分）
# 以 # 开头（1-4 级标题），后跟参考/注释/引用相关关键词
REFERENCE_SECTION_PATTERNS = [
    r'^#{1,4}\s*参考文献',          # ### 参考文献:, #### 参考文献 [References]
    r'^#{1,4}\s*參考文獻',          # 繁体
    r'^#{1,4}\s*References',       # ### References
    r'^#{1,4}\s*Bibliography',     # ### Bibliography
    r'^#{1,4}\s*注释\s*($|\[|:)',  # ### 注释:, ### 注释 [Note]
    r'^#{1,4}\s*注釋\s*($|\[|:)',  # 繁体
    r'^#{1,4}\s*Notes\s*($|\[|:)', # ### Notes
    r'^#{1,4}\s*引用文献',          # ### 引用文献
    r'^#{1,4}\s*参考书目',          # ### 参考书目
]

# ---------------------------------------------------------------------------
# 检索
# ---------------------------------------------------------------------------

DEFAULT_TOP_K = 20             # 检索默认返回数（每路）
RRF_K = 60                     # RRF 融合常数

# ---------------------------------------------------------------------------
# ChromaDB
# ---------------------------------------------------------------------------

CHROMA_HNSW_SPACE = "cosine"

# ---------------------------------------------------------------------------
# 流水线目录（相对于项目根目录）
# ---------------------------------------------------------------------------

PRIMARY_DATA_DIR = "primary_datas"
OUTPUT_MARKDOWN_DIR = "output/markd_demo"
OUTPUT_SPLIT_DIR = "output/split_demo"
OUTPUT_CHROMA_DIR = "output/chroma_demo"

COLLECTION_NAME_SUFFIX = "_papers"  # 集合名: <name>_papers

# KB 级别集合配置（单集合架构）
KB_CHROMA_DIR_PREFIX = "kb_"      # ChromaDB 目录前缀: kb_{kb_id}
KB_COLLECTION_PREFIX = "kb_"      # 集合名前缀: kb_{kb_id}_papers

HASH_REGISTRY_FILE = "output/file_hash_registry.json"  # 文件哈希注册表
HASH_ALGORITHM = "sha256"  # 哈希算法

# ---------------------------------------------------------------------------
# RAG 生成
# ---------------------------------------------------------------------------

RAG_LLM_API_KEY_ENV = "DEEPSEEK_API_KEY"
RAG_LLM_BASE_URL = "https://api.deepseek.com/v1"
RAG_LLM_MODEL = "deepseek-chat"
RAG_LLM_TEMPERATURE = 0.3
RAG_LLM_MAX_TOKENS = 1024
RAG_MAX_CONTEXT_CHUNKS = 8        # 最多送入 LLM 的文本块数
RAG_MAX_CONTEXT_CHARS = 8000      # 上下文总字符数上限
RAG_REQUEST_TIMEOUT = 60          # API 请求超时（秒）

# 各智能体 LLM（默认保持原生成链路，仅评审默认独立为 Qwen）
COORDINATOR_LLM_API_KEY_ENV = RAG_LLM_API_KEY_ENV
COORDINATOR_LLM_BASE_URL = RAG_LLM_BASE_URL
COORDINATOR_LLM_MODEL = RAG_LLM_MODEL

LITERATURE_LLM_API_KEY_ENV = RAG_LLM_API_KEY_ENV
LITERATURE_LLM_BASE_URL = RAG_LLM_BASE_URL
LITERATURE_LLM_MODEL = RAG_LLM_MODEL

OUTLINE_LLM_API_KEY_ENV = RAG_LLM_API_KEY_ENV
OUTLINE_LLM_BASE_URL = RAG_LLM_BASE_URL
OUTLINE_LLM_MODEL = RAG_LLM_MODEL

WRITING_LLM_API_KEY_ENV = RAG_LLM_API_KEY_ENV
WRITING_LLM_BASE_URL = RAG_LLM_BASE_URL
WRITING_LLM_MODEL = RAG_LLM_MODEL

# 评审 / 评测 LLM（与写作模型解耦，避免同模型生成后自评）
REVIEW_LLM_API_KEY_ENV = "DASHSCOPE_API_KEY"
REVIEW_LLM_BASE_URL = DASHSCOPE_BASE_URL
REVIEW_LLM_MODEL = "qwen3.7-plus"

# ---------------------------------------------------------------------------
# 评测
# ---------------------------------------------------------------------------

EVAL_K_VALUES = (5, 10)
EVAL_METRIC_KEYS = [
    "Recall@5", "Recall@10",
    "Precision@5", "Precision@10",
    "MRR", "NDCG@10",
]

# ---------------------------------------------------------------------------
# 设备
# ---------------------------------------------------------------------------

DEVICE = "cuda"

# ---------------------------------------------------------------------------
# 运行时配置覆盖（来自 server/runtime_config.json，由前端「模型配置」页写入）
# 优先级：runtime_config.json > 环境变量 > 上方默认值。导入时一次性应用。
# ---------------------------------------------------------------------------


def _apply_runtime_overrides() -> None:
    import json

    store_path = PROJECT_ROOT / "server" / "runtime_config.json"
    if not store_path.exists():
        return
    try:
        store = json.loads(store_path.read_text(encoding="utf-8"))
    except Exception:
        return

    g = globals()

    # Runtime JSON stores model overrides only; API keys live in .env.
    models = store.get("models") or {}

    def _set(role: str, model_key: str | None, url_key: str | None, env_key: str | None = None):
        m = models.get(role) or {}
        if model_key and m.get("model"):
            g[model_key] = m["model"]
        if url_key and m.get("base_url"):
            g[url_key] = m["base_url"]
        if env_key and m.get("api_key_env"):
            g[env_key] = m["api_key_env"]

    _set("generation", "RAG_LLM_MODEL", "RAG_LLM_BASE_URL")
    _set("coordinator", "COORDINATOR_LLM_MODEL", "COORDINATOR_LLM_BASE_URL", "COORDINATOR_LLM_API_KEY_ENV")
    _set("literature", "LITERATURE_LLM_MODEL", "LITERATURE_LLM_BASE_URL", "LITERATURE_LLM_API_KEY_ENV")
    _set("outline", "OUTLINE_LLM_MODEL", "OUTLINE_LLM_BASE_URL", "OUTLINE_LLM_API_KEY_ENV")
    _set("writing", "WRITING_LLM_MODEL", "WRITING_LLM_BASE_URL", "WRITING_LLM_API_KEY_ENV")
    _set("review", "REVIEW_LLM_MODEL", "REVIEW_LLM_BASE_URL", "REVIEW_LLM_API_KEY_ENV")
    _set("embedding", "EMBEDDING_MODEL", "DASHSCOPE_BASE_URL")
    _set("query_llm", "QUERY_LLM_MODEL", None)
    _set("vl", "VL_MODEL", "VL_BASE_URL")
    _set("reranker", "RERANKER_MODEL", None)


_apply_runtime_overrides()
