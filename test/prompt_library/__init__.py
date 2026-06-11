"""
Prompt 库包。提供版本化的提示词管理。

使用方式：
    from test.prompt_library import registry
    prompt = registry.get("query_understanding", version="v1")
"""

from . import registry

__all__ = ["registry"]
