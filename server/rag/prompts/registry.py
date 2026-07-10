"""
Prompt 版本注册表。

所有 prompt 版本在此统一注册，调用方通过 get() 获取指定版本的 prompt。
新增版本只需在对应 vN/ 目录下添加模块并在 _REGISTRY 中注册。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PromptEntry:
    """单条 prompt 注册项。"""
    name: str
    version: str
    system: str
    user_template: str | None = None
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# 注册表主体 — 格式: (name, version) → PromptEntry
# 新增版本在此追加，不要修改已有条目（保证历史可复现）
# ---------------------------------------------------------------------------

def _build_registry() -> dict[tuple[str, str], PromptEntry]:
    from .v1 import query_understanding as qu_v1
    from .v1 import answer_generation as ag_v1
    from .v1 import hyde as hyde_v1
    from .v2 import query_understanding as qu_v2

    entries = [
        PromptEntry(
            name="query_understanding",
            version="v1",
            system=qu_v1.SYSTEM,
            user_template=qu_v1.USER_TEMPLATE,
            metadata=qu_v1.METADATA,
        ),
        PromptEntry(
            name="query_understanding",
            version="v2",
            system=qu_v2.SYSTEM,
            user_template=qu_v2.USER_TEMPLATE,
            metadata=qu_v2.METADATA,
        ),
        PromptEntry(
            name="answer_generation",
            version="v1",
            system=ag_v1.SYSTEM,
            user_template=ag_v1.USER_TEMPLATE,
            metadata=ag_v1.METADATA,
        ),
        PromptEntry(
            name="hyde",
            version="v1",
            system=hyde_v1.SYSTEM,
            user_template=hyde_v1.USER_TEMPLATE,
            metadata=hyde_v1.METADATA,
        ),
    ]
    return {(e.name, e.version): e for e in entries}


_REGISTRY: dict[tuple[str, str], PromptEntry] | None = None


def _get_registry() -> dict[tuple[str, str], PromptEntry]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------

LATEST: dict[str, str] = {
    "query_understanding": "v2",
    "answer_generation": "v1",
    "hyde": "v1",
}


def get(name: str, version: str | None = None) -> PromptEntry:
    """获取指定名称和版本的 prompt 条目。

    Args:
        name: prompt 名称，如 ``"query_understanding"``。
        version: 版本字符串，如 ``"v1"``。为 None 时使用 LATEST 中的最新版本。

    Returns:
        对应的 PromptEntry。

    Raises:
        KeyError: 名称或版本不存在。
    """
    if version is None:
        version = LATEST.get(name)
        if version is None:
            raise KeyError(f"未知 prompt 名称: {name!r}")

    key = (name, version)
    registry = _get_registry()
    if key not in registry:
        raise KeyError(f"prompt '{name}' 版本 '{version}' 不存在")
    return registry[key]


def list_versions(name: str) -> list[str]:
    """列出某个 prompt 的所有可用版本，按版本号排序。"""
    registry = _get_registry()
    versions = [v for (n, v) in registry if n == name]
    return sorted(versions)


def list_prompts() -> list[str]:
    """列出所有已注册的 prompt 名称（去重）。"""
    registry = _get_registry()
    return sorted({n for (n, _) in registry})
