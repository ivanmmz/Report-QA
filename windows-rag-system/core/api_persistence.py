"""API persistence handler for Windows RAG System.

Manages persistent storage of API configurations with support for:
- Multiple provider presets (OpenAI, Gemini, DeepSeek, Anthropic, etc.)
- Custom provider management
- Environment variable overrides
- Default provider/model switching
"""
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from utils.file_io import read_json, write_json
from utils.logger import setup_logger

logger = setup_logger("api_persistence")

class APIPersistence:
    """Handles persistent storage of API configuration."""

    def __init__(
        self,
        local_path: str = "config/api_keys.local.json",
        template_path: str = "config/api_keys.json",
    ):
        """Initialize persistence handler.

        Args:
            local_path: Persistent local config path.
            template_path: Default template config path.
        """
        self.local_path = Path(local_path)
        self.template_path = Path(template_path)
        self._ensure_local()

    def _ensure_local(self) -> None:
        """Ensure local config exists. If missing, create empty file (don't auto-fill)."""
        if not self.local_path.exists():
            # Create empty config - user must configure everything themselves
            write_json(self.local_path, {
                "providers": {},
                "default_provider": "",
                "default_model": ""
            })
            logger.info("Created empty local API config")

    def load(self) -> Dict[str, Any]:
        """Load API configuration with fallback chain.

        Priority:
        1. local config
        2. template config
        3. environment variables

        Returns:
            Merged configuration dict.
        """
        config = read_json(self.local_path)
        
        if not config:
            config = read_json(self.template_path)
        
        # Apply env overrides for all known providers
        for provider_name in config.get("providers", {}):
            env_key = os.getenv(f"{provider_name.upper().replace('-', '_')}_API_KEY")
            if env_key:
                providers = config.get("providers", {})
                if provider_name in providers:
                    providers[provider_name]["api_key"] = env_key
        
        # Legacy OpenAI env var
        env_key = os.getenv("OPENAI_API_KEY")
        if env_key:
            providers = config.get("providers", {})
            if "openai" in providers:
                providers["openai"]["api_key"] = env_key
        
        return config

    def save(self, config: Dict[str, Any]) -> None:
        """Save configuration to local persistent storage.

        Args:
            config: Configuration dict to persist.
        """
        write_json(self.local_path, config)
        logger.info("Saved API configuration")

    def update_key(self, provider: str, api_key: str) -> None:
        """Update API key for a provider.

        Args:
            provider: Provider name (e.g., 'openai').
            api_key: New API key.
        """
        config = self.load()
        providers = config.get("providers", {})
        
        if provider not in providers:
            providers[provider] = {}
        
        providers[provider]["api_key"] = api_key
        config["providers"] = providers
        self.save(config)
        logger.info(f"Updated API key for {provider}")

    def update_provider_config(
        self,
        provider: str,
        api_key: str | None = None,
        base_url: str | None = None,
        models: List[str] | None = None,
        description: str | None = None,
    ) -> None:
        """Update provider configuration.

        Args:
            provider: Provider name.
            api_key: Optional API key.
            base_url: Optional base URL.
            models: Optional model list.
            description: Optional description.
        """
        config = self.load()
        providers = config.get("providers", {})
        
        if provider not in providers:
            providers[provider] = {}
        
        pconf = providers[provider]
        
        if api_key is not None:
            pconf["api_key"] = api_key
        if base_url is not None:
            pconf["base_url"] = base_url
        if models is not None:
            pconf["models"] = models
        if description is not None:
            pconf["description"] = description
        
        config["providers"] = providers
        self.save(config)
        logger.info(f"Updated configuration for {provider}")

    def update_provider(self, provider: str, model: str | None = None) -> None:
        """Update default provider and optionally model.

        Args:
            provider: Provider name.
            model: Optional model name.
        """
        config = self.load()
        config["default_provider"] = provider
        if model:
            config["default_model"] = model
        self.save(config)
        logger.info(f"Updated default provider to {provider}")

    def add_provider(
        self,
        name: str,
        base_url: str,
        models: List[str],
        api_key: str = "",
        description: str = "",
    ) -> None:
        """Add a new custom provider.

        Args:
            name: Provider name.
            base_url: API base URL.
            models: List of model names.
            api_key: API key.
            description: Description.
        """
        config = self.load()
        providers = config.get("providers", {})
        
        providers[name] = {
            "base_url": base_url,
            "models": models,
            "api_key": api_key,
            "description": description,
        }
        
        config["providers"] = providers
        self.save(config)
        logger.info(f"Added new provider: {name}")

    def remove_provider(self, name: str) -> None:
        """Remove a provider.

        Args:
            name: Provider name.
        """
        config = self.load()
        providers = config.get("providers", {})
        
        if name in providers:
            del providers[name]
            config["providers"] = providers
            self.save(config)
            logger.info(f"Removed provider: {name}")

    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """Get configuration for a specific provider.

        Args:
            provider: Provider name.

        Returns:
            Provider config dict.
        """
        config = self.load()
        providers = config.get("providers", {})
        return providers.get(provider, {})

    def validate(self) -> Dict[str, bool]:
        """Validate API keys.

        Returns:
            Dict mapping provider names to validity.
        """
        config = self.load()
        providers = config.get("providers", {})
        results = {}
        
        for name, pconf in providers.items():
            key = pconf.get("api_key", "")
            if name == "local":
                results[name] = True  # Local doesn't need key
            else:
                results[name] = bool(key) and key not in ("", "dummy", "not-needed")
        
        return results

    def get_providers(self) -> Dict[str, Any]:
        """Get providers list.

        Returns:
            Providers dict.
        """
        config = self.load()
        return config.get("providers", {})

    def get_default(self) -> tuple[str, str]:
        """Get default provider and model.

        Returns:
            Tuple of (provider, model). Returns empty strings if not configured.
        """
        config = self.load()
        provider = config.get("default_provider", "")
        model = config.get("default_model", "")
        return provider, model

    def is_configured(self) -> bool:
        """Check if API is configured (default provider set and has API key).

        Returns:
            True if configured and valid.
        """
        provider, model = self.get_default()
        if not provider or not model:
            return False
        pconf = self.get_provider_config(provider)
        key = pconf.get("api_key", "")
        return bool(key) and key not in ("", "dummy", "not-needed")

    def get_default_provider_config(self) -> Dict[str, Any]:
        """Get default provider configuration.

        Returns:
            Default provider config.
        """
        provider, _ = self.get_default()
        return self.get_provider_config(provider)

    def reset_to_defaults(self) -> None:
        """Reset configuration to empty state (no provider, no key)."""
        config = {
            "providers": {},
            "default_provider": "",
            "default_model": "",
        }
        self.save(config)
        logger.info("Reset API configuration to empty state")
