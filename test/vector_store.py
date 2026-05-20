"""
学术论文 RAG 系统的向量化存储模块。
使用 ChromaDB 作为本地向量数据库，DashScope text-embedding-v4 生成嵌入向量。
"""

import logging
import os
import time
import uuid
from typing import Optional

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

# text-embedding-v4 固定维度
_DIM = 1024
# 单次 API 调用最大文本数（text-embedding-v4 限制为 10）
_BATCH_LIMIT = 10


class VectorStoreManager:
    """管理嵌入向量生成、ChromaDB 存储及相似度检索。

    嵌入向量由阿里云 DashScope ``text-embedding-v4`` 通过 OpenAI 兼容接口生成。
    需要在环境变量或 ``.env`` 文件中配置 ``DASHSCOPE_API_KEY``。

    Args:
        embedding_model_name: DashScope 嵌入模型名称，默认 ``text-embedding-v4``。
        db_path: ChromaDB 数据库本地目录路径。
        collection_name: ChromaDB 集合名称，默认 ``"papers"``。
    """

    def __init__(
        self,
        embedding_model_name: str = "text-embedding-v4",
        db_path: str = "./output/chroma_demo",
        collection_name: str = "papers",
    ):
        self.collection_name = collection_name
        self.db_path = db_path
        self.model_name = embedding_model_name

        api_key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "未找到 DASHSCOPE_API_KEY，请在环境变量或 .env 文件中配置"
            )

        self._client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        logger.info("DashScope 客户端就绪，模型=%s", self.model_name)

        try:
            self._db = chromadb.PersistentClient(path=self.db_path)
        except Exception as e:
            raise RuntimeError(
                f"无法打开 ChromaDB 数据库 '{self.db_path}': {e}"
            ) from e

        self._collection = self._db.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "集合 '%s' 就绪（当前行数=%d，度量=cosine）",
            self.collection_name, self._collection.count(),
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _encode_batch(self, texts: list[str]) -> list[list[float]]:
        """通过 DashScope API 编码一批文本，失败时自动重试。"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = self._client.embeddings.create(
                    model=self.model_name,
                    input=texts,
                )
                return [item.embedding for item in resp.data]
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "嵌入 API 错误（第 %d/%d 次），%d 秒后重试: %s",
                        attempt + 1, max_retries, wait, e,
                    )
                    time.sleep(wait)
                else:
                    raise

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def insert_chunks(
        self,
        chunks: list[dict],
        source: str,
        replace: bool = False,
    ) -> int:
        """将分块文本编码为向量并写入数据库。

        Args:
            chunks: 分块字典列表，每个字典包含 ``text``、``page``、``metadata`` 键。
            source: 来源标识，写入 metadata。
            replace: 为 True 时先按 source 删除旧数据再插入。

        Returns:
            插入的行数。
        """
        if not chunks:
            logger.warning("insert_chunks 收到空列表")
            return 0

        if replace:
            self.delete_source(source)

        texts = [c["text"] for c in chunks]
        total = len(texts)
        logger.info("正在通过 %s 编码 %d 个分块 …", self.model_name, total)

        all_embeddings: list[list[float]] = []
        for i in range(0, total, _BATCH_LIMIT):
            batch = texts[i:i + _BATCH_LIMIT]
            all_embeddings.extend(self._encode_batch(batch))
            logger.info("  已编码 %d/%d", min(i + _BATCH_LIMIT, total), total)

        ids: list[str] = []
        metadatas: list[dict] = []
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            cid = meta.get("chunk_id", str(uuid.uuid4()))
            ids.append(cid)
            metadatas.append({
                "page": int(chunk["page"]),
                "source": source,
                "chunk_id": cid,
            })

        self._collection.add(
            ids=ids,
            embeddings=all_embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info("已向 '%s' 插入 %d 行", self.collection_name, total)
        return total

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """返回与查询文本最相似的前 *top_k* 个分块。

        Returns:
            字典列表，每个字典包含 ``text``、``page``、``source``、
            ``chunk_id`` 和 ``score`` 键。
        """
        if self._collection.count() == 0:
            logger.warning(
                "集合 '%s' 为空，返回空结果", self.collection_name
            )
            return []

        query_emb = self._encode_batch([query])[0]

        results = self._collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        formatted = []
        ids_list = results.get("ids", [[]])[0]
        docs_list = results.get("documents", [[]])[0]
        metas_list = results.get("metadatas", [[]])[0]
        dists_list = results.get("distances", [[]])[0]

        for i in range(len(ids_list)):
            meta = metas_list[i] if i < len(metas_list) else {}
            formatted.append({
                "text": docs_list[i] if i < len(docs_list) else "",
                "page": meta.get("page"),
                "source": meta.get("source", ""),
                "chunk_id": meta.get("chunk_id", ""),
                "score": dists_list[i] if i < len(dists_list) else 0.0,
            })
        return formatted

    def get_collection_stats(self) -> dict:
        """返回集合统计信息，包含当前行数。"""
        return {"row_count": self._collection.count()}

    def delete_source(self, source: str) -> int:
        """按 source 字段删除所有匹配行。

        Returns:
            删除的行数（通过前后行数差估算）。
        """
        before = self._collection.count()
        try:
            self._collection.delete(where={"source": source})
        except Exception as e:
            logger.error("按 source '%s' 删除失败: %s", source, e)
            return 0

        after = self._collection.count()
        deleted = before - after
        logger.info("已删除 source='%s' 的 %d 行", source, deleted)
        return deleted


# ---------------------------------------------------------------------------
# 快速验证
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    import pathlib
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print("用法: python vector_store.py <chunks_json_path> [db_path] [collection_name]")
        print("示例: python vector_store.py output/split_demo/demo1/demo1.json")
        print("      python vector_store.py output/split_demo/demo1/demo1.json ./output/chroma_demo/demo1 demo1_papers")
        sys.exit(1)

    chunks_file = pathlib.Path(sys.argv[1])
    if not chunks_file.exists():
        raise FileNotFoundError(f"分块文件未找到: {chunks_file}")

    name = chunks_file.stem
    db_path = sys.argv[2] if len(sys.argv) > 2 else f"./output/chroma_demo/{name}"
    collection_name = sys.argv[3] if len(sys.argv) > 3 else f"{name}_papers"

    chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
    logger.info("从 %s 加载了 %d 个分块", chunks_file, len(chunks))

    store = VectorStoreManager(
        embedding_model_name="text-embedding-v4",
        db_path=db_path,
        collection_name=collection_name,
    )

    source = name
    store.insert_chunks(chunks, source=source, replace=True)

    stats = store.get_collection_stats()
    logger.info("集合统计: %s", stats)

    results = store.search("建设性沟通与健康信息采纳", top_k=3)
    for r in results:
        logger.info("score=%.4f  page=%s  %s", r["score"], r["page"], r["chunk_id"])
        logger.info("  text: %s…", r["text"][:100])
