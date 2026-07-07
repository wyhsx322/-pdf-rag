"""Runtime model settings and local API key management."""

import json
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values, load_dotenv, set_key
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import test.config as cfg

router = APIRouter()

CONFIG_PATH = Path(__file__).parent.parent / "runtime_config.json"
ENV_PATH = PROJECT_ROOT / ".env"
MANAGED_KEYS = ["DASHSCOPE_API_KEY", "DEEPSEEK_API_KEY"]


def load_store() -> dict:
    """Read model runtime settings. API keys are intentionally excluded."""
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return {"models": data.get("models") or {}}
        except Exception:
            pass
    return {"models": {}}


def save_store(data: dict) -> None:
    payload = {"models": data.get("models") or {}}
    CONFIG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def default_models() -> dict:
    return {
        "generation": {"model": cfg.RAG_LLM_MODEL, "base_url": cfg.RAG_LLM_BASE_URL},
        "embedding": {"model": cfg.EMBEDDING_MODEL, "base_url": cfg.DASHSCOPE_BASE_URL},
        "query_llm": {"model": cfg.QUERY_LLM_MODEL, "base_url": cfg.DASHSCOPE_BASE_URL},
        "vl": {"model": cfg.VL_MODEL, "base_url": cfg.VL_BASE_URL},
        "reranker": {"model": cfg.RERANKER_MODEL},
    }


def effective_models(store: dict) -> dict:
    models = default_models()
    for role, override in (store.get("models") or {}).items():
        if role in models and isinstance(override, dict):
            models[role].update({k: v for k, v in override.items() if v})
    return models


def _mask(value: str) -> str:
    if not value:
        return ""
    tail = value[-4:] if len(value) >= 4 else value
    return "****" + tail


def _env_value(env: str) -> str:
    value = os.environ.get(env, "")
    if value:
        return value
    return (dotenv_values(ENV_PATH).get(env) or "").strip()


def key_state(env: str) -> dict:
    val = _env_value(env)
    return {"configured": bool(val), "hint": _mask(val)}


def save_env_key(env: str, value: str) -> None:
    ENV_PATH.touch(exist_ok=True)
    set_key(str(ENV_PATH), env, value, quote_mode="never")
    os.environ[env] = value


def apply_runtime_config() -> None:
    """Load local .env keys into the process before business modules are used."""
    load_dotenv(ENV_PATH, override=False)


class ModelRole(BaseModel):
    model: str
    base_url: Optional[str] = None


class SettingsUpdate(BaseModel):
    keys: dict[str, str] = Field(default_factory=dict)
    models: dict[str, ModelRole] = Field(default_factory=dict)


class TestRequest(BaseModel):
    provider: str


@router.get("/settings")
def get_settings():
    store = load_store()
    return {
        "keys": {env: key_state(env) for env in MANAGED_KEYS},
        "models": effective_models(store),
    }


@router.put("/settings")
def update_settings(req: SettingsUpdate):
    store = load_store()
    store.setdefault("models", {})

    for env, val in req.keys.items():
        if env in MANAGED_KEYS and val.strip():
            save_env_key(env, val.strip())

    defaults = default_models()
    for role, m in req.models.items():
        if role not in defaults:
            continue
        patch = {"model": m.model}
        if m.base_url is not None:
            patch["base_url"] = m.base_url
        store["models"][role] = patch

    save_store(store)
    return get_settings()


@router.post("/settings/test")
def test_connection(req: TestRequest):
    env = req.provider
    if env not in MANAGED_KEYS:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    api_key = _env_value(env)
    if not api_key:
        return {"ok": False, "message": "API key is not configured"}

    models = effective_models(load_store())
    try:
        from openai import OpenAI

        if env == "DEEPSEEK_API_KEY":
            role = models["generation"]
            client = OpenAI(api_key=api_key, base_url=role.get("base_url"), timeout=20)
            client.chat.completions.create(
                model=role["model"],
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return {"ok": True, "message": f"DeepSeek ({role['model']}) connection ok"}

        role = models["embedding"]
        client = OpenAI(api_key=api_key, base_url=role.get("base_url"), timeout=20)
        client.embeddings.create(model=role["model"], input="ping")
        return {"ok": True, "message": f"DashScope ({role['model']}) connection ok"}
    except Exception as e:
        return {"ok": False, "message": f"Connection failed: {str(e)[:160]}"}
