"""
Model capability registry with optional online updates.

Resolves three things per model:
  1. is_reasoning  -> whether to use reasoning-style API params
                      (reasoning_effort / max_completion_tokens) instead of
                      temperature / max_tokens.
  2. max_output    -> the model maximum output-token budget. Used to cap
                      gateway.max_tokens so we never request more than the
                      provider allows (which would cause an API error).
  3. context       -> context window size (informational).

Resolution order (first hit wins):
  a) Per-provider explicit override in api_keys config
     (providers.<name>.model_overrides.<model>).
  b) A locally cached online database (model_caps.cache.json) refreshed from
     OpenRouter public /api/v1/models endpoint at startup (best-effort,
     non-blocking, survives offline).
  c) A built-in static table of well-known model families below.
  d) Heuristic fallback: detect reasoning/thinking keywords in the model name.

This is deliberately conservative: when unsure we treat the model as a standard
chat model (temperature + max_tokens), which is the safe default for
OpenAI-compatible APIs.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in static table
# ---------------------------------------------------------------------------
# Keys are matched case-insensitively as SUBSTRINGS of the model name, so
# "deepseek-v4-flash" matches the "deepseek-v4" entry. Order matters: more
# specific patterns are listed first.
#
# max_output values reflect the provider advertised maximum output tokens.
# When a family has variants with different limits we use the smallest common
# safe value to avoid API errors; the online update will refine per-model.

_STATIC_TABLE = [
    # --- OpenAI reasoning family ---
    {"pattern": "o1-mini",            "reasoning": True,  "max_output": 65536, "context": 128000},
    {"pattern": "o1-preview",         "reasoning": True,  "max_output": 32768, "context": 128000},
    {"pattern": "o1",                 "reasoning": True,  "max_output": 100000, "context": 200000},
    {"pattern": "o3-mini",            "reasoning": True,  "max_output": 100000, "context": 200000},
    {"pattern": "o3",                 "reasoning": True,  "max_output": 100000, "context": 200000},
    {"pattern": "o4-mini",            "reasoning": True,  "max_output": 100000, "context": 200000},
    # --- DeepSeek ---
    {"pattern": "deepseek-reasoner",  "reasoning": True,  "max_output": 8192,  "context": 64000},
    {"pattern": "deepseek-r1",        "reasoning": True,  "max_output": 8192,  "context": 64000},
    {"pattern": "deepseek-v4-pro",    "reasoning": False, "max_output": 8192,  "context": 128000},
    {"pattern": "deepseek-v4-flash",  "reasoning": False, "max_output": 8192,  "context": 128000},
    {"pattern": "deepseek-v4",        "reasoning": False, "max_output": 8192,  "context": 128000},
    {"pattern": "deepseek-v3",        "reasoning": False, "max_output": 8192,  "context": 64000},
    # --- Xiaomi MiMo ---
    {"pattern": "mimo-v2.5-pro",      "reasoning": True,  "max_output": 131072, "context": 1048576},
    {"pattern": "mimo-v2.5",          "reasoning": True,  "max_output": 16384, "context": 1048576},
    {"pattern": "mimo",               "reasoning": True,  "max_output": 16384, "context": 1048576},
    # --- Qwen ---
    {"pattern": "qwen3-max-thinking", "reasoning": True,  "max_output": 32768, "context": 262144},
    {"pattern": "qwen3-plus-thinking","reasoning": True,  "max_output": 32768, "context": 131072},
    {"pattern": "qwen3.7-max",        "reasoning": False, "max_output": 16384, "context": 131072},
    {"pattern": "qwen3.7-plus",       "reasoning": False, "max_output": 16384, "context": 131072},
    {"pattern": "qwen3.6-plus",       "reasoning": False, "max_output": 16384, "context": 131072},
    {"pattern": "qwq",                "reasoning": True,  "max_output": 16384, "context": 131072},
    {"pattern": "qwen",               "reasoning": False, "max_output": 8192,  "context": 32768},
    # --- Moonshot Kimi ---
    {"pattern": "kimi-k2-thinking",   "reasoning": True,  "max_output": 262144, "context": 262144},
    {"pattern": "kimi-k2.7",          "reasoning": False, "max_output": 16384, "context": 131072},
    {"pattern": "kimi-k2.6",          "reasoning": False, "max_output": 16384, "context": 131072},
    {"pattern": "kimi",               "reasoning": False, "max_output": 8192,  "context": 128000},
    # --- Minimax ---
    {"pattern": "minimax-m3",         "reasoning": False, "max_output": 16384, "context": 1000000},
    {"pattern": "minimax-m2.7",       "reasoning": False, "max_output": 16384, "context": 245760},
    {"pattern": "minimax-m2.5",       "reasoning": False, "max_output": 16384, "context": 245760},
    {"pattern": "minimax",            "reasoning": False, "max_output": 8192,  "context": 245760},
    # --- GLM / Zhipu ---
    {"pattern": "glm-5.1",            "reasoning": False, "max_output": 16384, "context": 128000},
    {"pattern": "glm-5",              "reasoning": False, "max_output": 16384, "context": 128000},
    {"pattern": "glm-4",              "reasoning": False, "max_output": 4096,  "context": 128000},
    {"pattern": "glm-zero",           "reasoning": True,  "max_output": 16384, "context": 128000},
    # --- Google Gemini ---
    {"pattern": "gemini-3.1-flash-thinking", "reasoning": True,  "max_output": 65536, "context": 1000000},
    {"pattern": "gemini-3-pro",              "reasoning": False, "max_output": 8192,  "context": 2000000},
    {"pattern": "gemini-3-flash",            "reasoning": False, "max_output": 8192,  "context": 1000000},
    {"pattern": "gemini-2.5-pro",            "reasoning": True,  "max_output": 8192,  "context": 2000000},
    {"pattern": "gemini",                    "reasoning": False, "max_output": 8192,  "context": 128000},
    # --- Anthropic Claude ---
    {"pattern": "claude-opus-4",      "reasoning": True,  "max_output": 32000, "context": 200000},
    {"pattern": "claude-sonnet-4",    "reasoning": True,  "max_output": 64000, "context": 200000},
    {"pattern": "claude-3.7",         "reasoning": True,  "max_output": 8192,  "context": 200000},
    {"pattern": "claude-3.5",         "reasoning": False, "max_output": 8192,  "context": 200000},
    {"pattern": "claude",             "reasoning": False, "max_output": 4096,  "context": 200000},
    # --- Misc open models ---
    {"pattern": "llama-3.3",          "reasoning": False, "max_output": 4096,  "context": 128000},
    {"pattern": "llama-3.1",          "reasoning": False, "max_output": 4096,  "context": 128000},
    {"pattern": "llama",              "reasoning": False, "max_output": 4096,  "context": 8000},
    {"pattern": "mistral-large",      "reasoning": False, "max_output": 8192,  "context": 128000},
    {"pattern": "mistral",            "reasoning": False, "max_output": 4096,  "context": 32000},
    {"pattern": "gemma",              "reasoning": False, "max_output": 8192,  "context": 128000},
]

# Substrings that strongly indicate a reasoning / thinking model when nothing
# in the static or online table matched.
_REASONING_HINTS = (
    "reason", "think", "thinking", "-r1", "qwq", "reasoner",
    "o1", "o3", "o4", "deepseek-reason", "mimo", "zero",
)

# Conservative default for completely unknown models.
_DEFAULT_MAX_OUTPUT = 4096
_DEFAULT_CONTEXT = 32768

# ---------------------------------------------------------------------------
# Online update (best-effort)
# ---------------------------------------------------------------------------

_CACHE_FILENAME = "model_caps.cache.json"
_ONLINE_URL = "https://openrouter.ai/api/v1/models"
_ONLINE_TIMEOUT = 8  # seconds
_REFRESH_INTERVAL = 24 * 3600  # refresh at most once per day


def _cache_path() -> Path:
    here = Path(__file__).resolve().parent
    cfg_dir = here.parent / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / _CACHE_FILENAME


def _try_online_update() -> Optional[Dict[str, Any]]:
    """Fetch OpenRouter public model list and cache it.

    Returns the parsed mapping {model_id: {max_output, context, reasoning}}
    or None on any failure. Never raises.
    """
    cache_p = _cache_path()
    # Skip refresh if cache is fresh enough.
    try:
        if cache_p.exists():
            age = cache_p.stat().st_mtime
            if (time.time() - age) < _REFRESH_INTERVAL:
                with open(cache_p, "r", encoding="utf-8") as f:
                    return json.load(f)
    except Exception:
        pass

    try:
        req = urlrequest.Request(
            _ONLINE_URL,
            headers={"User-Agent": "ReportQA/1.0 model-capability-updater"},
        )
        with urlrequest.urlopen(req, timeout=_ONLINE_TIMEOUT) as resp:
            raw = resp.read()
        data = json.loads(raw)
        table = {}
        for m in data.get("data", []):
            mid = m.get("id", "")
            if not mid:
                continue
            top = m.get("top_provider") or {}
            max_out = top.get("max_completion_tokens") or m.get("max_completion_tokens")
            ctx = m.get("context_length")
            is_reason = any(h in mid.lower() for h in _REASONING_HINTS)
            table[mid.lower()] = {
                "max_output": int(max_out) if max_out else None,
                "context": int(ctx) if ctx else None,
                "reasoning": is_reason,
            }
        with open(cache_p, "w", encoding="utf-8") as f:
            json.dump(table, f, ensure_ascii=False)
        logger.info(f"Model capability online update: {len(table)} models cached.")
        return table
    except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError) as e:
        logger.warning(f"Model capability online update failed: {e}")
    except Exception as e:
        logger.warning(f"Model capability online update unexpected error: {e}")
    return None


# Lazily-populated module-level cache.
_online_cache = None
_online_loaded = False


def _ensure_online_loaded() -> Dict[str, Any]:
    global _online_cache, _online_loaded
    if _online_loaded:
        return _online_cache or {}
    _online_loaded = True
    _online_cache = _try_online_update()
    return _online_cache or {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_capabilities(model, provider_overrides=None) -> dict:
    """Resolve capabilities for a model name.

    Args:
        model: The model id as used in the API request.
        provider_overrides: Optional dict from the provider config, e.g.
            {"deepseek-v4-flash": {"reasoning": False, "max_output": 8192}}.
            Highest priority.

    Returns:
        {"reasoning": bool, "max_output": int, "context": int, "source": str}
    """
    if not model:
        return {
            "reasoning": False,
            "max_output": _DEFAULT_MAX_OUTPUT,
            "context": _DEFAULT_CONTEXT,
            "source": "empty",
        }
    mlower = model.lower()

    # 1. Explicit per-provider override.
    if provider_overrides:
        ov = provider_overrides.get(model) or provider_overrides.get(mlower)
        if ov:
            return {
                "reasoning": bool(ov.get("reasoning", False)),
                "max_output": int(ov.get("max_output", _DEFAULT_MAX_OUTPUT)),
                "context": int(ov.get("context", _DEFAULT_CONTEXT)),
                "source": "override",
            }

    # 2. Resolve reasoning flag + baseline caps from the static table. The
    #    static table is human-curated and more reliable than the online
    #    heuristic for the reasoning/thinking distinction.
    static_row = None
    for row in _STATIC_TABLE:
        if row["pattern"] in mlower:
            static_row = row
            break
    if static_row:
        is_reason = bool(static_row["reasoning"])
        base_max = int(static_row["max_output"])
        base_ctx = int(static_row["context"])
        source = "static"
    else:
        is_reason = any(h in mlower for h in _REASONING_HINTS)
        base_max = _DEFAULT_MAX_OUTPUT
        base_ctx = _DEFAULT_CONTEXT
        source = "heuristic"

    # 3. Refine max_output / context from the online cache when available.
    #    Online data has per-model precision that the static table cannot
    #    keep up with, but we do NOT trust its reasoning flag.
    online = _ensure_online_loaded()
    if online:
        hit = _match_online(online, mlower)
        if hit:
            entry = online[hit]
            online_max = entry.get("max_output")
            online_ctx = entry.get("context")
            if online_max and online_max > 0:
                base_max = min(int(online_max), 262144)
            if online_ctx and online_ctx > 0:
                base_ctx = int(online_ctx)
            source = "static+online" if static_row else "heuristic+online"

    return {
        "reasoning": is_reason,
        "max_output": base_max,
        "context": base_ctx,
        "source": source,
    }


def _match_online(online, mlower) -> Optional[str]:
    """Find the best online-table key for a local model name."""
    if mlower in online:
        return mlower
    # Strip vendor prefixes: "deepseek-ai/deepseek-v4-flash" vs "deepseek-v4-flash"
    best = None
    best_len = 0
    for key in online:
        suffix = key.split("/", 1)[-1] if "/" in key else key
        if suffix == mlower or mlower in suffix or suffix in mlower:
            if len(suffix) > best_len:
                best = key
                best_len = len(suffix)
    return best


def is_reasoning_model(model, provider_overrides=None) -> bool:
    return get_capabilities(model, provider_overrides)["reasoning"]


def max_output_tokens(model, provider_overrides=None) -> int:
    return get_capabilities(model, provider_overrides)["max_output"]


def refresh_online() -> Optional[Dict[str, Any]]:
    """Force a refresh of the online cache (e.g. from a Settings button)."""
    global _online_cache, _online_loaded
    _online_loaded = False
    _online_cache = None
    try:
        p = _cache_path()
        if p.exists():
            p.unlink()
    except Exception:
        pass
    return _try_online_update()
