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

PROJECT_ROOT = Path(__file__).parent.parent

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
