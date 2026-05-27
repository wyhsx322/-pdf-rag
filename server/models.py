"""
Pydantic 请求/响应模型定义。
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


# ── 知识库 ──

class KBCreateRequest(BaseModel):
    """创建知识库请求体"""
    name: str = Field(..., min_length=1, max_length=50, description="知识库名称")
    type: Literal["work", "study", "personal"] = Field(default="work", description="知识库类型")
    description: str = Field(default="", max_length=200, description="知识库描述")


class KBResponse(BaseModel):
    """知识库响应体"""
    id: int
    name: str
    type: str
    description: str
    created_at: str
    document_count: int = 0


class KBDetailResponse(BaseModel):
    """知识库详情（含文档列表）"""
    id: int
    name: str
    type: str
    description: str
    created_at: str
    documents: list["DocumentResponse"] = []


# ── 文档 ──

class DocumentResponse(BaseModel):
    """文档响应体"""
    id: int
    kb_id: int
    filename: str
    original_name: str
    file_size: int
    status: str
    page_count: Optional[int] = None
    created_at: str


class BatchImportRequest(BaseModel):
    """批量导入请求体"""
    source_dir: str = Field(default="", description="要导入的目录路径（相对于项目根目录）")


# ── 切片 ──

class ChunkPreviewRequest(BaseModel):
    """切片预览请求体"""
    text: str = Field(..., description="要切片的文本")
    method: Literal["recursive", "sentence", "paragraph", "fixed"] = Field(default="recursive", description="切片方式")
    chunk_size: int = Field(default=1000, ge=100, le=5000, description="每个 chunk 的最大字符数")
    chunk_overlap: int = Field(default=200, ge=0, le=1000, description="相邻 chunk 重叠字符数")
    separators: list[str] = Field(default=["\n\n", "\n", "。", ".", "！", "？", "；", ";", " ", ""], description="分隔符列表")
    preserve_images: bool = Field(default=True, description="是否保留图片上下文")
    preserve_tables: bool = Field(default=True, description="是否保留表格上下文")


class ChunkResult(BaseModel):
    """单个切片结果"""
    chunk_id: str
    page: int
    text: str
    text_length: int
    has_figure: bool = False


class ChunkPreviewResponse(BaseModel):
    """切片预览响应"""
    total_chunks: int
    chunks: list[ChunkResult]
    avg_chunk_size: float


class ChunkExecuteRequest(BaseModel):
    """切片执行请求体"""
    method: Literal["recursive", "sentence", "paragraph", "fixed"] = Field(default="recursive")
    chunk_size: int = Field(default=1000, ge=100, le=5000)
    chunk_overlap: int = Field(default=200, ge=0, le=1000)
    separators: list[str] = Field(default=["\n\n", "\n", "。", ".", "！", "？", "；", ";", " ", ""])
    preserve_images: bool = Field(default=True)
    preserve_tables: bool = Field(default=True)


# ── 通用 ──

class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str
