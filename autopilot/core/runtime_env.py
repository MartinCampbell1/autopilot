"""Runtime environment sanitization for worker and teammate processes."""

from __future__ import annotations

import os
from collections.abc import Mapping

RUNTIME_ENV_EXACT_ALLOWLIST: frozenset[str] = frozenset(
    {
        "PATH",
        "HOME",
        "SHELL",
        "TERM",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LC_COLLATE",
        "LC_MESSAGES",
        "TZ",
        "TMPDIR",
        "TMP",
        "TEMP",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "NO_COLOR",
        "COLORTERM",
        "CI",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
    }
)

RUNTIME_ENV_PREFIX_ALLOWLIST: tuple[str, ...] = (
    "AUTOPILOT_",
    "CODEX_",
    "CLAUDE_",
    "OPENAI_",
    "ANTHROPIC_",
    "GOOGLE_",
    "GEMINI_",
    "OLLAMA_",
    "OPENROUTER_",
    "AZURE_",
    "AZURE_OPENAI_",
    "VERTEX_",
    "GOOGLE_CLOUD_",
    "XAI_",
    "GROQ_",
    "MISTRAL_",
    "TOGETHER_",
    "DEEPSEEK_",
    "HUGGINGFACE_",
    "HF_",
    "FIREWORKS_",
    "PERPLEXITY_",
    "LMSTUDIO_",
    "LOCALAI_",
    "VLLM_",
)


def runtime_env_key_allowed(key: str) -> bool:
    """Return whether one inherited environment key is safe to forward."""

    normalized = str(key or "").strip()
    if not normalized:
        return False
    if normalized in RUNTIME_ENV_EXACT_ALLOWLIST:
        return True
    return any(normalized.startswith(prefix) for prefix in RUNTIME_ENV_PREFIX_ALLOWLIST)


def build_runtime_base_env(base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a sanitized runtime env containing only safe inherited keys."""

    source = dict(base_env) if base_env is not None else dict(os.environ)
    sanitized = {
        str(key): str(value)
        for key, value in source.items()
        if runtime_env_key_allowed(str(key))
    }
    sanitized.setdefault("PATH", str(source.get("PATH") or os.defpath))
    return sanitized


__all__ = [
    "RUNTIME_ENV_EXACT_ALLOWLIST",
    "RUNTIME_ENV_PREFIX_ALLOWLIST",
    "build_runtime_base_env",
    "runtime_env_key_allowed",
]
