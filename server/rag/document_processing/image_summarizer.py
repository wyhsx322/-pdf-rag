"""
图片摘要生成器。

使用 DeepSeek 多模态模型 (deepseek-chat) 对学术论文图片
生成结构化 JSON 摘要，存入文本向量库供检索。
"""

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from server.core.config import (
    VL_API_KEY_ENV,
    VL_BASE_URL,
    VL_MODEL,
    VL_TEMPERATURE,
    VL_MAX_TOKENS,
    MAX_RETRIES,
)

load_dotenv()

logger = logging.getLogger(__name__)

_IMAGE_SUMMARY_PROMPT = """你是一个学术论文图片分析专家。请详细分析这张图片，按以下JSON格式输出：

{
    "figure_type": "图片类型（流程图/表格/柱状图/折线图/框架图/示意图/地图/截图/其他）",
    "description": "图片内容的详细学术描述，包括展示的数据、变量关系、趋势变化、层次结构等（200-300字）",
    "key_elements": ["关键元素1", "关键元素2", "关键元素3"],
    "keywords": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"]
}

只输出JSON，不要markdown代码块包裹，不要其他解释文字。"""


def _encode_image_base64(image_path: str) -> str:
    """将图片编码为 base64 data URL。"""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    # 根据扩展名确定 MIME 类型
    ext = Path(image_path).suffix.lower()
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}
    return f"data:image/{mime.get(ext, 'jpeg')};base64,{b64}"


class ImageSummarizer:
    """多模态图片摘要生成器。

    Args:
        model: DeepSeek 视觉模型名称，默认 ``deepseek-chat``。
        temperature: 生成温度。
    """

    def __init__(
        self,
        model: str = VL_MODEL,
        temperature: float = VL_TEMPERATURE,
    ):
        api_key = os.environ.get(VL_API_KEY_ENV, "")
        if not api_key:
            raise RuntimeError(
                f"未找到 {VL_API_KEY_ENV}，请在环境变量或 .env 文件中配置"
            )

        self._client = OpenAI(
            api_key=api_key,
            base_url=VL_BASE_URL,
        )
        self._model = model
        self._temperature = temperature
        logger.info("ImageSummarizer 就绪，模型=%s base_url=%s", model, VL_BASE_URL)

    def _parse_summary(self, raw: str) -> dict:
        """解析 LLM 返回的 JSON，处理可能的格式问题。"""
        raw = raw.strip()
        # 去掉可能的 markdown 代码块包裹
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("JSON 解析失败，原始输出: %s", raw[:200])
            return {
                "figure_type": "未知",
                "description": raw[:500],
                "key_elements": [],
                "keywords": [],
            }

    def summarize_image(self, image_path: str, caption: str = "") -> Optional[dict]:
        """对单张图片生成结构化摘要。

        Args:
            image_path: 图片文件的绝对路径。
            caption: 图片标题（可选，作为提示补充）。

        Returns:
            结构化摘要字典，失败时返回 None。
        """
        if not os.path.isfile(image_path):
            logger.warning("图片文件不存在: %s", image_path)
            return None

        prompt = _IMAGE_SUMMARY_PROMPT
        if caption:
            prompt += f"\n\n参考标题: {caption}"

        data_url = _encode_image_base64(image_path)

        for attempt in range(MAX_RETRIES):
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    temperature=self._temperature,
                    max_tokens=VL_MAX_TOKENS,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": data_url}},
                            {"type": "text", "text": prompt},
                        ],
                    }],
                )
                raw = resp.choices[0].message.content.strip()
                summary = self._parse_summary(raw)
                logger.info(
                    "图片摘要: %s → type=%s, keywords=%s",
                    os.path.basename(image_path),
                    summary.get("figure_type", "?"),
                    summary.get("keywords", []),
                )
                return summary
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "VL API 错误（第 %d/%d 次），%d 秒后重试: %s",
                        attempt + 1, MAX_RETRIES, wait, e,
                    )
                    time.sleep(wait)
                else:
                    logger.error("图片摘要生成失败: %s → %s", image_path, e)
                    return None

    def summarize_all(
        self, image_dir: str, captions: dict[str, str] | None = None
    ) -> list[dict]:
        """对目录下所有 JPEG/PNG 图片生成摘要。

        Args:
            image_dir: 图片所在目录。
            captions: {filename: caption_text} 映射（可选）。

        Returns:
            [{"image_file": "xxx.jpeg", "image_path": "...",
              "summary": {...}, "summary_text": "..."}, ...]
        """
        captions = captions or {}
        results = []
        image_files = sorted(
            f for f in os.listdir(image_dir)
            if f.lower().endswith(('.jpeg', '.jpg', '.png', '.gif', '.webp'))
        )

        if not image_files:
            logger.warning("目录中无图片: %s", image_dir)
            return results

        logger.info("开始生成 %d 张图片摘要...", len(image_files))
        for fname in image_files:
            img_path = os.path.join(image_dir, fname)
            caption = captions.get(fname, "")
            logger.info("  处理: %s%s", fname, f" (标题: {caption})" if caption else "")

            summary = self.summarize_image(img_path, caption)
            if summary is None:
                continue

            # 构建检索用文本
            parts = [f"图片摘要: {summary.get('figure_type', '')}"]
            if caption:
                parts.append(f"标题: {caption}")
            parts.append(summary.get("description", ""))
            keywords = "、".join(summary.get("keywords", []))
            if keywords:
                parts.append(f"关键词: {keywords}")
            summary_text = "。".join(parts)

            results.append({
                "image_file": fname,
                "image_path": os.path.abspath(img_path),
                "summary": summary,
                "summary_text": summary_text,
            })

        logger.info("图片摘要生成完成: %d/%d 张成功", len(results), len(image_files))
        return results
