"""LLM Gateway for Windows RAG System."""
import os
from typing import List, Dict, Any, Generator
from openai import OpenAI

from utils.logger import setup_logger
from utils.file_io import read_json

logger = setup_logger("llm_gateway")


class LLMGateway:
    """Unified LLM gateway supporting multiple providers."""

    def __init__(self, config_path: str = "config/api_keys.local.json", fallback_path: str = "config/api_keys.json"):
        """Initialize gateway with provider configs.

        Args:
            config_path: Primary config path (local/persistent).
            fallback_path: Fallback config path.
        """
        self.config = self._load_config(config_path, fallback_path)
        self.provider = self.config.get("default_provider", "")
        self.model = self.config.get("default_model", "")
        self.client = None
        self._init_client()

    def _load_config(self, primary: str, fallback: str) -> Dict[str, Any]:
        """Load configuration with fallback chain.

        Args:
            primary: Primary config path.
            fallback: Fallback config path.

        Returns:
            Merged configuration dict.
        """
        config = read_json(primary)
        if not config.get("providers"):
            config = read_json(fallback)
        
        # Override with environment variables for all providers
        for provider_name in config.get("providers", {}):
            env_key = os.getenv(f"{provider_name.upper().replace('-', '_')}_API_KEY")
            if env_key:
                config["providers"][provider_name]["api_key"] = env_key
        
        # Legacy OpenAI env var
        env_key = os.getenv("OPENAI_API_KEY")
        if env_key and "providers" in config and "openai" in config["providers"]:
            config["providers"]["openai"]["api_key"] = env_key
        
        return config

    def _init_client(self) -> None:
        """Initialize OpenAI-compatible client."""
        if not self.provider or not self.model:
            logger.info("No provider configured, skipping client initialization")
            return

        providers = self.config.get("providers", {})
        pconf = providers.get(self.provider, {})
        
        base_url = pconf.get("base_url", "")
        api_key = pconf.get("api_key", "")
        
        # Check if provider needs API key
        is_key_optional = self.provider in ("local",) or api_key in ("not-needed", "")
        
        if not api_key and not is_key_optional:
            logger.warning(f"No API key configured for {self.provider}")
        
        if not base_url:
            logger.warning(f"No base URL configured for {self.provider}")
            return
        
        # Ensure base_url ends with /v1 for OpenAI-compatible APIs
        if base_url and not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
            # Some providers like Gemini already include the full path
            if "googleapis.com" not in base_url and "anthropic.com" not in base_url:
                base_url = base_url.rstrip("/") + "/v1"
        
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key or "dummy",
        )

    def update_provider(self, provider: str, model: str | None = None) -> None:
        """Switch provider/model.

        Args:
            provider: Provider name.
            model: Optional model override.
        """
        self.provider = provider
        if model:
            self.model = model
        self._init_client()

    def chat(self, query: str, context: str, system_prompt: str | None = None) -> str:
        """Send chat completion request.

        Args:
            query: User question.
            context: Retrieved context.
            system_prompt: Optional custom system prompt.

        Returns:
            Generated response text.
        """
        if not self.client:
            return "Error: API not configured. Please configure your API in Settings."

        if not system_prompt:
            system_prompt = (
                "You are a helpful document analysis assistant. "
                "Answer based ONLY on the provided context. "
                "If the answer is not in the context, say so. "
                "Cite sources using [1], [2] format."
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=8192,
            )
            content = response.choices[0].message.content or ""
            if not response.choices[0].message.content:
                logger.warning(f"LLM returned empty content. finish_reason={response.choices[0].finish_reason}, usage={response.usage}")
            return content
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return f"Error: {e}"

    def stream_chat(self, query: str, context: str, system_prompt: str | None = None) -> Generator[str, None, None]:
        """Stream chat completion.

        Args:
            query: User question.
            context: Retrieved context.
            system_prompt: Optional custom system prompt.

        Yields:
            Token strings.
        """
        if not self.client:
            yield "Error: API not configured. Please configure your API in Settings."
            return

        if not system_prompt:
            system_prompt = (
                "You are a helpful document analysis assistant. "
                "Answer based ONLY on the provided context."
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ]

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=4096,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            yield f"Error: {e}"

    def list_models(self) -> List[str]:
        """List available models for current provider.

        Returns:
            List of model names.
        """
        providers = self.config.get("providers", {})
        pconf = providers.get(self.provider, {})
        return pconf.get("models", [])
