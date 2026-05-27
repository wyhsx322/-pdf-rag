"""
文档处理器：单篇/批量 PDF 流水线 + 向量库 CRUD。

集中管理路径解析、流水线编排和进度追踪，服务器路由层统一通过此类
访问底层 pipeline 函数，不再自行拼接路径。
"""

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from .config import (
    PROJECT_ROOT,
    PRIMARY_DATA_DIR,
    OUTPUT_MARKDOWN_DIR,
    OUTPUT_SPLIT_DIR,
    OUTPUT_CHROMA_DIR,
    COLLECTION_NAME_SUFFIX,
)

logger = logging.getLogger(__name__)


# ── 结果类型 ──

@dataclass
class ProcessResult:
    """单篇处理结果"""
    doc_id: int
    success: bool
    message: str
    page_count: int = 0
    chunk_count: int = 0


@dataclass
class BatchEvent:
    """批量处理进度事件（适配 SSE 推送）"""
    doc_id: int
    original_name: str
    status: str   # "processing" | "done" | "error"
    message: str
    step: str = ""  # 当前步骤描述


# ── 处理器 ──

class DocumentProcessor:
    """文档流水线处理器，绑定一个知识库。

    Args:
        kb_name: 知识库名称（对应 primary_datas/{kb_name}/ 目录）。
    """

    def __init__(self, kb_name: str):
        self.kb_name = kb_name

    # ──────────────────────────────────────
    # 路径解析
    # ──────────────────────────────────────

    @staticmethod
    def doc_dir_name(doc_id: int) -> str:
        """文档级目录名: ``doc_{doc_id}``"""
        return f"doc_{doc_id}"

    def pdf_path(self, doc: dict) -> Path:
        """PDF 源文件路径: ``primary_datas/{kb_name}/{doc_id}_{original_name}``"""
        return PROJECT_ROOT / PRIMARY_DATA_DIR / self.kb_name / doc["filename"]

    def md_dir(self, doc_id: int) -> Path:
        """Markdown 产物目录: ``output/markd_demo/doc_{doc_id}/``"""
        return PROJECT_ROOT / OUTPUT_MARKDOWN_DIR / self.doc_dir_name(doc_id)

    def md_path(self, doc_id: int) -> Path:
        """Markdown 文件路径: ``output/markd_demo/doc_{doc_id}/doc_{doc_id}.md``"""
        dn = self.doc_dir_name(doc_id)
        return PROJECT_ROOT / OUTPUT_MARKDOWN_DIR / dn / f"{dn}.md"

    def chunks_dir(self, doc_id: int) -> Path:
        """分块产物目录: ``output/split_demo/doc_{doc_id}/``"""
        return PROJECT_ROOT / OUTPUT_SPLIT_DIR / self.doc_dir_name(doc_id)

    def chunks_path(self, doc_id: int) -> Path:
        """分块 JSON 路径: ``output/split_demo/doc_{doc_id}/doc_{doc_id}.json``"""
        dn = self.doc_dir_name(doc_id)
        return PROJECT_ROOT / OUTPUT_SPLIT_DIR / dn / f"{dn}.json"

    def chroma_dir(self, doc_id: int) -> Path:
        """ChromaDB 持久化目录: ``output/chroma_demo/doc_{doc_id}/``"""
        return PROJECT_ROOT / OUTPUT_CHROMA_DIR / self.doc_dir_name(doc_id)

    def collection_name(self, doc_id: int) -> str:
        """ChromaDB 集合名: ``doc_{doc_id}_papers``"""
        return f"{self.doc_dir_name(doc_id)}{COLLECTION_NAME_SUFFIX}"

    # ──────────────────────────────────────
    # 流水线步骤
    # ──────────────────────────────────────

    def step1_pdf_to_md(self, doc_id: int, pdf_src: Path | None = None) -> Path:
        """PDF → Markdown。

        Args:
            doc_id: 文档 ID。
            pdf_src: PDF 源文件路径，为 None 时需通过 doc 字典推导（需要先调用 pdf_path）。

        Returns:
            生成的 .md 文件路径。
        """
        from .pipeline import step1_pdf_to_md

        md = self.md_path(doc_id)
        src = pdf_src or self.md_dir(doc_id)  # fallback 无效，调用方应提供 pdf_src
        logger.info("[1/3] 解析 PDF: %s", src)
        step1_pdf_to_md(Path(src), md)
        return md

    def step1_5_summarize_images(self, doc_id: int) -> None:
        """图片 → AI 摘要（写入 figure_summaries.json）。"""
        from .pipeline import step1_5_summarize_images

        md_dir = self.md_dir(doc_id)
        md = self.md_path(doc_id)
        if not md.exists():
            logger.warning("Markdown 不存在，跳过图片摘要: %s", md)
            return
        step1_5_summarize_images(md_dir, md, source=self.doc_dir_name(doc_id))

    def step2_md_to_chunks(self, doc_id: int) -> Path:
        """Markdown → 分块 JSON。

        Returns:
            生成的 .json 文件路径。
        """
        from .pipeline import step2_md_to_chunks

        md = self.md_path(doc_id)
        if not md.exists():
            raise FileNotFoundError(f"Markdown 文件不存在: {md}")
        chunks = self.chunks_path(doc_id)
        logger.info("[2/3] 切分 Markdown: %s", md)
        step2_md_to_chunks(md, chunks, source=self.doc_dir_name(doc_id))
        return chunks

    def step3_chunks_to_db(self, doc_id: int) -> None:
        """分块 → 向量编码 → ChromaDB 入库。"""
        from .pipeline import step3_chunks_to_db

        chunks = self.chunks_path(doc_id)
        if not chunks.exists():
            raise FileNotFoundError(f"分块文件不存在: {chunks}")
        logger.info("[3/3] 向量化入库: %s", chunks)
        step3_chunks_to_db(
            chunks,
            db_path=str(self.chroma_dir(doc_id)),
            collection_name=self.collection_name(doc_id),
            source=self.doc_dir_name(doc_id),
            md_dir=self.md_dir(doc_id),
        )

    # ──────────────────────────────────────
    # 单篇完整流水线
    # ──────────────────────────────────────

    def process_one(self, doc_id: int, pdf_src: Path | None = None) -> ProcessResult:
        """执行单篇完整流水线：PDF→Markdown→图片摘要→分块→向量入库。

        Args:
            doc_id: 文档 ID。
            pdf_src: PDF 源文件路径，为 None 时根据 kb_name + doc 记录推导。

        Returns:
            ProcessResult 包含成功/失败状态和统计信息。
        """
        try:
            if pdf_src is None:
                return ProcessResult(
                    doc_id=doc_id, success=False,
                    message="pdf_src 不能为 None，请通过 pdf_path(doc) 获取",
                )

            if not Path(pdf_src).exists():
                return ProcessResult(
                    doc_id=doc_id, success=False,
                    message=f"PDF 文件不存在: {pdf_src}",
                )

            self.step1_pdf_to_md(doc_id, pdf_src=Path(pdf_src))
            self.step1_5_summarize_images(doc_id)

            chunks_path = self.step2_md_to_chunks(doc_id)
            chunk_count = 0
            if chunks_path.exists():
                chunks_data = json.loads(chunks_path.read_text(encoding="utf-8"))
                chunk_count = len(chunks_data)

            self.step3_chunks_to_db(doc_id)

            # 计算页数（复用 text_splitter 的页面解析器）
            from .text_splitter import _parse_markdown_to_pages
            md = self.md_path(doc_id)
            page_count = 0
            if md.exists():
                text = md.read_text(encoding="utf-8")
                page_map = _parse_markdown_to_pages(text)
                page_count = len(page_map)

            return ProcessResult(
                doc_id=doc_id, success=True,
                message="处理完成",
                page_count=page_count, chunk_count=chunk_count,
            )
        except Exception as e:
            logger.exception("文档 %d 处理失败", doc_id)
            return ProcessResult(
                doc_id=doc_id, success=False,
                message=str(e),
            )

    # ──────────────────────────────────────
    # 批量流水线（生成器）
    # ──────────────────────────────────────

    def process_batch(self, docs: list[dict]) -> Generator[BatchEvent, None, None]:
        """批量处理多篇文档，逐篇 yield 进度事件。

        单篇失败不中断批量，捕获异常后记录 error 事件并继续处理下一篇。

        Args:
            docs: 文档记录列表（每条包含 id, filename, original_name, kb_id 等字段）。

        Yields:
            BatchEvent: 进度事件，status 依次为 "processing" → "done"/"error"。
        """
        for doc in docs:
            doc_id = doc["id"]
            original_name = doc.get("original_name", f"ID={doc_id}")
            pdf_src = self.pdf_path(doc)

            yield BatchEvent(
                doc_id=doc_id, original_name=original_name,
                status="processing", message="开始处理…",
            )

            if not pdf_src.exists():
                yield BatchEvent(
                    doc_id=doc_id, original_name=original_name,
                    status="error", message=f"PDF 文件不存在: {pdf_src}",
                )
                self._update_doc_status(doc_id, "error")
                continue

            try:
                yield BatchEvent(
                    doc_id=doc_id, original_name=original_name,
                    status="processing", message="Step 1/3: PDF 解析中…",
                    step="pdf_to_md",
                )
                self.step1_pdf_to_md(doc_id, pdf_src=pdf_src)

                # 解析完成后立即计算页数
                md = self.md_path(doc_id)
                pg_count = 0
                if md.exists():
                    from .text_splitter import _parse_markdown_to_pages
                    text = md.read_text(encoding="utf-8")
                    pg_count = len(_parse_markdown_to_pages(text))
                self._update_doc_status(doc_id, "parsed", page_count=pg_count)

                yield BatchEvent(
                    doc_id=doc_id, original_name=original_name,
                    status="processing", message="Step 1.5/3: 图片摘要生成中…",
                    step="summarize_images",
                )
                self.step1_5_summarize_images(doc_id)

                yield BatchEvent(
                    doc_id=doc_id, original_name=original_name,
                    status="processing", message="Step 2/3: 文本切片中…",
                    step="chunking",
                )
                self.step2_md_to_chunks(doc_id)
                self._update_doc_status(doc_id, "chunked")

                yield BatchEvent(
                    doc_id=doc_id, original_name=original_name,
                    status="processing", message="Step 3/3: 向量化入库中…",
                    step="indexing",
                )
                self.step3_chunks_to_db(doc_id)
                self._update_doc_status(doc_id, "indexed")

                yield BatchEvent(
                    doc_id=doc_id, original_name=original_name,
                    status="done", message="处理完成",
                )
            except Exception as e:
                logger.exception("文档 %d (%s) 处理失败", doc_id, original_name)
                self._update_doc_status(doc_id, "error")
                yield BatchEvent(
                    doc_id=doc_id, original_name=original_name,
                    status="error", message=str(e),
                )

    # ──────────────────────────────────────
    # 向量库 CRUD
    # ──────────────────────────────────────

    def get_vector_stats(self, doc_id: int) -> dict:
        """获取文档的向量库统计信息。

        Returns:
            包含 doc_id, collection_name, collection_exists, vector_count 的字典。
        """
        import chromadb

        collection_name = self.collection_name(doc_id)
        chroma_dir = str(self.chroma_dir(doc_id))

        stats = {
            "doc_id": doc_id,
            "collection_name": collection_name,
            "collection_exists": False,
            "vector_count": 0,
        }

        if Path(chroma_dir).exists():
            try:
                client = chromadb.PersistentClient(path=chroma_dir)
                collections = client.list_collections()
                for col in collections:
                    if col.name == collection_name:
                        stats["collection_exists"] = True
                        stats["vector_count"] = col.count()
                        break
            except Exception as e:
                logger.warning("获取向量统计失败: %s", e)

        return stats

    def delete_vectors(self, doc_id: int) -> bool:
        """删除文档的向量库数据。

        优先通过 ChromaDB API 删除 collection，失败时回退到直接删除目录。

        Returns:
            是否成功删除。
        """
        import chromadb

        collection_name = self.collection_name(doc_id)
        chroma_dir = str(self.chroma_dir(doc_id))

        deleted = False
        try:
            client = chromadb.PersistentClient(path=chroma_dir)
            client.delete_collection(collection_name)
            deleted = True
        except Exception:
            dir_path = self.chroma_dir(doc_id)
            if dir_path.exists():
                shutil.rmtree(str(dir_path), ignore_errors=True)
                deleted = True

        return deleted

    def reindex(self, doc_id: int) -> None:
        """重新索引：删除旧向量库 + 从已有分块重新入库。

        Raises:
            FileNotFoundError: 分块文件不存在。
            Exception: 索引过程中的其他错误。
        """
        # 先删除旧向量
        self.delete_vectors(doc_id)

        # 检查分块数据存在
        chunks = self.chunks_path(doc_id)
        if not chunks.exists():
            raise FileNotFoundError(f"切片数据不存在: {chunks}")

        # 重新入库
        self.step3_chunks_to_db(doc_id)

    def search_in_doc(self, doc_id: int, query: str, top_k: int = 10) -> list[dict]:
        """在单个文档的向量库中检索。

        Args:
            doc_id: 文档 ID。
            query: 查询文本。
            top_k: 返回结果数。

        Returns:
            检索结果列表，每项包含 text, page, source, chunk_id, score。
        """
        from .vector_store import VectorStoreManager

        chroma_dir = str(self.chroma_dir(doc_id))
        if not Path(chroma_dir).exists():
            return []

        store = VectorStoreManager(
            db_path=chroma_dir,
            collection_name=self.collection_name(doc_id),
        )
        return store.search(query, top_k=top_k)

    # ──────────────────────────────────────
    # 辅助方法
    # ──────────────────────────────────────

    @staticmethod
    def _update_doc_status(doc_id: int, status: str, page_count: int | None = None) -> None:
        """更新数据库中文档的处理状态和可选页数。"""
        try:
            from server.database import get_connection
            conn = get_connection()
            if page_count is not None:
                conn.execute(
                    "UPDATE documents SET status = ?, page_count = ? WHERE id = ?",
                    (status, page_count, doc_id),
                )
            else:
                conn.execute("UPDATE documents SET status = ? WHERE id = ?", (status, doc_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("更新文档 %d 状态失败: %s", doc_id, e)
