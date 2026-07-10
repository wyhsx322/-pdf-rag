"""论文项目长期记忆模块：基于 ChromaDB 的语义向量存储。

每个论文项目有独立的向量集合（thesis_mem_{project_id}），
存储文献研究阶段提炼的论点和证据，供写作 Agent 跨会话检索。

JD 关键词：Long-term Memory、Persistent State、Cross-session Context
"""

import os
import uuid
from pathlib import Path

from server.core.config import (
    DASHSCOPE_API_KEY_ENV,
    DASHSCOPE_BASE_URL,
    EMBEDDING_MODEL,
    CHROMA_HNSW_SPACE,
    PROJECT_ROOT,
)

# 记忆存储根目录（与 paper_rag.db 同级）
MEMORY_CHROMA_DIR = PROJECT_ROOT / "data" / "thesis_memory"


class ProjectMemory:
    """论文项目的长期向量记忆。

    Args:
        project_id: 论文项目 ID，用于隔离各项目的记忆空间。
    """

    def __init__(self, project_id: int):
        self.project_id = project_id
        self._collection_name = f"thesis_mem_{project_id}"
        self._db_path = str(MEMORY_CHROMA_DIR)
        self._store = None  # 懒加载

    def _get_store(self):
        """懒加载 VectorStoreManager，避免在 API key 未配置时报错。"""
        if self._store is None:
            from server.rag.retrieval.vector_store import VectorStoreManager
            MEMORY_CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            self._store = VectorStoreManager(
                embedding_model_name=EMBEDDING_MODEL,
                db_path=self._db_path,
                collection_name=self._collection_name,
            )
        return self._store

    def save_arguments(self, texts: list[str], source: str = "literature") -> int:
        """将论点/证据文本向量化并存入记忆。

        Args:
            texts: 文本列表（每条是一个论点或证据片段）
            source: 来源标识（literature / writing 等）

        Returns:
            成功保存的条数
        """
        if not texts:
            return 0
        try:
            store = self._get_store()
            chunks = [
                {
                    "text": t,
                    "page": 0,
                    "metadata": {
                        "chunk_id": uuid.uuid4().hex,
                        "source": source,
                        "project_id": self.project_id,
                    },
                }
                for t in texts
                if t.strip()
            ]
            return store.insert_chunks(chunks, source=source, replace=False)
        except Exception:
            return 0

    def search_similar(self, query: str, top_k: int = 5) -> list[dict]:
        """语义检索与 query 最相关的历史论点/证据。

        Returns:
            结果列表，每条含 text 和 score（距离越小越相关）
        """
        try:
            store = self._get_store()
            if store.get_collection_stats()["row_count"] == 0:
                return []
            results = store.search(query=query, top_k=top_k)
            return [{"text": r["text"], "score": r["score"]} for r in results]
        except Exception:
            return []

    def get_count(self) -> int:
        """返回记忆中存储的条数。"""
        try:
            return self._get_store().get_collection_stats()["row_count"]
        except Exception:
            return 0
